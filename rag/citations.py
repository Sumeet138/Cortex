from datetime import datetime


def build_citations(chunks: list[dict]) -> list[dict]:
    """
    Build citation objects from retrieved chunks.
    Returns top chunks as citations — these ARE the grounding, regardless of
    which specific ones Gemini chose to reference.
    """
    citations = []
    for chunk in chunks:
        authored_at = chunk.get("authored_at")
        date_str = None
        if authored_at:
            if isinstance(authored_at, datetime):
                date_str = authored_at.strftime("%Y-%m-%d")
            else:
                date_str = str(authored_at)[:10]
        citations.append(
            {
                "source": chunk.get("source"),
                "content_type": chunk.get("content_type"),
                "authored_at": date_str,
                "url": chunk.get("url"),
                "snippet": chunk.get("text", "")[:150],
            }
        )
    return citations
