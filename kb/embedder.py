import asyncio
from abc import ABC, abstractmethod


class Embedder(ABC):
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts for indexing, returning one vector per input."""
        ...

    async def embed_one(self, text: str) -> list[float]:
        """Embed a single document text. Delegates to embed_batch."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_one_query(self, text: str) -> list[float]:
        """Embed a query text. Override for query-specific task type."""
        return await self.embed_one(text)


class VertexEmbedder(Embedder):
    def __init__(self, model: str, dim: int, project: str, location: str) -> None:
        self.model = model
        self.dim = dim
        self.project = project
        self.location = location
        self._initialized = False

    def _ensure_init(self) -> None:
        if not self._initialized:
            import vertexai
            vertexai.init(project=self.project, location=self.location)
            self._initialized = True

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents via Vertex text-embedding-005 in thread pool."""
        self._ensure_init()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_embed, texts, "RETRIEVAL_DOCUMENT")

    async def embed_one_query(self, text: str) -> list[float]:
        """Embed a search query with RETRIEVAL_QUERY task type for better asymmetric recall."""
        self._ensure_init()
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, self._sync_embed, [text], "RETRIEVAL_QUERY")
        return results[0]

    def _sync_embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

        model = TextEmbeddingModel.from_pretrained(self.model)
        inputs = [TextEmbeddingInput(text=t, task_type=task_type) for t in texts]
        embeddings = model.get_embeddings(inputs, output_dimensionality=self.dim)
        return [list(e.values) for e in embeddings]
