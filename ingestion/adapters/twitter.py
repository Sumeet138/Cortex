import io
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import ijson

from app.models import ContentItem
from ingestion.base import SourceAdapter, register
from ingestion.normalizer import normalize_text


@register("twitter")
class TwitterAdapter(SourceAdapter):
    def parse(self, file: Path) -> Iterator[ContentItem]:
        if file.suffix.lower() == ".zip":
            with zipfile.ZipFile(file) as zf:
                yield from _parse_zip(zf)
        elif file.is_dir():
            yield from _parse_directory(file)
        elif file.suffix.lower() == ".js":
            with file.open("rb") as f:
                yield from _stream_tweet_js(f)


def _parse_zip(zf: zipfile.ZipFile) -> Iterator[ContentItem]:
    names = sorted(n for n in zf.namelist() if "tweet" in n.lower() and n.endswith(".js"))
    for name in names:
        with zf.open(name) as f:
            yield from _stream_tweet_js(f)


def _parse_directory(directory: Path) -> Iterator[ContentItem]:
    data_dir = directory / "data"
    search_dir = data_dir if data_dir.exists() else directory
    for js_file in sorted(search_dir.glob("tweet*.js")):
        with js_file.open("rb") as f:
            yield from _stream_tweet_js(f)


def _stream_tweet_js(f: io.RawIOBase) -> Iterator[ContentItem]:
    """Strip JS assignment prefix (window.YTD.tweet.partN = ) then stream-parse JSON array."""
    raw = f.read()
    bracket = raw.find(b"[")
    end = raw.rfind(b"]")
    if bracket == -1 or end == -1 or end < bracket:
        return
    # Slice to the matching closing bracket so a trailing ';' (real export
    # format: `window.YTD.tweets.part0 = [...];`) doesn't break ijson.
    for item in ijson.items(io.BytesIO(raw[bracket : end + 1]), "item"):
        tweet = item.get("tweet", item)
        text = tweet.get("full_text", "").strip()
        if not text or text.startswith("RT @"):
            continue
        text = normalize_text(text)
        tweet_id = tweet.get("id_str", "")
        yield ContentItem(
            source_id=tweet_id,
            source="twitter",
            content_type="post",
            text=text,
            authored_at=_parse_twitter_date(tweet.get("created_at", "")),
            url=f"https://twitter.com/i/web/status/{tweet_id}" if tweet_id else None,
            lang=tweet.get("lang", ""),
            raw={k: v for k, v in tweet.items() if k not in ("entities", "extended_entities")},
        )


def _parse_twitter_date(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=UTC)
    except ValueError:
        return None
