import tiktoken

from app.models import Chunk, ContentItem
from ingestion.normalizer import content_hash

_ENCODER = tiktoken.get_encoding("cl100k_base")
_MAX_TOKENS = 512
_OVERLAP_TOKENS = 50

# These content types represent atomic thoughts — never split, even if long.
_ATOMIC_TYPES = frozenset({"post", "comment", "bio", "profile"})


def chunk_item(item: ContentItem) -> list[Chunk]:
    """Produce Chunk list from a ContentItem using content-type-aware strategy."""
    if item.content_type in _ATOMIC_TYPES:
        return [_make_chunk(item, item.text, 0, 1)]
    if item.content_type == "article":
        return _chunk_article(item)
    return [_make_chunk(item, item.text, 0, 1)]


def _chunk_article(item: ContentItem) -> list[Chunk]:
    segments = _recursive_split(item.text)
    total = len(segments)
    return [_make_chunk(item, seg, i, total) for i, seg in enumerate(segments)]


def _recursive_split(text: str) -> list[str]:
    tokens = _ENCODER.encode(text)
    if len(tokens) <= _MAX_TOKENS:
        return [text]

    # 1. Try paragraph boundaries
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return _merge_segments(paragraphs)

    # 2. Try sentence boundaries
    sentences = [s.strip() for s in text.replace(". ", ".\n").split("\n") if s.strip()]
    if len(sentences) > 1:
        return _merge_segments(sentences)

    # 3. Fixed token windows with overlap (last resort)
    return _fixed_split(tokens)


def _merge_segments(segments: list[str]) -> list[str]:
    """Greedily merge segments up to MAX_TOKENS; carry last segment as overlap."""
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for seg in segments:
        seg_tokens = len(_ENCODER.encode(seg))
        if current_tokens + seg_tokens > _MAX_TOKENS and current:
            chunks.append(" ".join(current))
            # overlap: keep the last segment as context
            current = [current[-1]]
            current_tokens = len(_ENCODER.encode(current[0]))
        current.append(seg)
        current_tokens += seg_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks


def _fixed_split(tokens: list[int]) -> list[str]:
    """Token-window split with OVERLAP_TOKENS overlap."""
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + _MAX_TOKENS, len(tokens))
        chunks.append(_ENCODER.decode(tokens[start:end]))
        if end == len(tokens):
            break
        start = end - _OVERLAP_TOKENS
    return chunks


def _make_chunk(item: ContentItem, text: str, index: int, total: int) -> Chunk:
    return Chunk(
        content_hash=content_hash(text),
        source_id=item.source_id,
        source=item.source,
        content_type=item.content_type,
        text=text,
        authored_at=item.authored_at,
        url=item.url,
        lang=item.lang,
        chunk_index=index,
        total_chunks=total,
        extra={"chunk_index": index, "total_chunks": total},
    )
