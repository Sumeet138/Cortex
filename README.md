# Cortex

Ingest your LinkedIn, Twitter, and Instagram exports. Ask questions. Get answers grounded in your own content.

**Live demo:** https://cortex.areysumeetji.dev  
**Backend:** Cloud Run — https://cortex-api-1251588617.us-central1.run.app/health

---

## What it does

Cortex is a three-layer system:

1. **Ingestion** — stream-parse social exports (LinkedIn CSV, Twitter tweets.js, Instagram JSON), extract only authored content (posts, articles, profile bio), discard reshares/likes/ads, normalize to a canonical `ContentItem` schema.
2. **Vector KB** — chunk content, embed via Vertex AI `text-embedding-005` (768d), deduplicate by content hash, upsert into pgvector with metadata for source filtering.
3. **RAG chat** — embed query, retrieve top-k by cosine similarity, enforce a grounding guardrail (score < 0.30 → refuse), build prompt with citations, stream Gemini response as SSE.

---

## Architecture decisions

**1. Adapter registry pattern for ingestion.**
Each source (LinkedIn, Twitter, Instagram) is a `SourceAdapter` subclass registered by key. The main pipeline only knows `parse(path) → Iterator[ContentItem]`. Adding a fourth source means writing one new file and registering it — nothing else changes. File-type sniffing (CSV headers, JSON structure) happens inside the adapter, so the API accepts bare files without requiring the user to rename them.

**2. pgvector over a dedicated vector DB.**
A separate vector store (Pinecone, Qdrant) adds an extra network hop, another service to auth, and a second schema to maintain. pgvector keeps vectors and metadata in one place, allows SQL `WHERE source = 'linkedin'` filters at retrieval time without a post-filter pass, and transitions from Docker locally to Cloud SQL in prod with only a connection string change. The tradeoff: pgvector HNSW index builds are slower than Pinecone's managed index at large scale, but at 10k–100k chunks the difference is irrelevant.

**3. Real async concurrency in the embedding pipeline.**
Embedding is the bottleneck. The naive approach (`await embed()` per batch) is sequential. Instead: acquire a semaphore *before* `create_task` (backpressure), dispatch all batches as concurrent tasks, `gather` at the end. At 5-way concurrency this produces a measured 2.9x wall-time reduction. Deduplication runs in two passes — intra-run (`seen: set[str]`) before batching, and a DB hash pre-filter before embedding — so duplicate content is never embedded or billed.

---

## Where does it break at 10x data volume?

The embedding step. At 10x volume (~100k chunks), five concurrent Vertex AI batch calls start hitting quota limits (`RESOURCE_EXHAUSTED`). The HNSW index also degrades — `ef_construction=64` was tuned for <50k vectors; at 500k+ the index build time and memory footprint grow significantly. The second breakpoint is the Cloud Run instance: a single 512Mi container will OOM if a 500MB export is streamed into memory. The fix is already partially in place (streaming parsers with `ijson`), but chunking batches need to be bounded more aggressively and the embedder needs exponential backoff with quota-aware retry.

---

## What I cut, and what comes next

**Cut to stay in scope:**
- Auth — there is none. Any user can ingest and query. Fine for a demo, not for production.
- Hybrid search — BM25 + vector would improve recall on exact-match queries (names, dates, URLs). Pure vector search misses keyword hits.
- Eval harness — no automated retrieval quality measurement. Guardrail threshold (0.30) was tuned by manual spot-checking, not a held-out eval set.
- Re-embedding on model upgrade — chunks store `embedding_model` and `dim` columns for this reason, but the migration path isn't implemented.
- ZIP file support — real LinkedIn/Instagram exports are zipped. The adapter handles bare files; ZIP extraction would need one more step.

**What I'd build next:**
Proper auth (OAuth so users own their data), BM25 hybrid search via `pg_bm25` or a Tantivy sidecar, and an eval loop using a small labeled question set to tune the retrieval threshold scientifically.

---

## If I had to rethink this at 10x scale

The current design is a synchronous request-response pipeline — upload file, wait, get stats. At 10x this becomes a UX problem (60s+ waits) and a reliability problem (Cloud Run timeout).

The rethink: **event-driven ingestion**. File upload writes to Cloud Storage and publishes a Pub/Sub message. A Cloud Run Job (not a service) picks it up, processes asynchronously, and writes progress to a status table. The chat API is unchanged. This decouples ingestion latency from the user-facing response and makes retries trivial.

On the retrieval side: replace pure pgvector cosine with a **hybrid BM25 + vector** pipeline and add a **cross-encoder reranker** (e.g. `cross-encoder/ms-marco-MiniLM`) as a second-pass filter over the top-20. This addresses the main quality gap — the current system retrieves by semantic similarity but can't rank by relevance precision, so off-topic chunks occasionally surface in the top-8.

On the knowledge representation side: **GraphRAG**. Instead of independent chunk embeddings, extract entities and relationships (person → opinion → topic) into a graph. Multi-hop queries ("what's consistent across their LinkedIn posts and tweets about AI?") that currently require good luck with retrieval become graph traversals. The cost is significantly higher complexity and a Neo4j or similar dependency.

---

## Using the live demo

This is a **shared single-tenant demo** — all visitors share one database. Before uploading your own exports:

1. Click **"Clear All Data"** to wipe any existing data
2. Upload your files or click **"Load Demo Data"** to load the sample dataset
3. Ask questions in the chat

If results look wrong, someone else may have ingested data after you. Clear and re-seed.

---

## Running locally

**Prerequisites:** Docker, Python 3.12, uv, Node 18+, GCP project with Vertex AI enabled.

```bash
# 1. Start Postgres with pgvector
docker compose up -d

# 2. Install Python deps
uv sync

# 3. Copy and fill env
cp .env.example .env
# Set DATABASE_URL, GOOGLE_CLOUD_PROJECT, VERTEX_LOCATION

# 4. Start backend
uv run uvicorn app.main:app --reload --port 8000

# 5. Start frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 — drag in an export file or click "Load Demo Data".

---

## Stack

| Layer | Choice |
|---|---|
| Ingestion | Python streaming parsers, adapter registry |
| Embeddings | Vertex AI `text-embedding-005`, 768d, batched + concurrent |
| Vector store | pgvector (Docker dev → Cloud SQL prod) |
| Generation | Vertex AI `gemini-2.5-flash`, SSE streaming |
| Backend | FastAPI + SQLAlchemy 2.0 + asyncpg |
| Frontend | React 18 + Vite |
| Deploy | Cloud Run + Cloud SQL + Vercel |
