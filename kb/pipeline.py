import asyncio
import json
import time
from collections.abc import Callable, Iterator

from app.models import Chunk, ContentItem
from app.settings import settings
from ingestion.filter import is_authored_content
from kb.chunker import chunk_item
from kb.embedder import Embedder, VertexEmbedder
from kb.store import filter_new_hashes, upsert_chunks

# Called after each batch completes, with a snapshot of running stats + elapsed.
ProgressCallback = Callable[[dict], None]


async def run_ingestion(
    items: Iterator[ContentItem],
    embedder: Embedder | None = None,
    on_progress: ProgressCallback | None = None,
) -> dict[str, int]:
    """
    Full ingestion pipeline: filter → chunk → dedup → batch embed → upsert.

    Concurrency is real and bounded: at most `embed_concurrency` batches are
    in flight at once. We acquire the semaphore BEFORE launching each batch
    task, which both caps parallel Vertex calls and applies backpressure on
    the item stream — so memory stays bounded even for 50MB+ exports.

    Args:
        items: Raw ContentItem stream from any SourceAdapter.
        embedder: Override for testing. Defaults to VertexEmbedder from settings.
        on_progress: Optional callback invoked after each batch with a stats
            snapshot (total_chunks, inserted, dupes_skipped, batches, elapsed).

    Returns:
        Stats dict: total_chunks, inserted, dupes_skipped, batches.
    """
    if embedder is None:
        embedder = VertexEmbedder(
            model=settings.vertex_embedding_model,
            dim=settings.vertex_embedding_dim,
            project=settings.google_cloud_project,
            location=settings.vertex_location,
        )

    sem = asyncio.Semaphore(settings.embed_concurrency)
    stats: dict[str, int] = {
        "total_chunks": 0,
        "inserted": 0,
        "dupes_skipped": 0,
        "batches": 0,
    }
    start = time.monotonic()
    tasks: list[asyncio.Task] = []

    async def flush(b: list[Chunk]) -> None:
        try:
            hashes = [c.content_hash for c in b]
            new_hashes = await filter_new_hashes(hashes)
            new_chunks = [c for c in b if c.content_hash in new_hashes]
            # Single sync statement — atomic on the asyncio event loop.
            stats["dupes_skipped"] += len(b) - len(new_chunks)

            if new_chunks:
                embeddings = await embedder.embed_batch([c.text for c in new_chunks])
                rows = [
                    _make_row(c, emb)
                    for c, emb in zip(new_chunks, embeddings, strict=True)
                ]
                # Resolve the await FIRST, then do the atomic += — otherwise the
                # read-modify-write straddles an await and concurrent flushes
                # clobber each other's increment (lost updates).
                inserted = await upsert_chunks(rows)
                stats["inserted"] += inserted

            stats["batches"] += 1
            if on_progress is not None:
                on_progress({**stats, "elapsed": round(time.monotonic() - start, 1)})
        finally:
            sem.release()

    async def dispatch(b: list[Chunk]) -> None:
        # Acquire before creating the task: blocks the producer once
        # `embed_concurrency` batches are already in flight (backpressure).
        await sem.acquire()
        tasks.append(asyncio.create_task(flush(b)))

    # Intra-run dedup: a content_hash seen earlier in THIS run never enters a
    # second batch. Combined with the per-batch DB pre-filter, this guarantees
    # every row handed to upsert is genuinely new — so inserted == len(rows),
    # and we avoid paying to embed the same text twice within one export.
    seen: set[str] = set()
    batch: list[Chunk] = []
    for item in items:
        if not is_authored_content(item):
            continue
        for chunk in chunk_item(item):
            stats["total_chunks"] += 1
            if chunk.content_hash in seen:
                stats["dupes_skipped"] += 1
                continue
            seen.add(chunk.content_hash)
            batch.append(chunk)

            if len(batch) >= settings.embed_batch_size:
                await dispatch(batch)
                batch = []

    if batch:
        await dispatch(batch)

    await asyncio.gather(*tasks)
    return stats


def _make_row(chunk: Chunk, embedding: list[float]) -> dict:
    return {
        "content_hash": chunk.content_hash,
        "source_id": chunk.source_id,
        "source": chunk.source,
        "content_type": chunk.content_type,
        "text": chunk.text,
        "authored_at": chunk.authored_at,
        "url": chunk.url,
        "lang": chunk.lang,
        # pgvector accepts "[x,y,z]" text literal cast to ::vector
        "embedding": "[" + ",".join(f"{x:.8f}" for x in embedding) + "]",
        "embedding_model": settings.vertex_embedding_model,
        "dim": settings.vertex_embedding_dim,
        "extra": json.dumps(chunk.extra),
    }
