import json
import tempfile
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text

import ingestion.adapters  # noqa: F401 — triggers @register decorators
from app.db import engine, run_migrations
from app.settings import settings
from ingestion.base import REGISTRY
from kb.pipeline import run_ingestion
from rag.citations import build_citations
from rag.generator import stream_gemini
from rag.prompt import RAG_SYSTEM, build_prompt
from rag.retriever import MIN_RETRIEVAL_SCORE, embed_query, retrieve


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await run_migrations()
    yield


app = FastAPI(title="Cortex", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}


# ── Ingest ────────────────────────────────────────────────────────────────────

@app.post("/ingest")
async def ingest_endpoint(
    source: str = Form(...),
    file: UploadFile = File(...),  # noqa: B008
) -> dict[str, int]:
    """
    Accept a social export file and run the full ingestion pipeline.
    Returns: {total_chunks, inserted, dupes_skipped}
    """
    if source not in REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Valid: {sorted(REGISTRY)}",
        )

    suffix = Path(file.filename or "export").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        adapter = REGISTRY[source]()
        items = adapter.parse(tmp_path)
        stats = await run_ingestion(items)
    finally:
        tmp_path.unlink(missing_ok=True)

    return stats


# ── Seed demo data ───────────────────────────────────────────────────────────

_DEMO_FILES = [
    ("linkedin",   "testing_data/linkedin_shares_mock.csv"),
    ("linkedin",   "testing_data/linkedin_articles_mock.csv"),
    ("twitter",    "testing_data/tweets_mock.js"),
    ("instagram",  "testing_data/instagram_posts_mock.json"),
    ("instagram",  "testing_data/instagram_personal_information_mock.json"),
]

_PROJECT_ROOT = Path(__file__).parent.parent


@app.delete("/data")
async def delete_all_data() -> dict[str, int]:
    """Wipe all ingested chunks. Use when switching datasets."""
    async with engine.begin() as conn:
        result = await conn.execute(text("DELETE FROM chunks"))
        return {"deleted": result.rowcount}


@app.post("/seed")
async def seed_demo_data() -> dict:
    """
    Ingest all testing_data/ fixture files in one click.
    Idempotent — re-running skips already-embedded chunks.
    """
    totals: dict[str, int] = {"total_chunks": 0, "inserted": 0, "dupes_skipped": 0}
    results = []
    for source, rel_path in _DEMO_FILES:
        file_path = _PROJECT_ROOT / rel_path
        if not file_path.exists():
            results.append({"file": rel_path, "error": "not found"})
            continue
        adapter = REGISTRY[source]()
        stats = await run_ingestion(adapter.parse(file_path))
        for k in totals:
            totals[k] += stats.get(k, 0)
        results.append({"file": rel_path, "source": source, **stats})
    return {"totals": totals, "files": results}


# ── Chat (SSE) ────────────────────────────────────────────────────────────────

@app.get("/chat")
async def chat(
    q: str,
    source: str | None = None,
    k: int = 8,
) -> StreamingResponse:
    """
    Stream a grounded RAG answer as Server-Sent Events.

    Event types:
      {"type": "token",  "text": "..."}          — partial answer token
      {"type": "done",   "citations": [...]}      — final event with source citations
      {"type": "error",  "text": "..."}           — grounding guardrail or error
    """
    return StreamingResponse(
        _stream_chat(q, source=source, k=k),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_chat(
    question: str,
    source: str | None,
    k: int,
) -> AsyncIterator[str]:
    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    # 1. Embed query (RETRIEVAL_QUERY task type)
    query_vec = await embed_query(question)

    # 2. Retrieve top-k
    chunks = await retrieve(query_vec, k=k, source=source)

    # 3. Grounding guardrail
    if not chunks or chunks[0]["score"] < MIN_RETRIEVAL_SCORE:
        yield sse({
            "type": "error",
            "text": "I don't have enough information about this topic in the provided content.",
        })
        return

    # 4. Build prompt
    prompt = build_prompt(question, chunks)

    # 5. Stream Gemini response
    async for token in stream_gemini(prompt, RAG_SYSTEM):
        yield sse({"type": "token", "text": token})

    # 6. Emit citations from retrieved chunks
    yield sse({"type": "done", "citations": build_citations(chunks)})
