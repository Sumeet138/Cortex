from sqlalchemy import text

from app.db import engine
from app.settings import settings
from kb.embedder import VertexEmbedder

MIN_RETRIEVAL_SCORE = 0.30  # below this → "not enough data"


async def embed_query(question: str) -> list[float]:
    """Embed a query with RETRIEVAL_QUERY task type for better recall."""
    embedder = VertexEmbedder(
        model=settings.vertex_embedding_model,
        dim=settings.vertex_embedding_dim,
        project=settings.google_cloud_project,
        location=settings.vertex_location,
    )
    return await embedder.embed_one_query(question)


async def retrieve(
    query_embedding: list[float],
    k: int = 8,
    source: str | None = None,
    content_type: str | None = None,
) -> list[dict]:
    """
    Return top-k chunks by cosine similarity.
    Optional source / content_type filters applied in SQL.
    Score = 1 - cosine_distance (1.0 = identical, 0.0 = orthogonal).
    """
    vec_str = "[" + ",".join(f"{x:.8f}" for x in query_embedding) + "]"
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    content_hash,
                    source,
                    content_type,
                    text,
                    authored_at,
                    url,
                    1 - (embedding <=> CAST(:vec AS vector)) AS score
                FROM chunks
                WHERE embedding IS NOT NULL
                  AND (CAST(:src AS text) IS NULL OR source = :src)
                  AND (CAST(:ctype AS text) IS NULL OR content_type = :ctype)
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :k
            """),
            {"vec": vec_str, "src": source, "ctype": content_type, "k": k},
        )
        rows = result.mappings().all()

    return [dict(row) for row in rows]
