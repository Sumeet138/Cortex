from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ContentItem:
    source_id: str
    source: str          # linkedin | twitter | instagram
    content_type: str    # post | comment | article | bio | profile
    text: str
    authored_at: datetime | None
    url: str | None
    lang: str
    raw: dict


@dataclass
class Chunk:
    content_hash: str    # sha256(text.lower()) — idempotency key
    source_id: str
    source: str
    content_type: str
    text: str
    authored_at: datetime | None
    url: str | None
    lang: str
    chunk_index: int
    total_chunks: int
    extra: dict = field(default_factory=dict)
