# Cortex — Product Requirements Document

## 1. One-line

Ingest a person's social data exports (LinkedIn, Twitter/X, Instagram), build a vector knowledge base from their *authored* content, and answer natural-language questions about them through a grounded, cited RAG chat.

## 2. Problem

A person's "digital self" is scattered across platforms in incompatible export formats (LinkedIn CSV, Twitter JSON, Instagram JSON/HTML). There is no single way to ask *"What does this person think about X?"* and get an answer grounded in their own words. Cortex turns raw, messy, multi-format exports into a queryable knowledge base.

## 3. Goals

| # | Goal | Success signal |
|---|------|----------------|
| G1 | Parse 3 export formats into one canonical content model | All three produce identical `ContentItem` shape; adding a 4th source takes < 1 hour |
| G2 | Keep only content that *represents the person* | Reshares without commentary, likes, ads, system messages are dropped |
| G3 | Build an extensible vector knowledge base | New content types added via schema extension, not rewrite |
| G4 | Answer questions grounded in ingested data with citations | Every answer cites source + date; weak retrieval yields "not enough data," never a hallucination |
| G5 | Handle large exports efficiently | 50MB+ files parse in constant memory; 10k chunks embed via batching + dedup + incremental upsert |

## 4. Non-goals (consciously out of scope for the 4–6h window)

- Authentication / multi-tenant / user accounts
- Polished UI / design system (assignment: "design is not the point")
- Hybrid search (BM25 + vector), rerankers, eval harness — named as "what I'd build next"
- Real-time ingestion / webhooks — batch ETL is sufficient at this scale
- Full test suite — smoke coverage on parsers + retrieval only

## 5. Users & primary flow

**User:** someone exploring a person's public/authored thinking (recruiter, researcher, the person themselves).

**Flow:**
1. Drop export files into an ingest command/endpoint.
2. System streams-parses → normalizes → dedups → chunks → embeds → upserts to pgvector.
3. User opens chat page, asks a question.
4. System embeds query → retrieves top-k chunks (with metadata filter) → passes to Gemini → streams a grounded answer with inline citations.

## 6. Functional requirements

### 6.1 Ingestion
- **FR1** Accept LinkedIn (CSV), Twitter/X (JSON), Instagram (JSON/HTML) exports.
- **FR2** Each source is a thin adapter implementing `parse(file) -> Iterator[ContentItem]`; registered in a registry. No downstream layer knows the source format.
- **FR3** Stream-parse large files (`ijson` for JSON, streaming `csv` reader) — never load a whole file into memory.
- **FR4** Noise filter: drop reshares-without-commentary, likes/saves, ads, connection/system notifications. Keep authored posts, substantive comments, articles, bio/profile.

### 6.2 Knowledge base
- **FR5** Content-type-aware chunking: short posts/tweets/comments = one atomic chunk (never split); long articles = recursive paragraph-boundary split, token-budgeted, small overlap; bio/profile = one chunk.
- **FR6** Embed via Vertex AI `text-embedding-005`.
- **FR7** Store vector + metadata in one pgvector row. Metadata at query time: `source, content_type, authored_at, url, source_id, content_hash`.
- **FR8** Schema extensible to new content types without rewrite (new column / JSONB field).

### 6.3 Efficiency
- **FR9** Dedup before embedding via `sha256(normalized_text)` — skip exact duplicates (cross-posts).
- **FR10** Batch embedding calls (100–500 inputs/request), bounded concurrency (asyncio semaphore).
- **FR11** Incremental upsert keyed on `content_hash` (`ON CONFLICT DO NOTHING`) — re-running ingest only embeds new content.

### 6.4 Chat / RAG
- **FR12** Minimal React chat page.
- **FR13** Retrieve top-k by vector similarity + optional metadata filter; generate grounded answer via Vertex Gemini 2.0 Flash.
- **FR14** Cite sources (platform + date + url) inline.
- **FR15** Stream the response (SSE).
- **FR16** Grounding guardrail: insufficient retrieval → explicit "not enough data in this person's content."

## 7. Non-functional requirements

- **NFR1 — Memory:** ingestion memory is independent of input file size (streaming).
- **NFR2 — Cost:** dedup + batching keep 10k-chunk embedding near-free on credits.
- **NFR3 — Portability:** storage is config — local Docker Postgres (dev) ↔ Cloud SQL (prod) via one `DATABASE_URL` swap, no code change.
- **NFR4 — Config:** 12-factor. All endpoints/secrets from env (`DATABASE_URL`, `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION`).
- **NFR5 — Extensibility:** new source adapter in < 1 hour; new content type via schema extension.

## 8. Architecture (summary — full rationale in `architecture_selection.md`)

```
exports ─▶ SourceAdapter (stream-parse) ─▶ ContentItem[] ─▶ noise filter
        ─▶ dedup (sha256) ─▶ content-type chunker ─▶ Vertex embed (batch/bounded)
        ─▶ pgvector upsert (incremental)
query   ─▶ embed ─▶ top-k + metadata filter ─▶ Gemini (stream) ─▶ cited answer
```

| Layer | Choice |
|-------|--------|
| Ingestion | Python, streaming parse, adapter registry → `ContentItem` |
| Embeddings | Vertex AI `text-embedding-005` (batched, dedup, incremental) |
| Vector DB | pgvector — Docker local (dev) → Cloud SQL (prod) |
| Generation | Vertex Gemini 2.0 Flash, streaming, grounded + cited |
| Backend | FastAPI (async batch embed, SSE) |
| Frontend | React/Vite minimal chat |
| Deploy | Cloud Run + Cloud SQL |

## 9. Canonical data model (contract)

```
ContentItem {
  source_id     # platform-native id  → idempotency
  source        # linkedin | twitter | instagram
  content_type  # post | comment | article | bio | profile
  text          # the authored words
  authored_at   # normalized UTC
  url           # permalink if available
  lang          # detected language
  raw           # original blob (kept for re-processing)
}
```

## 10. Open risks

| Risk | Mitigation |
|------|------------|
| Vertex needs GCP auth even in local dev (not fully offline) | **Decided: Vertex everywhere** (dev + prod). Reviewer runs `gcloud auth application-default login`. `Embedder` interface kept for extensibility, but only the Vertex impl ships. Rationale: embeddings are model-locked (same model must write + read), so one model across all envs guarantees vector compatibility. |
| Export formats vary by account/locale | Adapters tolerate missing fields; `raw` retained for re-parse |
| Near-duplicate (not exact) content slips dedup | Accepted tradeoff at this scale; semantic dedup is "next" work |
