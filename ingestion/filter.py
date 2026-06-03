from app.models import ContentItem

_AUTHORED_TYPES = frozenset({"post", "comment", "article", "bio", "profile"})


def is_authored_content(item: ContentItem) -> bool:
    """Return True only for content that represents the person's authored words."""
    if item.content_type not in _AUTHORED_TYPES:
        return False
    if not item.text.strip():
        return False
    # SIM103: keep explicit for readability — multi-condition return is less clear inlined
    if item.source == "twitter" and item.text.startswith("RT @"):  # noqa: SIM103
        return False
    return True
