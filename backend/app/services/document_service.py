"""
SafeVision AI — Document Ingestion Service (Phase 8)

Handles the complete document pipeline:
  Upload → Validate → Extract Text → Chunk → Embed → Store

Supported formats: .txt, .md (plain text / markdown)

Chunking strategy:
  Fixed-size character chunks with configurable overlap.
  Deterministic: same input always produces the same chunks.
  Preserves document order via chunk_index.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import pypdf
import structlog
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.document import (
    DocumentChunk,
    DocumentStatus,
    DocumentType,
    SafetyDocument,
)
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_base import KnowledgeBase

log = structlog.get_logger()

# ==============================================================================
# Supported file extensions → DocumentType
# ==============================================================================

EXTENSION_MAP: dict[str, DocumentType] = {
    ".txt": DocumentType.TXT,
    ".md": DocumentType.MARKDOWN,
    ".markdown": DocumentType.MARKDOWN,
    ".pdf": DocumentType.PDF,
}


SUPPORTED_EXTENSIONS = set(EXTENSION_MAP.keys())


# ==============================================================================
# Document Service
# ==============================================================================

class DocumentService:
    """
    Document ingestion and management service.

    Handles validation, text extraction, chunking, embedding, and storage.
    """

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    @staticmethod
    def ingest(
        db: Session,
        org_id: str,
        filename: str,
        content: str | bytes,
        title: str | None = None,
        description: str | None = None,
        uploaded_by: str | None = None,
    ) -> SafetyDocument:
        """
        Ingest a safety document: validate, chunk, embed, store.

        This is the main entry point for document processing.

        Args:
            db: SQLAlchemy session.
            org_id: Organization ID (tenant).
            filename: Original filename (used for type detection).
            content: Document content (str or bytes).
            title: Optional title (defaults to filename).
            description: Optional description.
            uploaded_by: User ID who uploaded.

        Returns:
            SafetyDocument with status READY on success, FAILED on error.

        Raises:
            ValueError: For validation failures (unsupported type, empty, too large).
        """
        settings = get_settings()

        # --- Validate ---
        doc_type = DocumentService._detect_type(filename)
        if doc_type is None:
            msg = (
                f"Unsupported file type: '{filename}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )
            raise ValueError(msg)

        # Size check
        byte_size = len(content) if isinstance(content, bytes) else len(content.encode("utf-8"))
        if byte_size > settings.max_document_size_bytes:
            msg = (
                f"Document too large: {byte_size} bytes "
                f"(max: {settings.max_document_size_bytes})"
            )
            raise ValueError(msg)

        # Extraction & Chunking per document type
        pages_info: list[dict] | None = None
        if doc_type == DocumentType.PDF:
            pages = DocumentService.extract_text_from_pdf(content)
            pages_info = pages
            raw_chunks: list[dict] = []
            for page in pages:
                page_chunks = DocumentService.chunk_text(
                    page["text"],
                    chunk_size=settings.chunk_size,
                    overlap=settings.chunk_overlap,
                )
                for c in page_chunks:
                    raw_chunks.append({
                        "text": c["text"],
                        "metadata": {
                            "page_number": page["page_number"],
                            "start_char": c["metadata"]["start_char"],
                            "end_char": c["metadata"]["end_char"],
                            "chunk_index": len(raw_chunks),
                        },
                    })
        else:
            text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
            if not text.strip():
                msg = "Document is empty or contains only whitespace"
                raise ValueError(msg)

            raw_chunks = DocumentService.chunk_text(
                text,
                chunk_size=settings.chunk_size,
                overlap=settings.chunk_overlap,
            )

        if not raw_chunks:
            msg = "Document produced no chunks after processing"
            raise ValueError(msg)

        # --- Create document record ---
        doc = SafetyDocument(
            id=str(uuid.uuid4()),
            org_id=org_id,
            title=title or filename,
            description=description,
            document_type=doc_type,
            filename=filename,
            file_size=byte_size,
            status=DocumentStatus.PROCESSING,
            uploaded_by=uploaded_by,
        )
        db.add(doc)
        db.flush()

        try:
            # --- Generate embeddings ---
            chunk_texts = [c["text"] for c in raw_chunks]
            embeddings = EmbeddingService.embed_texts(chunk_texts)

            # --- Store chunks in PostgreSQL & ChromaDB ---
            db_chunks = []
            chroma_chunks = []

            for i, (chunk_data, embedding) in enumerate(
                zip(raw_chunks, embeddings, strict=True),
            ):
                chunk_id = str(uuid.uuid4())
                chunk_meta = chunk_data.get("metadata", {})
                db_chunk = DocumentChunk(
                    id=chunk_id,
                    document_id=doc.id,
                    org_id=org_id,
                    chunk_index=i,
                    content=chunk_data["text"],
                    char_count=len(chunk_data["text"]),
                    source_metadata=chunk_meta,
                    embedding_dim=len(embedding),
                )
                db.add(db_chunk)
                db_chunks.append(db_chunk)

                chroma_meta = {
                    "document_id": doc.id,
                    "org_id": org_id,
                    "chunk_index": i,
                    "document_title": doc.title,
                    "filename": doc.filename,
                }
                if "page_number" in chunk_meta:
                    chroma_meta["page_number"] = chunk_meta["page_number"]

                chroma_chunks.append({
                    "id": chunk_id,
                    "content": chunk_data["text"],
                    "embedding": embedding,
                    "metadata": chroma_meta,
                })

            # --- Store vectors in ChromaDB ---
            KnowledgeBase.store_chunks(org_id=org_id, chunks=chroma_chunks)

            # --- Update document status ---
            doc.status = DocumentStatus.READY
            doc.chunk_count = len(db_chunks)
            doc_meta = {
                "chunk_size": settings.chunk_size,
                "chunk_overlap": settings.chunk_overlap,
                "embedding_model": settings.embedding_model,
                "embedding_dim": settings.embedding_dimension,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            if pages_info is not None:
                doc_meta["page_count"] = len(pages_info)
            doc.processing_metadata = doc_meta
            db.flush()

            log.info(
                "document_ingested",
                doc_id=doc.id,
                org_id=org_id,
                chunks=len(db_chunks),
                filename=filename,
            )

        except Exception as e:
            # Clean up any partial vectors in ChromaDB to prevent orphaned embeddings
            try:
                KnowledgeBase.delete_document_chunks(org_id=org_id, document_id=doc.id)
            except Exception as cleanup_err:
                log.warning("chroma_cleanup_failed", doc_id=doc.id, error=str(cleanup_err))

            # Mark document as failed — don't leave partial state
            doc.status = DocumentStatus.FAILED
            doc.processing_metadata = {"error": str(e)}
            db.flush()
            log.error(
                "document_ingestion_failed",
                doc_id=doc.id,
                org_id=org_id,
                error=str(e),
            )
            raise

        return doc

    # ------------------------------------------------------------------
    # PDF Extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_text_from_pdf(content: str | bytes) -> list[dict]:
        """
        Extract text from a PDF document page by page.

        Returns:
            List of dicts: [{"page_number": int, "text": str}]

        Raises:
            ValueError: If PDF is invalid, empty, or contains no extractable text (OCR not enabled).
        """
        raw_bytes = content if isinstance(content, bytes) else content.encode("utf-8", errors="replace")
        try:
            reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        except Exception as e:
            msg = f"Failed to parse PDF document: {e}"
            raise ValueError(msg) from e

        if not reader.pages:
            msg = "PDF document contains no pages"
            raise ValueError(msg)

        pages: list[dict] = []
        total_text_len = 0
        for page_idx, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as e:
                log.warning("pdf_page_extract_failed", page=page_idx, error=str(e))
                page_text = ""

            clean_text = page_text.strip()
            if clean_text:
                total_text_len += len(clean_text)
                pages.append({
                    "page_number": page_idx,
                    "text": clean_text,
                })

        if total_text_len == 0 or not pages:
            msg = "PDF contains no extractable text; OCR is not currently enabled."
            raise ValueError(msg)

        return pages


    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 512,
        overlap: int = 64,
    ) -> list[dict]:
        """
        Split text into fixed-size chunks with overlap.

        Deterministic: same input always produces the same chunks.

        Args:
            text: Input text to chunk.
            chunk_size: Maximum characters per chunk.
            overlap: Character overlap between consecutive chunks.

        Returns:
            List of dicts: {"text": str, "metadata": {"start": int, "end": int}}
        """
        if not text or not text.strip():
            return []

        if chunk_size <= 0:
            msg = "chunk_size must be positive"
            raise ValueError(msg)
        if overlap < 0:
            msg = "overlap must be non-negative"
            raise ValueError(msg)
        if overlap >= chunk_size:
            msg = "overlap must be less than chunk_size"
            raise ValueError(msg)

        # Normalize whitespace
        text = text.strip()

        chunks = []
        start = 0
        step = chunk_size - overlap

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()

            if chunk_text:  # Skip empty chunks
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "start_char": start,
                        "end_char": end,
                        "chunk_index": len(chunks),
                    },
                })

            start += step

        return chunks

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @staticmethod
    def get_document(db: Session, doc_id: str, org_id: str) -> SafetyDocument | None:
        """Get a document by ID, scoped by org_id."""
        return db.query(SafetyDocument).filter(
            SafetyDocument.id == doc_id,
            SafetyDocument.org_id == org_id,
            SafetyDocument.status != DocumentStatus.DELETED,
        ).first()

    @staticmethod
    def list_documents(
        db: Session,
        org_id: str,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[SafetyDocument], int]:
        """List documents for an organization (paginated)."""
        query = db.query(SafetyDocument).filter(
            SafetyDocument.org_id == org_id,
            SafetyDocument.status != DocumentStatus.DELETED,
        )
        total = query.count()
        offset = (page - 1) * size
        docs = (
            query
            .order_by(SafetyDocument.created_at.desc())
            .offset(offset)
            .limit(size)
            .all()
        )
        return docs, total

    @staticmethod
    def delete_document(db: Session, doc_id: str, org_id: str) -> bool:
        """Soft-delete a document and remove its vectors from ChromaDB."""
        doc = DocumentService.get_document(db, doc_id, org_id)
        if doc is None:
            return False

        # Remove vectors from ChromaDB
        KnowledgeBase.delete_document_chunks(org_id=org_id, document_id=doc_id)

        # Soft-delete in PostgreSQL
        doc.status = DocumentStatus.DELETED
        doc.updated_at = datetime.now(timezone.utc)
        db.flush()

        log.info("document_deleted", doc_id=doc_id, org_id=org_id)
        return True

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_type(filename: str) -> DocumentType | None:
        """Detect document type from filename extension."""
        if not filename:
            return None
        lower = filename.lower()
        for ext, doc_type in EXTENSION_MAP.items():
            if lower.endswith(ext):
                return doc_type
        return None
