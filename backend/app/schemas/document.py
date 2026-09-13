"""
SafeVision AI — Document / RAG Schemas (Phase 8)

Request/response contracts for the document and knowledge APIs.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ==============================================================================
# Request Schemas
# ==============================================================================

class DocumentUploadRequest(BaseModel):
    """Metadata for document upload (file content sent separately)."""
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None


class KnowledgeSearchRequest(BaseModel):
    """POST /api/knowledge/search request."""
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


# ==============================================================================
# Response Schemas
# ==============================================================================

class DocumentChunkResponse(BaseModel):
    """A document chunk."""
    id: str
    document_id: str
    chunk_index: int
    content: str
    char_count: int

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    """Single document response."""
    id: str
    org_id: str
    title: str
    description: str | None
    document_type: str
    filename: str
    file_size: int | None
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    """Document with chunks."""
    chunks: list[DocumentChunkResponse] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    """Paginated document list."""
    data: list[DocumentResponse]
    total: int
    page: int
    size: int


class KnowledgeSearchResult(BaseModel):
    """A single search result."""
    chunk_id: str
    content: str
    score: float
    metadata: dict = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    """Knowledge search response."""
    query: str
    results: list[KnowledgeSearchResult]
    total_results: int
