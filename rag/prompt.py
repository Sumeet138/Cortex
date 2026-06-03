from datetime import datetime

RAG_SYSTEM = """You are a knowledgeable assistant analyzing a specific person's authored content.
Answer the user's question based ONLY on the provided content excerpts.

Rules:
- Use only information present in the excerpts below.
- If the excerpts do not contain enough information, respond exactly:
  "I don't have enough information about this topic in the provided content."
- Be concise and direct.
- Do not invent facts or infer beyond what is written."""

RAG_USER_TMPL = """Content excerpts:
{context}

Question: {question}"""


def build_prompt(question: str, chunks: list[dict]) -> str:
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", "unknown")
        ctype = chunk.get("content_type", "")
        authored_at = chunk.get("authored_at")
        date_str = ""
        if authored_at:
            if isinstance(authored_at, datetime):
                date_str = authored_at.strftime("%Y-%m-%d")
            else:
                date_str = str(authored_at)[:10]
        label = f"[{i}] ({source} {ctype}, {date_str})" if date_str else f"[{i}] ({source} {ctype})"
        context_parts.append(f'{label}\n"{chunk["text"]}"')

    context = "\n\n".join(context_parts)
    return RAG_USER_TMPL.format(context=context, question=question)
