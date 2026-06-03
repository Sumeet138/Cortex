import io
import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import ijson

from app.models import ContentItem
from ingestion.base import SourceAdapter, register
from ingestion.normalizer import detect_language, normalize_text


@register("instagram")
class InstagramAdapter(SourceAdapter):
    def parse(self, file: Path) -> Iterator[ContentItem]:
        if file.suffix.lower() == ".zip":
            with zipfile.ZipFile(file) as zf:
                yield from _parse_zip(zf)
        elif file.is_dir():
            yield from _parse_directory(file)
        elif file.suffix.lower() == ".json":
            yield from _parse_json_file(file)


def _parse_zip(zf: zipfile.ZipFile) -> Iterator[ContentItem]:
    names = zf.namelist()
    for name in names:
        lower = name.lower()
        if "posts_" in lower and lower.endswith(".json"):
            with zf.open(name) as f:
                yield from _stream_posts(f)
        elif "personal_information.json" in lower or "profile_information.json" in lower:
            with zf.open(name) as f:
                yield from _parse_profile(f)


def _parse_directory(directory: Path) -> Iterator[ContentItem]:
    content_dir = directory / "content"
    if content_dir.exists():
        for posts_file in sorted(content_dir.glob("posts_*.json")):
            with posts_file.open("rb") as f:
                yield from _stream_posts(f)
    for profile_path in (
        directory / "personal_information" / "personal_information.json",
        directory / "account_information" / "profile_information.json",
    ):
        if profile_path.exists():
            with profile_path.open("rb") as f:
                yield from _parse_profile(f)
            break


def _parse_json_file(path: Path) -> Iterator[ContentItem]:
    """Parse a single uploaded JSON file, sniffing posts vs profile.

    Posts exports are a JSON array (starts with '['); the profile export is a
    JSON object (starts with '{'). Filename is unreliable after temp storage.
    """
    with path.open("rb") as f:
        head = f.read(256).lstrip()
    if head.startswith(b"["):
        with path.open("rb") as f:
            yield from _stream_posts(f)
    else:
        with path.open("rb") as f:
            yield from _parse_profile(f)


def _stream_posts(f: io.RawIOBase) -> Iterator[ContentItem]:
    for post in ijson.items(f, "item"):
        for media in post.get("media", [post]):
            caption = media.get("title", "").strip()
            if not caption:
                continue
            text = normalize_text(caption)
            ts = media.get("creation_timestamp", 0)
            uri = media.get("uri", "")
            yield ContentItem(
                source_id=uri.split("/")[-1] if uri else text[:32],
                source="instagram",
                content_type="post",
                text=text,
                authored_at=datetime.fromtimestamp(ts, tz=UTC) if ts else None,
                url=None,
                lang=detect_language(text),
                raw={"uri": uri, "creation_timestamp": ts, "title": caption},
            )


def _parse_profile(f: io.RawIOBase) -> Iterator[ContentItem]:
    try:
        data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    profile_user = data.get("profile_user", [{}])
    if isinstance(profile_user, list):
        profile_user = profile_user[0] if profile_user else {}
    bio = profile_user.get("string_map_data", {}).get("Bio", {}).get("value", "").strip()
    if not bio:
        return
    text = normalize_text(bio)
    yield ContentItem(
        source_id="ig_bio",
        source="instagram",
        content_type="bio",
        text=text,
        authored_at=None,
        url=None,
        lang=detect_language(text),
        raw={"bio": bio},
    )
