"""Unit tests for core contracts — no DB or GCP required."""

import os
from datetime import UTC, datetime

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://cortex:cortex@localhost:5433/cortex")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

from app.models import ContentItem  # noqa: E402
from ingestion.base import REGISTRY, SourceAdapter, register  # noqa: E402
from kb.embedder import Embedder, VertexEmbedder  # noqa: E402


def test_content_item_fields() -> None:
    item = ContentItem(
        source_id="123",
        source="linkedin",
        content_type="post",
        text="Hello world",
        authored_at=datetime(2024, 1, 1, tzinfo=UTC),
        url="https://linkedin.com/posts/123",
        lang="en",
        raw={"original": "data"},
    )
    assert item.source_id == "123"
    assert item.source == "linkedin"
    assert item.content_type == "post"
    assert item.text == "Hello world"
    assert item.lang == "en"
    assert isinstance(item.raw, dict)


def test_content_item_optional_fields() -> None:
    item = ContentItem(
        source_id="456",
        source="twitter",
        content_type="post",
        text="Tweet text",
        authored_at=None,
        url=None,
        lang="en",
        raw={},
    )
    assert item.authored_at is None
    assert item.url is None


def test_source_adapter_registry() -> None:
    from collections.abc import Iterator
    from pathlib import Path

    @register("test_source")
    class TestAdapter(SourceAdapter):
        def parse(self, file: Path) -> Iterator[ContentItem]:
            return iter([])

    assert "test_source" in REGISTRY
    assert REGISTRY["test_source"] is TestAdapter
    del REGISTRY["test_source"]


def test_vertex_embedder_is_embedder() -> None:
    emb = VertexEmbedder(
        model="text-embedding-005",
        dim=768,
        project="test-project",
        location="us-central1",
    )
    assert isinstance(emb, Embedder)
    assert emb.model == "text-embedding-005"
    assert emb.dim == 768


def test_embedder_abc_cannot_be_instantiated_directly() -> None:
    """Embedder is abstract — subclasses must implement embed_batch."""

    class IncompleteEmbedder(Embedder):
        pass  # no embed_batch

    try:
        IncompleteEmbedder()
        raise AssertionError("Should have raised TypeError")
    except TypeError:
        pass  # expected — abstract method not implemented
