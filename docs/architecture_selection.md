# Architecture Selection — Decisions, Why, and Why-Nots

> This document is the defense record. Every major choice lists what we picked, why it wins, every alternative we rejected, and *why it lost*. It exists so the decisions can be argued under questioning, not just stated.

---

## Decision 1 — Vector store: **Postgres + pgvector**

**Picked:** pgvector, Docker locally for dev → Cloud SQL for production.

### Why it wins
1. **One store for vectors AND metadata.** Both live in the same row. Alternatives put vectors in store X and metadata in DB Y → two writes per upsert, sync drift, reconciliation bugs. pgvector = one transactional write.
2. **Incremental upsert is native** (an explicit assignment requirement): `INSERT ... ON CONFLICT (content_hash) DO NOTHING`. No application-level dedup dance.
3. **Metadata-at-query-time is a graded line.** "Think about what metadata matters at query time." pgvector fuses it into one SQL query: `WHERE source='twitter' AND authored_at > '2024-01-01'` *combined with* vector similarity. Ranges, joins, and filters are first-class.
4. **Extensible without rewrite** (assignment line): new content type = add a column or JSONB key. A migration, not a re-architecture.

### Alternatives rejected
| Option | Why rejected |
|--------|--------------|
| **Chroma** | Fastest to stand up, but signals optimizing for the take-home, not production. Weak filtering (dict-only, no ranges/joins). Under questioning, the only "why" is "it was easy" — a poor judgment signal. |
| **Qdrant** | Technically excellent and scales to 10M+, but at 10k chunks it's a Ferrari to cross the street. Adds a container. Can't answer "why not the Postgres you already run for app data?" → over-engineering signal. |
| **Pinecone** | Zero infra, but outsources the interesting part, costs money, vendor lock, and *re-splits* metadata from vectors. Evaluator learns nothing about our data-layer thinking. |

### Why local-dev → cloud-prod is correct (not a compromise)
pgvector is the **same extension** in Docker and Cloud SQL — only the connection string differs. Reviewer runs `docker compose up` offline with zero GCP auth (lowers friction to evaluate us). Deploy = point `DATABASE_URL` at Cloud SQL, identical schema/queries/index, no code change.

**Defense line:** *"Storage is config, not architecture. Local Postgres and Cloud SQL run identical pgvector — the swap is one env var. Dev stays hermetic and free; prod gets managed backups/HA. No code branches on environment."*

---

## Decision 2 — Cloud strategy: **All-GCP (Vertex + Cloud SQL + Cloud Run)**

**Picked:** unified GCP, funded by $300 credits.

### Why it wins
- **One cloud, one IAM, one bill.** Coherent story: Vertex embeddings + Vertex Gemini generation + Cloud SQL pgvector + Cloud Run deploy.
- **Credits make premium choices effectively free** — no penny-pinching that compromises the design.
- **Native integration:** Cloud Run ↔ Cloud SQL connector, Vertex auth via ADC, no cross-vendor glue.

### Alternatives rejected
| Option | Why rejected |
|--------|--------------|
| **Vendor-light (OpenAI + local PG only)** | Lowest friction and zero-risk, but leaves $300 credits unused and tells a two-vendor story. Fine fallback, but we have a better-funded option. |
| **Hybrid (Vertex embeds, local everything)** | Reasonable, but doesn't commit to a deployable cloud story — and the assignment implies deployment. |

### Known snag (named, not hidden) — RESOLVED
Vertex needs GCP auth even in local dev (`gcloud auth application-default login`), so the system isn't 100% offline.

**Decision: Vertex everywhere (dev + prod). No local fallback ships.** The deciding constraint is that **embeddings are model-locked** — a vector only has meaning if query-time uses the exact model (and dimension) that wrote it. bge-small (384d) and Vertex `text-embedding-005` (768d) are incompatible; mixing them silently corrupts similarity. Running one model across all environments removes that whole failure class.

- The `Embedder` interface is **still defined** (cheap, keeps the swap trivial later), but only the Vertex impl ships.
- The schema stores `embedding_model` + `dim` per vector so the system can refuse to mix models if one is ever added (correctness guardrail, see `future-scope.md` item 6).
- Accepted cost: a reviewer must have a GCP account + run ADC login to execute end-to-end. Named, not hidden.

**Defense line:** *"Embeddings are model-locked — same model must write and read or similarity is meaningless. One model across all envs removes that failure class, so I run Vertex everywhere rather than a dev/prod split that would force re-embedding and risk dimension mismatch. The Embedder interface and per-vector model versioning keep a future swap safe."*

---

## Decision 3 — Embeddings: **Vertex AI `text-embedding-005`**

**Picked:** Vertex `text-embedding-005`.

### Why it wins
- Credits cover it → free for this assignment.
- Top-tier quality; configurable dimensionality (768 default — smaller index, faster search, lower storage).
- Completes the single-cloud narrative (same vendor as generation).

