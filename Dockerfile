FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install deps first (layer cache)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Copy source
COPY app/ ./app/
COPY ingestion/ ./ingestion/
COPY kb/ ./kb/
COPY rag/ ./rag/
COPY migrations/ ./migrations/
COPY testing_data/ ./testing_data/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
