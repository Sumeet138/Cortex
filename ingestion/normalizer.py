import hashlib
import html
import re
import unicodedata


def normalize_text(text: str) -> str:
    """Decode HTML entities, NFKC-normalize unicode, collapse whitespace."""
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def content_hash(normalized_text: str) -> str:
    """SHA-256 of lowercased normalized text — idempotency key for upserts."""
    return hashlib.sha256(normalized_text.lower().encode()).hexdigest()


def detect_language(text: str) -> str:
    """Best-effort language detection; returns '' on short text or failure."""
    if len(text) < 15:
        return ""
    try:
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0
        return detect(text)
    except Exception:
        return ""