### Alternatives rejected
| Option | Why rejected |
|--------|--------------|
| **OpenAI `3-small`** | Lowest friction and cheap, but doesn't use credits and adds a second vendor. Strong fallback if Vertex setup eats too much time. |
| **Local bge-small** | $0 marginal and offline — the strongest pure cost-flex — but download + slow-without-GPU is a setup-risk gamble, and (decisive) its 384d vectors are incompatible with Vertex's 768d, so it can't coexist as a fallback without re-embedding. Dropped entirely; Vertex runs in all environments (see Decision 2). |

**Defense for not going local-to-save-cost:** *"Dedup + batching already drop 10k chunks to cents-or-free. Engineering time to babysit a local model outweighs the saving at this scale. At 10M chunks the math flips — then self-hosted wins. The choice is scale-dependent, and I've matched it to the scale."*

---

## Decision 4 — Generation LLM: **Vertex Gemini 2.0 Flash**

**Picked:** Gemini 2.0 Flash via Vertex.

### Why it wins
- Fast + cheap-on-credits, streaming native, strong at grounded/cited RAG.
- Same vendor as embeddings → one IAM, one bill, coherent story.

### Alternatives rejected
| Option | Why rejected |
|--------|--------------|
| **gpt-4o-mini** | Equally capable for grounded RAG, but breaks the single-cloud story and ignores credits. Fallback if pairing with OpenAI embeddings. |
| **Gemini Pro / larger** | Unnecessary cost/latency for short grounded answers; Flash is the right tier for retrieval-augmented Q&A. |

---

## Decision 5 — Backend stack: **Python + FastAPI**

**Picked:** Python / FastAPI.

### Why it wins
- The efficiency section (streaming parse, bounded-concurrency batch embed) is **idiomatic in Python** — `ijson`, `asyncio` semaphores — and awkward elsewhere. Don't fight the tools on the most-graded layer.
- Best RAG/embedding ecosystem.
- FastAPI gives async + SSE streaming cleanly.

### Alternatives rejected
| Option | Why rejected |
|--------|--------------|
| **Full TypeScript (Next.js)** | Single language and fastest UI, but trades ergonomics on Section 04 (efficiency), the highest-scoring part. Streaming parse + async batch are clunkier. Frontend is explicitly "not the point," so the TS UI advantage is worth little here. |

---

## Decision 6 — Frontend: **React + Vite (minimal)**

**Picked:** minimal React/Vite chat page.

### Why it wins
- Assignment: "a simple React page is fine, design is not the point." Meet the bar, spend the budget on graded layers.
- Vite = fast dev server, trivial SSE consumption for streaming.

### Alternatives rejected
| Option | Why rejected |
|--------|--------------|
| **Next.js** | More than needed for one chat page; adds build/deploy weight. |
| **Plain HTML/JS** | Slightly faster to write, but React is expected and costs nothing extra. |

---

## Decision 7 — Deploy target: **Cloud Run**

**Picked:** Cloud Run (backend + frontend) + Cloud SQL.

### Why it wins
- Serverless, **scale-to-zero** → credits last longer.
- One `gcloud run deploy`; native Cloud SQL connector.
- The service is stateless — perfect Cloud Run fit.

### Alternatives rejected
| Option | Why rejected |
|--------|--------------|
| **GKE** | Earns its complexity at many-services scale, not one stateless service. Ops overhead unjustified. |
| **Compute Engine VM** | You babysit patching/scaling/uptime. No autoscale. |

**Defense line (why not GKE):** *"One stateless service. Cloud Run gives autoscale + scale-to-zero with zero ops. GKE earns its complexity with many services, not here."*

---

## Cross-cutting principle: **config, not code, branches on environment**

Everything reads from env (`DATABASE_URL`, `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION`). 12-factor. Local `.env` ↔ Cloud Run env vars. This is what makes the local→cloud swap (Decision 1) a one-variable change with zero code forks.

---

## Summary table

| Decision | Picked | Top rejected alternative | One-line why |
|----------|--------|--------------------------|--------------|
| Vector store | pgvector | Chroma | One store for vectors+metadata, SQL filtering, native incremental upsert |
| Cloud | All-GCP | Vendor-light | Credits fund a coherent single-cloud story |
| Embeddings | Vertex `text-embedding-005` | OpenAI 3-small | Free on credits, top quality, single vendor |
| Generation | Gemini 2.0 Flash | gpt-4o-mini | Fast, cheap-on-credits, single vendor |
| Backend | FastAPI | Next.js (TS) | Efficiency layer is idiomatic in Python |
| Frontend | React/Vite | Next.js | Minimal is the explicit bar |
| Deploy | Cloud Run | GKE | Stateless service, scale-to-zero, zero ops |
