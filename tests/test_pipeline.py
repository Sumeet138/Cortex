"""
Pipeline integration tests — requires running Postgres (docker compose up -d).
Uses mock embedder: no Vertex AI / GCP credentials needed.
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://cortex:cortex@localhost:5433/cortex")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

from sqlalchemy import text  # noqa: E402

from app.db import engine, run_migrations  # noqa: E402
from app.models import ContentItem  # noqa: E402
from app.settings import settings  # noqa: E402
from ingestion.adapters.linkedin import LinkedInAdapter  # noqa: E402
from kb.embedder import Embedder  # noqa: E402
from kb.pipeline import run_ingestion  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


class MockEmbedder(Embedder):
    """Deterministic fake embedder — returns zero vectors. No GCP required."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * settings.vertex_embedding_dim for _ in texts]


@pytest.fixture(scope="session")
async def db_ready():
    """Run migrations once for the session."""
    await run_migrations()
    yield
    # Clean up test rows
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM chunks WHERE source_id LIKE 'test-%' OR source='linkedin'")
        )


async def _clean_linkedin() -> None:
    """Remove linkedin rows so a test starts from a known-empty slate.

    The session-scoped DB is shared across tests, so each DB test that asserts
    on insert/dupe counts must isolate itself rather than rely on ordering.
    """
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM chunks WHERE source='linkedin'"))


@pytest.mark.integration
async def test_pipeline_inserts_chunks(db_ready: None) -> None:
    await _clean_linkedin()
    items = list(LinkedInAdapter().parse(FIXTURES / "linkedin"))
    stats = await run_ingestion(iter(items), embedder=MockEmbedder())

    assert stats["total_chunks"] > 0
    assert stats["inserted"] > 0
    assert stats["dupes_skipped"] == 0


@pytest.mark.integration
async def test_pipeline_deduplicates_on_rerun(db_ready: None) -> None:
    await _clean_linkedin()
    items = list(LinkedInAdapter().parse(FIXTURES / "linkedin"))

    # First run — inserts
    stats1 = await run_ingestion(iter(items), embedder=MockEmbedder())
    # Second run — all dupes
    stats2 = await run_ingestion(iter(items), embedder=MockEmbedder())

    assert stats1["inserted"] > 0
    assert stats2["inserted"] == 0
    assert stats2["dupes_skipped"] == stats1["inserted"]


@pytest.mark.integration
async def test_pipeline_rows_have_correct_metadata(db_ready: None) -> None:
    # Self-contained: ensure linkedin rows exist before reading one.
    await _clean_linkedin()
    items = list(LinkedInAdapter().parse(FIXTURES / "linkedin"))
    await run_ingestion(iter(items), embedder=MockEmbedder())

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT source, content_type, embedding_model, dim "
                "FROM chunks WHERE source='linkedin' LIMIT 1"
            )
        )
        row = result.fetchone()

    assert row is not None
    assert row[0] == "linkedin"
    assert row[2] == settings.vertex_embedding_model
    assert row[3] == settings.vertex_embedding_dim


@pytest.mark.integration
async def test_pipeline_filters_noise() -> None:
    """Items that fail is_authored_content are never inserted."""
    noise = ContentItem(
        source_id="noise-1",
        source="linkedin",
        content_type="like",  # noise type
        text="some liked content",
        authored_at=None,
        url=None,
        lang="en",
        raw={},
    )
    stats = await run_ingestion(iter([noise]), embedder=MockEmbedder())
    assert stats["total_chunks"] == 0
    assert stats["inserted"] == 0
