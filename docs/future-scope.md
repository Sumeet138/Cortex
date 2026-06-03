# Future Scope

Deliberately deferred work. Each item names *why it's out of the 4–6h window* and *what it would buy*. This doubles as the source for the README's "what I'd build next" and "10x rethink" answers.

---

## 1. GraphRAG — knowledge graph layer (Neo4j)

**Status:** deferred. Reserved as the primary answer to README Q4 ("make it 10x better — rethink, not iterate").

### Storyline (quick-glance)

The plain story, in one breath:

> Right now we ask the person's words *"what looks similar?"* (vector).
> With a graph we also ask *"what's connected?"* — people, topics, companies, time.

**Today — vector only:**
```
question ─▶ embed ─▶ [pgvector: nearest chunks] ─▶ LLM ─▶ answer
                          │
                     finds text that SOUNDS like the question
                     (blind to relationships)
```

**With GraphRAG — vector finds the door, graph walks the rooms:**
```
                 ┌─▶ [pgvector: nearest chunks] ──┐   (entry points)
question ─▶ embed │                                ├─▶ merge ─▶ LLM ─▶ grounded
                 └─▶ [graph: who/what/when around │            multi-hop answer
                      those chunks, 1–2 hops] ─────┘   (the connections)
```

**How the graph gets built (ingestion side):**
```
ContentItem ─▶ LLM-NER ─▶ entities + relations ─▶ Neo4j
  "post about      │            │
   remote work"    │            └─ (Post)-[:MENTIONS]->(Topic:"remote work")
                   └─ Person, Topic, Company nodes
```

**One concrete example:**
```
Q: "How did X's view on AI evolve?"

vector alone:  returns 3 posts that mention AI   ✗ no order, no change
graph:         (X)-[:AUTHORED]->(Post {t})-[:MENTIONS]->(Topic:AI)
               walk posts BY TIME ─▶ 2022 skeptical → 2024 optimistic  ✓
```

### What it adds
A property graph alongside the vector store, populated by LLM-based entity extraction (NER) over each chunk:

```
(Person)-[:AUTHORED]->(Post)
(Post)-[:MENTIONS]->(Topic | Company | Person)
(Post)-[:ON_PLATFORM]->(Platform)
(Person)-[:WORKED_AT]->(Company)
# timestamps on Post nodes / edges for temporal queries
```

Retrieval becomes **hybrid**: vector search finds entry-point chunks → traverse the graph for connected context → feed both to the LLM. Grounded multi-hop, not just nearest-neighbor.

### Why it beats vector-only (the queries that justify it)
Vector RAG is structurally weak at entity-centric, multi-hop, and temporal questions:

| Query | Vector top-k | Graph |
|-------|-------------|-------|
| "What does X think about remote work?" | Good | Tie |
| "Who does X talk about most?" | Bad (no aggregation) | Strong (degree on `MENTIONS`) |
| "How did X's view on AI evolve?" | Bad (no time/relation) | Strong (timestamped edges) |
| "What connects X's posts on startups + burnout?" | Weak | Strong (shared topic nodes, multi-hop) |
| "Same person across LinkedIn + Twitter?" | Can't | Strong (identity resolution / node merge) |

### Why it's deferred (the honest cost)
- **Second source of truth** — graph + pgvector must stay in sync.
- **Entity-extraction pipeline** — LLM-NER per chunk: more LLM calls, prompt design, entity dedup/canonicalization. This is the expensive part.
- **+2–4 hours** realistically. Building it half-way while the core RAG stays rough is a worse signal than a clean vector RAG that *names* this as the next evolution.

### Build path when resumed
1. Thin slice first: one entity type (`Topic`), one relation (`MENTIONS`), hybrid retrieve.
2. Expand to Person/Company + identity resolution across platforms.
3. Add temporal edges for "evolution over time" queries.

---

## 2. Hybrid search (BM25 + vector)

Lexical + semantic fusion (e.g. reciprocal rank fusion). Catches exact-term matches (names, acronyms, handles) that pure embeddings miss. Cheap to add (Postgres full-text + pgvector in one query). Deferred only for time.

## 3. Reranker

Cross-encoder rerank of top-k before generation → higher precision context, fewer tokens to the LLM. Cost: extra model call per query. Deferred for time.

## 4. Semantic dedup

Current dedup is exact-hash (`sha256(normalized_text)`) — near-duplicate cross-posts (minor edits) still slip through. Embedding-similarity dedup would catch them. Deferred; named as an accepted tradeoff at current scale.

## 5. Eval harness

Golden Q→expected-source set, retrieval precision/recall + grounding-faithfulness scoring. Needed before tuning chunking/k. Deferred — no tuning loop in the initial window.

## 6. Incremental re-embedding on model change

If the embedding model changes, all vectors need recompute. A versioned `embedding_model` column + background re-embed job would make this safe. Schema already reserves room; job deferred.

## 7. Streaming / event-driven ingestion

Current ingestion is batch ETL. At high volume or for live sync, move to a queue (Pub/Sub) + worker pool, decoupling parse → embed → upsert. Named in README "bottleneck at 10x" — embedding throughput is the first wall; a queue + horizontal embed workers is the fix.
