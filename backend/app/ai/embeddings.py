"""Embedding provider abstraction and implementations for local-first vector search."""

import abc
import hashlib
import math
import random
import re
from typing import Any
import httpx

from app.config import settings


class EmbeddingError(Exception):
    """Base exception for all embedding-related errors."""


class EmbeddingModelUnavailableError(EmbeddingError):
    """Raised when the specified embedding model is not installed or available on the host."""


class EmbeddingConnectionError(EmbeddingError):
    """Raised when the embedding provider cannot be reached."""


class EmbeddingDimensionMismatchError(EmbeddingError):
    """Raised when the returned embedding vector dimension differs from configured expectation."""


class EmbeddingProvider(abc.ABC):
    """Abstract base class for text embedding generation."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """The dimensionality of vectors produced by this provider."""

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """The name or identifier of the underlying embedding model."""

    @abc.abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text string."""

    @abc.abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a list of text strings."""

    def embed_text_sync(self, text: str) -> list[float]:
        """Synchronous wrapper for embed_text."""
        import asyncio
        return asyncio.run(self.embed_text(text))

    def embed_batch_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous wrapper for embed_batch."""
        import asyncio
        return asyncio.run(self.embed_batch(texts))


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Local Ollama-backed embedding provider using /api/embed or /api/embeddings."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.EMBEDDING_MODEL
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT
        self._client = client
        self._external_client = client is not None

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if not self._external_client and self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of strings using Ollama."""
        if not texts:
            return []

        client = await self._get_client()
        url_embed = f"{self._base_url}/api/embed"
        payload = {"model": self._model, "input": texts}

        try:
            resp = await client.post(url_embed, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                embeddings = data.get("embeddings")
                if isinstance(embeddings, list) and len(embeddings) == len(texts):
                    # Validate vector dimensions
                    for emb in embeddings:
                        if len(emb) != self._dimension:
                            raise EmbeddingDimensionMismatchError(
                                f"Embedding dimension mismatch: expected {self._dimension}, got {len(emb)}"
                            )
                    return embeddings
                raise EmbeddingError(f"Unexpected response format from Ollama /api/embed: {data}")

            if resp.status_code == 404:
                # Fallback to legacy single /api/embeddings sequentially
                return await self._embed_batch_legacy(texts, client)

            if "not support embeddings" in resp.text or "not found" in resp.text:
                raise EmbeddingModelUnavailableError(
                    f"Ollama model '{self._model}' is unavailable or does not support embeddings: {resp.text}"
                )

            raise EmbeddingError(f"Ollama embed returned HTTP {resp.status_code}: {resp.text}")

        except (httpx.ConnectError, httpx.NetworkError) as err:
            raise EmbeddingConnectionError(f"Failed to connect to Ollama at {self._base_url}: {err}") from err
        except httpx.TimeoutException as err:
            raise EmbeddingConnectionError(f"Timed out connecting to Ollama at {self._base_url}: {err}") from err

    async def _embed_batch_legacy(self, texts: list[str], client: httpx.AsyncClient) -> list[list[float]]:
        """Fallback for older Ollama servers supporting only /api/embeddings."""
        url_legacy = f"{self._base_url}/api/embeddings"
        results = []
        for text in texts:
            resp = await client.post(url_legacy, json={"model": self._model, "prompt": text})
            if resp.status_code != 200:
                raise EmbeddingError(f"Ollama legacy /api/embeddings returned HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            emb = data.get("embedding")
            if not isinstance(emb, list) or len(emb) != self._dimension:
                raise EmbeddingDimensionMismatchError(
                    f"Embedding dimension mismatch: expected {self._dimension}, got {len(emb) if isinstance(emb, list) else 'None'}"
                )
            results.append(emb)
        return results

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for a single text."""
        res = await self.embed_batch([text])
        return res[0]


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, mock embedding provider for tests and offline development."""

    def __init__(self, dimension: int | None = None, model_name: str = "mock-embed-v1") -> None:
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def _generate_vector(self, text: str) -> list[float]:
        """Generate a deterministic unit-normalized pseudo-vector based on word tokens and text hash."""
        words = [w.lower() for w in re.findall(r"\w+", text) if len(w) > 2]
        if not words:
            words = [text.strip().lower() or "empty"]

        combined = [0.0] * self._dimension
        for word in words:
            h = hashlib.sha256(word.encode("utf-8")).digest()
            seed = int.from_bytes(h[:8], "big")
            rng = random.Random(seed)
            for i in range(self._dimension):
                combined[i] += rng.gauss(0.0, 1.0)

        norm = math.sqrt(sum(x * x for x in combined))
        if norm == 0.0:
            combined[0] = 1.0
            norm = 1.0
        return [round(x / norm, 6) for x in combined]

    async def embed_text(self, text: str) -> list[float]:
        return self._generate_vector(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._generate_vector(t) for t in texts]


def get_embedding_provider() -> EmbeddingProvider:
    """Dependency factory returning the active embedding provider."""
    provider_type = settings.EMBEDDING_PROVIDER.strip().lower()
    if provider_type == "mock":
        return MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
    return OllamaEmbeddingProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
        timeout=settings.OLLAMA_TIMEOUT,
    )
