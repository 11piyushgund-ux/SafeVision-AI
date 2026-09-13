"""
SafeVision AI — Knowledge Base / Vector Store (Phase 8)

Uses ChromaDB as the vector store for safety document embeddings.

Architecture:
  - Document metadata + chunk text → PostgreSQL (SafetyDocument, DocumentChunk)
  - Embedding vectors → ChromaDB (indexed by chunk_id, filtered by org_id)
  - pgvector is NOT available on PostgreSQL 18.4; ChromaDB is the vector backend

ChromaDB collection naming:
  One collection per organization: "org_{org_id}" for strict tenant isolation.

Retrieval:
  Query → embed → search ChromaDB (org-scoped collection) → return chunks
"""

from __future__ import annotations

import structlog

from app.config import get_settings
from app.services.embedding_service import EmbeddingService

log = structlog.get_logger()

# Module-level ChromaDB client (lazy-loaded)
_chroma_client = None


def _get_chroma_client():
    """Lazy-load the ChromaDB persistent client."""
    global _chroma_client  # noqa: PLW0603
    if _chroma_client is None:
        import chromadb

        settings = get_settings()
        _chroma_client = chromadb.PersistentClient(
            path=settings.chromadb_persist_dir,
        )
        log.info("chromadb_initialized", persist_dir=settings.chromadb_persist_dir)
    return _chroma_client


def _collection_name(org_id: str) -> str:
    """Generate the ChromaDB collection name for an organization."""
    # ChromaDB collection names: 3-63 chars, [a-zA-Z0-9_-]
    # org_id is a UUID (36 chars) — prefix with "org_" = 40 chars
    return f"org_{org_id}"


class KnowledgeBase:
    """
    ChromaDB-backed vector store for safety knowledge retrieval.

    Each organization gets its own ChromaDB collection for strict isolation.
    """

    @staticmethod
    def store_chunks(
        org_id: str,
        chunks: list[dict],
    ) -> int:
        """
        Store document chunks with their embeddings in ChromaDB.

        Args:
            org_id: Organization ID for collection isolation.
            chunks: List of dicts with keys:
                - id: chunk UUID (str)
                - content: chunk text (str)
                - embedding: embedding vector (list[float])
                - metadata: additional metadata (dict)

        Returns:
            Number of chunks stored.

        Raises:
            ValueError: If chunks is empty or malformed.
        """
        if not chunks:
            msg = "Cannot store empty chunk list"
            raise ValueError(msg)

        client = _get_chroma_client()
        collection = client.get_or_create_collection(
            name=_collection_name(org_id),
            metadata={"org_id": org_id},
        )

        ids = [c["id"] for c in chunks]
        embeddings = [c["embedding"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [c.get("metadata", {}) for c in chunks]

        # Ensure org_id is in every metadata for defense-in-depth
        for m in metadatas:
            m["org_id"] = org_id

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        log.info(
            "knowledge_chunks_stored",
            org_id=org_id,
            chunk_count=len(chunks),
            collection=_collection_name(org_id),
        )

        return len(chunks)

    @staticmethod
    def search(
        org_id: str,
        query_text: str,
        top_k: int | None = None,
    ) -> list[dict]:
        """
        Semantic search for safety knowledge chunks.

        Args:
            org_id: Organization ID (tenant isolation).
            query_text: Natural language query.
            top_k: Number of results to return (default from config).

        Returns:
            List of result dicts, ordered by relevance:
                - chunk_id: str
                - content: str
                - score: float (similarity, higher = more relevant)
                - metadata: dict
        """
        if not query_text or not query_text.strip():
            msg = "Search query cannot be empty"
            raise ValueError(msg)

        settings = get_settings()
        if top_k is None:
            top_k = settings.rag_default_top_k

        client = _get_chroma_client()
        col_name = _collection_name(org_id)

        # Check if collection exists
        try:
            collection = client.get_collection(name=col_name)
        except Exception:
            log.info("knowledge_search_empty", org_id=org_id, reason="no_collection")
            return []

        # Check if collection has any documents
        if collection.count() == 0:
            return []

        # Embed the query
        query_embedding = EmbeddingService.embed_query(query_text)

        # Search
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                # ChromaDB returns distances; convert to similarity
                # For cosine distance: similarity = 1 - distance
                distance = results["distances"][0][i] if results["distances"] else 0.0
                similarity = max(0.0, 1.0 - distance)

                output.append({
                    "chunk_id": chunk_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "score": round(similarity, 6),
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })

        log.info(
            "knowledge_search_complete",
            org_id=org_id,
            query_len=len(query_text),
            top_k=top_k,
            results_count=len(output),
        )

        return output

    @staticmethod
    def delete_document_chunks(org_id: str, document_id: str) -> int:
        """
        Delete all chunks for a document from ChromaDB.

        Args:
            org_id: Organization ID.
            document_id: Document ID whose chunks should be removed.

        Returns:
            Number of chunks deleted (0 if none found).
        """
        client = _get_chroma_client()
        col_name = _collection_name(org_id)

        try:
            collection = client.get_collection(name=col_name)
        except Exception:
            return 0

        # Get chunks belonging to this document
        results = collection.get(
            where={"document_id": document_id},
            include=[],
        )

        if not results or not results["ids"]:
            return 0

        count = len(results["ids"])
        collection.delete(ids=results["ids"])

        log.info(
            "knowledge_chunks_deleted",
            org_id=org_id,
            document_id=document_id,
            deleted_count=count,
        )

        return count

    @staticmethod
    def get_collection_count(org_id: str) -> int:
        """Get the total number of chunks in an org's collection."""
        client = _get_chroma_client()
        try:
            collection = client.get_collection(name=_collection_name(org_id))
            return collection.count()
        except Exception:
            return 0
