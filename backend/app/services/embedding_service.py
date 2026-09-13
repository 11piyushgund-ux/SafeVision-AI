"""
SafeVision AI — Embedding Service (Phase 8)

Generates text embeddings using sentence-transformers.

Provider: Local sentence-transformers (all-MiniLM-L6-v2, 384 dimensions)
No external API keys required.

The service is stateless and thread-safe after model loading.
Model is loaded lazily on first use and cached for the process lifetime.
"""

from __future__ import annotations

import structlog
from sentence_transformers import SentenceTransformer

from app.config import get_settings

log = structlog.get_logger()

# Module-level cache for the model (loaded once)
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the sentence-transformers model."""
    global _model  # noqa: PLW0603
    if _model is None:
        settings = get_settings()
        log.info("embedding_model_loading", model=settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        log.info(
            "embedding_model_loaded",
            model=settings.embedding_model,
            dimension=_model.get_sentence_embedding_dimension(),
        )
    return _model


class EmbeddingService:
    """
    Generate text embeddings using sentence-transformers.

    Stateless — all state is in the cached model singleton.
    """

    @staticmethod
    def embed_texts(texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).

        Raises:
            ValueError: If texts is empty.
            RuntimeError: If embedding generation fails.
        """
        if not texts:
            msg = "Cannot embed empty text list"
            raise ValueError(msg)

        model = _get_model()
        settings = get_settings()

        try:
            vectors = model.encode(texts, show_progress_bar=False)
        except Exception as e:
            log.error("embedding_failed", error=str(e), text_count=len(texts))
            msg = f"Embedding generation failed: {e}"
            raise RuntimeError(msg) from e

        # Validate dimensions
        expected_dim = settings.embedding_dimension
        for i, vec in enumerate(vectors):
            if len(vec) != expected_dim:
                msg = (
                    f"Embedding dimension mismatch at index {i}: "
                    f"expected {expected_dim}, got {len(vec)}"
                )
                raise RuntimeError(msg)

        return [v.tolist() for v in vectors]

    @staticmethod
    def embed_query(text: str) -> list[float]:
        """
        Generate an embedding for a single query text.

        Convenience wrapper around embed_texts for single queries.
        """
        if not text or not text.strip():
            msg = "Cannot embed empty query"
            raise ValueError(msg)

        results = EmbeddingService.embed_texts([text])
        return results[0]

    @staticmethod
    def get_dimension() -> int:
        """Return the configured embedding dimension."""
        return get_settings().embedding_dimension
