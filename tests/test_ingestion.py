"""Parser tests — TDD required for ingestion layer per workflow.md."""

import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://cortex:cortex@localhost:5433/cortex")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

from app.models import ContentItem  # noqa: E402
from ingestion.adapters.instagram import InstagramAdapter  # noqa: E402
from ingestion.adapters.linkedin import LinkedInAdapter  # noqa: E402
from ingestion.adapters.twitter import TwitterAdapter  # noqa: E402
from ingestion.filter import is_authored_content  # noqa: E402
from ingestion.normalizer import content_hash, normalize_text  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


# ── LinkedIn ──────────────────────────────────────────────────────────────────

def test_linkedin_yields_authored_posts() -> None:
    items = list(LinkedInAdapter().parse(FIXTURES / "linkedin"))
    posts = [i for i in items if i.content_type == "post"]
    assert len(posts) == 2  # fixture has 2 posts with commentary, 1 reshare (dropped)
    assert all(isinstance(i, ContentItem) for i in posts)
    assert all(i.source == "linkedin" for i in posts)
    assert all(i.text for i in posts)


def test_linkedin_drops_reshares_without_commentary() -> None:
    items = list(LinkedInAdapter().parse(FIXTURES / "linkedin"))
    assert all(i.text.strip() for i in items)  # no empty-text items


def test_linkedin_yields_articles() -> None:
    items = list(LinkedInAdapter().parse(FIXTURES / "linkedin"))
    articles = [i for i in items if i.content_type == "article"]
    assert len(articles) == 1
    assert articles[0].source == "linkedin"
    assert "Remote work" in articles[0].text


def test_linkedin_url_field_present() -> None:
    items = list(LinkedInAdapter().parse(FIXTURES / "linkedin"))
    assert all(hasattr(i, "url") for i in items)  # url may be None but field exists


def test_linkedin_raw_preserved() -> None:
    items = list(LinkedInAdapter().parse(FIXTURES / "linkedin"))
    assert all(isinstance(i.raw, dict) for i in items)


# ── Twitter ───────────────────────────────────────────────────────────────────

def test_twitter_yields_original_tweets() -> None:
    items = list(TwitterAdapter().parse(FIXTURES / "twitter" / "tweet.js"))
    assert len(items) == 2  # fixture has 3 tweets, 1 retweet dropped
    assert all(i.source == "twitter" for i in items)
    assert all(i.content_type == "post" for i in items)


def test_twitter_drops_retweets() -> None:
    items = list(TwitterAdapter().parse(FIXTURES / "twitter" / "tweet.js"))
    assert not any(i.text.startswith("RT @") for i in items)


def test_twitter_parses_dates() -> None:
    items = list(TwitterAdapter().parse(FIXTURES / "twitter" / "tweet.js"))
    assert all(i.authored_at is not None for i in items)


def test_twitter_sets_url() -> None:
    items = list(TwitterAdapter().parse(FIXTURES / "twitter" / "tweet.js"))
    assert all(i.url and "twitter.com" in i.url for i in items)


def test_twitter_preserves_lang() -> None:
    items = list(TwitterAdapter().parse(FIXTURES / "twitter" / "tweet.js"))
    assert all(i.lang == "en" for i in items)


# ── Instagram ─────────────────────────────────────────────────────────────────

def test_instagram_yields_posts_with_captions() -> None:
    items = list(InstagramAdapter().parse(FIXTURES / "instagram"))
    posts = [i for i in items if i.content_type == "post"]
    assert len(posts) == 2  # fixture has 3 media, 1 with empty caption (dropped)
    assert all(i.source == "instagram" for i in posts)
    assert all(i.text for i in posts)


def test_instagram_drops_empty_captions() -> None:
    items = list(InstagramAdapter().parse(FIXTURES / "instagram"))
    assert not any(i.text == "" for i in items)


def test_instagram_yields_bio() -> None:
    items = list(InstagramAdapter().parse(FIXTURES / "instagram"))
    bios = [i for i in items if i.content_type == "bio"]
    assert len(bios) == 1
    assert bios[0].source_id == "ig_bio"
    assert "Builder" in bios[0].text


def test_instagram_post_has_timestamp() -> None:
    items = list(InstagramAdapter().parse(FIXTURES / "instagram"))
    posts = [i for i in items if i.content_type == "post"]
    assert all(i.authored_at is not None for i in posts)


# ── Noise filter ──────────────────────────────────────────────────────────────

def test_filter_passes_authored_post() -> None:
    item = ContentItem(
        source_id="1", source="linkedin", content_type="post",
        text="Real authored content", authored_at=None, url=None, lang="en", raw={},
    )
    assert is_authored_content(item) is True


def test_filter_blocks_empty_text() -> None:
    item = ContentItem(
        source_id="2", source="linkedin", content_type="post",
        text="   ", authored_at=None, url=None, lang="en", raw={},
    )
    assert is_authored_content(item) is False


def test_filter_blocks_retweet() -> None:
    item = ContentItem(
        source_id="3", source="twitter", content_type="post",
        text="RT @someone: cool post here", authored_at=None, url=None, lang="en", raw={},
    )
    assert is_authored_content(item) is False


def test_filter_blocks_noise_content_types() -> None:
    for noise_type in ("like", "save", "ad", "notification", "connection"):
        item = ContentItem(
            source_id="4", source="linkedin", content_type=noise_type,
            text="some text", authored_at=None, url=None, lang="en", raw={},
        )
        assert is_authored_content(item) is False, f"Expected False for type={noise_type}"


def test_filter_passes_all_authored_types() -> None:
    for authored_type in ("post", "comment", "article", "bio", "profile"):
        item = ContentItem(
            source_id="5", source="linkedin", content_type=authored_type,
            text="authored content", authored_at=None, url=None, lang="en", raw={},
        )
        assert is_authored_content(item) is True, f"Expected True for type={authored_type}"


# ── Normalizer ────────────────────────────────────────────────────────────────

def test_normalizer_decodes_html_entities() -> None:
    assert normalize_text("Hello &amp; world &lt;3") == "Hello & world <3"


def test_normalizer_collapses_whitespace() -> None:
    assert normalize_text("hello   world\n\tnext line") == "hello world next line"


def test_normalizer_strips_edges() -> None:
    assert normalize_text("  hello  ") == "hello"


def test_content_hash_is_deterministic() -> None:
    assert content_hash("Hello World") == content_hash("Hello World")


def test_content_hash_case_insensitive() -> None:
    assert content_hash("Hello World") == content_hash("hello world")


def test_content_hash_returns_hex_string() -> None:
    h = content_hash("test")
    assert len(h) == 64  # SHA-256 hex = 64 chars
    assert all(c in "0123456789abcdef" for c in h)
