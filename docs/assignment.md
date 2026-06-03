The Assignment
Skip the take-home quiz. Build something real. You have 4 to 6 hours. The scope is intentionally open. How you make decisions under that constraint is the signal.

Social Data, Vector Knowledge Base, Chat
Build an end-to-end system. Every layer matters. Efficiency is a first-class requirement, not a bonus.

01
Multi-source ingestion
Accept data exports from LinkedIn, Twitter/X, and Instagram. Each platform exports different formats: LinkedIn gives CSVs, Twitter gives JSON, Instagram gives JSON/HTML. Write parsers for all three. Extract the content that actually represents the person (authored posts, written content, profile data) and discard noise. Your parsers should be clean enough that adding a fourth source takes under an hour.
02
Vector knowledge base
From the parsed content, build a vector knowledge base. Chunk intelligently, not just by character count. Embed the chunks using any embedding model (OpenAI, HuggingFace, local). Design the storage schema yourself. Think about what metadata matters at query time. Use any vector store you want (Postgres + pgvector, Pinecone, Chroma, Qdrant) and explain your choice. The schema should be extensible to new content types without a rewrite.
03
Chat interface
Build a minimal chat UI (a simple React page is fine, design is not the point). A user should be able to ask "What does this person think about remote work?" and get an answer grounded in the ingested data with cited sources. Use RAG: retrieve relevant chunks, pass them to an LLM, return a grounded response. Streaming responses are a plus but not required.
04
Efficiency, for real
The system must handle large exports without choking. LinkedIn exports can be 50MB+. Embedding 10,000 chunks naively is slow and expensive. Show that you have thought about this: batching, concurrency, deduplication, incremental upserts. If you made a tradeoff for speed, name it. If you made a tradeoff for cost, name it.
05
Architecture write-up (required)
Include a README that answers the following. One paragraph per question is enough. We care about clarity, not length.
›
What does your system do, and what are the two or three most important architecture decisions you made?
›
Where is the bottleneck at 10x data volume? What breaks first?
›
What did you consciously cut to stay in the 4 to 6 hour window, and what would you build next?
›
If you had to make this architecture 10x better (not iterate on it, but rethink it), what would you change and why?
What we evaluate: How you reason under constraints, schema and layer design, code a teammate could extend, and honesty about tradeoffs. Polish is not the goal. Judgment is.
