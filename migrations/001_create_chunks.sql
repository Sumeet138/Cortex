CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash    TEXT NOT NULL UNIQUE,
    source_id       TEXT NOT NULL,
    source          TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    text            TEXT NOT NULL,
    authored_at     TIMESTAMPTZ,
    url             TEXT,
    lang            TEXT,
    embedding       vector(768),
    embedding_model TEXT NOT NULL DEFAULT 'text-embedding-005',
    dim             INTEGER NOT NULL DEFAULT 768,
    extra           JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS chunks_source_idx ON chunks (source);
CREATE INDEX IF NOT EXISTS chunks_authored_at_idx ON chunks (authored_at);
