"""
RAG layer tests.
Unit tests use mocks — no DB or GCP needed.
Integration tests marked @pytest.mark.integration.
"""

import json
import os
from unittest.mock import patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://cortex:cortex@localhost:5433/cortex")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402
from rag.citations import build_citations  # noqa: E402
from rag.prompt import RAG_SYSTEM, build_prompt  # noqa: E402
from rag.retriever import MIN_RETRIEVAL_SCORE  # noqa: E402

_DIM = 768
_FAKE_VEC = [0.1] * _DIM
_FAKE_CHUNKS = [
    {
        "content_hash": "abc123",
        "source": "linkedin",
        "content_type": "post",
        "text": "Remote work is the future of knowledge work and distributed teams.",
        "authored_at": None,
        "url": "https://linkedin.com/posts/123",
        "score": 0.92,
    }
]


# ── Prompt builder ────────────────────────────────────────────────────────────

def test_build_prompt_includes_question() -> None:
    prompt = build_prompt("What do you think about remote work?", _FAKE_CHUNKS)
    assert "remote work" in prompt.lower()


def test_build_prompt_includes_chunk_text() -> None:
    prompt = build_prompt("remote work?", _FAKE_CHUNKS)
    assert "Remote work is the future" in prompt


def test_build_prompt_includes_source_label() -> None:
    prompt = build_prompt("q?", _FAKE_CHUNKS)
    assert "linkedin" in prompt


def test_rag_system_prompt_has_grounding_rules() -> None:
    assert "ONLY" in RAG_SYSTEM or "only" in RAG_SYSTEM
    assert "don't have enough information" in RAG_SYSTEM.lower() or "not" in RAG_SYSTEM.lower()


# ── Citations ─────────────────────────────────────────────────────────────────

def test_build_citations_structure() -> None:
    citations = build_citations(_FAKE_CHUNKS)
    assert len(citations) == 1
    c = citations[0]
    assert c["source"] == "linkedin"
    assert c["content_type"] == "post"
    assert c["url"] == "https://linkedin.com/posts/123"
    assert "Remote work" in c["snippet"]


def test_build_citations_snippet_truncated() -> None:
    long_chunk = dict(_FAKE_CHUNKS[0], text="x" * 300)
    citations = build_citations([long_chunk])
    assert len(citations[0]["snippet"]) <= 150


def test_build_citations_empty_input() -> None:
    assert build_citations([]) == []


# ── /chat endpoint (mocked) ───────────────────────────────────────────────────

async def _collect_sse(response) -> list[dict]:
    events = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


@pytest.mark.integration
async def test_chat_returns_sse_stream() -> None:
    """Mocks embed_query + retrieve + stream_gemini — no GCP needed, needs DB."""
    async def fake_embed(q: str) -> list[float]:
        return _FAKE_VEC

    async def fake_retrieve(vec, k=8, source=None, content_type=None):
        return _FAKE_CHUNKS

    async def fake_stream(prompt, system):
        yield "Remote work "
        yield "is great."

    with (
        patch("app.main.embed_query", side_effect=fake_embed),
        patch("app.main.retrieve", side_effect=fake_retrieve),
        patch("app.main.stream_gemini", side_effect=fake_stream),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("GET", "/chat", params={"q": "remote work"}) as r:
                assert r.status_code == 200
                events = await _collect_sse(r)

    token_events = [e for e in events if e["type"] == "token"]
    done_events = [e for e in events if e["type"] == "done"]
    assert len(token_events) >= 1
    assert len(done_events) == 1
    assert "citations" in done_events[0]


@pytest.mark.integration
async def test_chat_guardrail_on_low_score() -> None:
    """Grounding guardrail fires when top chunk score is below threshold."""
    low_score_chunks = [dict(_FAKE_CHUNKS[0], score=MIN_RETRIEVAL_SCORE - 0.1)]

    async def fake_embed(q: str) -> list[float]:
        return _FAKE_VEC

    async def fake_retrieve(vec, k=8, source=None, content_type=None):
        return low_score_chunks

    with (
        patch("app.main.embed_query", side_effect=fake_embed),
        patch("app.main.retrieve", side_effect=fake_retrieve),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("GET", "/chat", params={"q": "unknowable topic"}) as r:
                events = await _collect_sse(r)

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "don't have enough information" in error_events[0]["text"].lower()


@pytest.mark.integration
async def test_ingest_endpoint_rejects_unknown_source() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/ingest",
            data={"source": "nonexistent"},
            files={"file": ("test.zip", b"fake", "application/zip")},
        )
    assert r.status_code == 400
