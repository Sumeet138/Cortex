"""Unit tests for content-type-aware chunker — no DB or GCP required."""

import os
from datetime import UTC, datetime

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://cortex:cortex@localhost:5433/cortex")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

from app.models import Chunk, ContentItem  # noqa: E402
from kb.chunker import _ENCODER, _MAX_TOKENS, chunk_item  # noqa: E402


def _item(content_type: str, text: str) -> ContentItem:
    return ContentItem(
        source_id="test-id",
        source="linkedin",
        content_type=content_type,
        text=text,
        authored_at=datetime(2024, 1, 1, tzinfo=UTC),
        url=None,
        lang="en",
        raw={},
    )


SHORT_TEXT = "Remote work is the future of knowledge work."
_SENTENCE = "Remote work has fundamentally transformed how we think about productivity. "
LONG_TEXT = (_SENTENCE * 60).strip()


def test_post_is_always_single_chunk() -> None:
    chunks = chunk_item(_item("post", LONG_TEXT))
    assert len(chunks) == 1


def test_comment_is_always_single_chunk() -> None:
    chunks = chunk_item(_item("comment", LONG_TEXT))
    assert len(chunks) == 1


def test_bio_is_always_single_chunk() -> None:
    chunks = chunk_item(_item("bio", LONG_TEXT))
    assert len(chunks) == 1


def test_short_article_is_single_chunk() -> None:
    chunks = chunk_item(_item("article", SHORT_TEXT))
    assert len(chunks) == 1


def test_long_article_is_split() -> None:
    chunks = chunk_item(_item("article", LONG_TEXT))
    assert len(chunks) > 1


def test_chunk_tokens_within_budget() -> None:
    chunks = chunk_item(_item("article", LONG_TEXT))
    for chunk in chunks:
        token_count = len(_ENCODER.encode(chunk.text))
        assert token_count <= _MAX_TOKENS, f"Chunk exceeds budget: {token_count} tokens"


def test_chunk_fields_match_item() -> None:
    item = _item("post", SHORT_TEXT)
    chunks = chunk_item(item)
    for chunk in chunks:
        assert isinstance(chunk, Chunk)
        assert chunk.source == item.source
        assert chunk.source_id == item.source_id
        assert chunk.content_type == item.content_type
        assert chunk.authored_at == item.authored_at


def test_chunk_has_content_hash() -> None:
    chunks = chunk_item(_item("post", SHORT_TEXT))
    assert len(chunks[0].content_hash) == 64  # SHA-256 hex
    assert all(c in "0123456789abcdef" for c in chunks[0].content_hash)


def test_chunk_index_and_total() -> None:
    chunks = chunk_item(_item("article", LONG_TEXT))
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert chunk.total_chunks == len(chunks)


def test_same_text_same_hash() -> None:
    c1 = chunk_item(_item("post", SHORT_TEXT))[0]
    c2 = chunk_item(_item("post", SHORT_TEXT))[0]
    assert c1.content_hash == c2.content_hash


def test_different_text_different_hash() -> None:
    c1 = chunk_item(_item("post", "text one"))[0]
    c2 = chunk_item(_item("post", "text two"))[0]
    assert c1.content_hash != c2.content_hash


def test_article_chunks_cover_original_words() -> None:
    """All unique words from the original should appear across chunks."""
    text = "Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa. " * 40
    chunks = chunk_item(_item("article", text))
    combined = " ".join(c.text for c in chunks)
    for word in ["Alpha", "Gamma", "Kappa"]:
        assert word in combined
