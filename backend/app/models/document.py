"""
SafeVision AI — Safety Document Model (Phase 8)

Stores metadata for uploaded safety documents and their processed chunks.
Documents belong to an organization (tenant isolation).

Vector embeddings are stored in ChromaDB (external vector store),
not in PostgreSQL, because pgvector extension is not available
on the current PostgreSQL 18.4 server.

The chunk records here store text + metadata; the corresponding
embedding vectors live in ChromaDB indexed by chunk_id.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentStatus(str, enum.Enum):
    """Document processing status."""
    PENDING = "pending"           # Uploaded, not yet processed
    PROCESSING = "processing"    # Currently being chunked/embedded
    READY = "ready"              # Fully processed and searchable
    FAILED = "failed"            # Processing failed
    DELETED = "deleted"          # Soft-deleted


class DocumentType(str, enum.Enum):
    """Supported document types."""
    TXT = "txt"
    MARKDOWN = "markdown"
    PDF = "pdf"



class SafetyDocument(Base):
    """A safety document uploaded by an organization."""
    __tablename__ = "safety_documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str] = mapped_column(
        SAEnum(DocumentType, name="document_type", create_constraint=True),
        nullable=False,
    )
    # Original filename as uploaded
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    # File size in bytes
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Processing status
    status: Mapped[str] = mapped_column(
        SAEnum(DocumentStatus, name="document_status", create_constraint=True),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True,
    )
    # Number of chunks after processing
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Processing metadata (errors, timing, etc.)
    processing_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Who uploaded this document
    uploaded_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    organization = relationship("Organization", backref="safety_documents")
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )
    uploader = relationship("User", backref="uploaded_documents")

    def __repr__(self) -> str:
        return f"<SafetyDocument(id={self.id}, title={self.title}, status={self.status})>"


class DocumentChunk(Base):
    """A text chunk from a processed safety document.

    The embedding vector is stored in ChromaDB, keyed by this chunk's ID.
    """
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("safety_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Character count
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Section/page metadata from the source document
    source_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Embedding dimension (for validation)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    document = relationship("SafetyDocument", back_populates="chunks")
    organization = relationship("Organization", backref="document_chunks")

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk(id={self.id}, doc={self.document_id}, "
            f"idx={self.chunk_index}, chars={self.char_count})>"
        )
