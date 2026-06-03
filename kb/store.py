from sqlalchemy import text

from app.db import engine


async def filter_new_hashes(content_hashes: list[str]) -> set[str]:
    """Return subset of hashes not already in the chunks table."""
    if not content_hashes:
        return set()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT content_hash FROM chunks WHERE content_hash = ANY(:hashes)"),
            {"hashes": content_hashes},
        )
        existing = {row[0] for row in result}
    return set(content_hashes) - existing


async def upsert_chunks(rows: list[dict]) -> int:
    """
    Bulk upsert chunks with embeddings.
    ON CONFLICT (content_hash) DO NOTHING — re-runs are idempotent.

    Returns len(rows): the caller (pipeline) guarantees every row is new
    (intra-run dedup + DB pre-filter), so ON CONFLICT is a safety net that
    should not fire. We return len(rows) because asyncpg's executemany
    rowcount is unreliable (-1) when ON CONFLICT is present.
    """
    if not rows:
        return 0
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO chunks (
                    content_hash, source_id, source, content_type, text,
                    authored_at, url, lang, embedding, embedding_model, dim, extra
                ) VALUES (
                    :content_hash, :source_id, :source, :content_type, :text,
                    :authored_at, :url, :lang, CAST(:embedding AS vector),
                    :embedding_model, :dim, CAST(:extra AS jsonb)
                )
                ON CONFLICT (content_hash) DO NOTHING
            """),
            rows,
        )
        return len(rows)
