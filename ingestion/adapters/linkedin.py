import csv
import io
import zipfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from app.models import ContentItem
from ingestion.base import SourceAdapter, register
from ingestion.normalizer import detect_language, normalize_text


@register("linkedin")
class LinkedInAdapter(SourceAdapter):
    def parse(self, file: Path) -> Iterator[ContentItem]:
        if file.suffix.lower() == ".zip":
            with zipfile.ZipFile(file) as zf:
                yield from _parse_zip(zf)
        elif file.is_dir():
            yield from _parse_directory(file)
        elif file.suffix.lower() == ".csv":
            yield from _parse_csv_file(file)


def _parse_zip(zf: zipfile.ZipFile) -> Iterator[ContentItem]:
    for name in zf.namelist():
        lower = name.lower()
        if "shares" in lower and lower.endswith(".csv"):
            with zf.open(name) as raw:
                yield from _parse_shares(io.TextIOWrapper(raw, encoding="utf-8-sig"))
        elif "articles" in lower and lower.endswith(".csv"):
            with zf.open(name) as raw:
                yield from _parse_articles(io.TextIOWrapper(raw, encoding="utf-8-sig"))


def _parse_directory(directory: Path) -> Iterator[ContentItem]:
    for csv_file in directory.glob("*.csv"):
        stem = csv_file.stem.lower()
        if "shares" in stem:
            with csv_file.open(encoding="utf-8-sig") as f:
                yield from _parse_shares(f)
        elif "articles" in stem:
            with csv_file.open(encoding="utf-8-sig") as f:
                yield from _parse_articles(f)


def _parse_csv_file(path: Path) -> Iterator[ContentItem]:
    """Parse a single uploaded CSV, dispatching on header columns.

    The /ingest endpoint stores uploads under a random temp name, so we sniff
    the header row instead of relying on the filename.
    """
    with path.open(encoding="utf-8-sig") as f:
        header = f.readline()
        f.seek(0)
        if "ShareCommentary" in header:
            yield from _parse_shares(f)
        elif "Content" in header or "Title" in header:
            yield from _parse_articles(f)


def _parse_shares(f: io.TextIOWrapper) -> Iterator[ContentItem]:
    for row in csv.DictReader(f):
        text = row.get("ShareCommentary", "").strip()
        if not text:
            continue  # reshare with no authored commentary — noise
        text = normalize_text(text)
        yield ContentItem(
            source_id=_url_id(row.get("ShareLink", "")) or text[:32],
            source="linkedin",
            content_type="post",
            text=text,
            authored_at=_parse_date(row.get("Date", "")),
            url=row.get("ShareLink") or None,
            lang=detect_language(text),
            raw=dict(row),
        )


def _parse_articles(f: io.TextIOWrapper) -> Iterator[ContentItem]:
    for row in csv.DictReader(f):
        content = row.get("Content", "").strip()
        title = row.get("Title", "").strip()
        text = normalize_text(content or title)
        if not text:
            continue
        yield ContentItem(
            source_id=_url_id(row.get("Url", "")) or title[:32],
            source="linkedin",
            content_type="article",
            text=text,
            authored_at=_parse_date(row.get("PublishedAt", "")),
            url=row.get("Url") or None,
            lang=detect_language(text),
            raw=dict(row),
        )


def _url_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1] if url else ""


def _parse_date(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None
