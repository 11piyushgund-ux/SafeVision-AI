"""
SafeVision AI — Document & Knowledge API Routes (Phase 8)

Endpoints:
  POST   /api/documents/upload     — Upload and ingest a safety document
  GET    /api/documents             — List documents
  GET    /api/documents/{id}        — Get document detail with chunks
  DELETE /api/documents/{id}        — Delete a document
  POST   /api/knowledge/search      — Semantic search over safety knowledge

All endpoints require authentication and enforce tenant isolation.
"""

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
)
from app.services.document_service import DocumentService
from app.services.knowledge_base import KnowledgeBase

router = APIRouter(tags=["Documents & Knowledge"])
log = structlog.get_logger()


# ==============================================================================
# POST /api/documents/upload — Upload Document
# ==============================================================================

@router.post(
    "/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Safety Document",
    description="Upload and ingest a safety document. Requires documents.upload permission.",
)
async def upload_document(
    file: UploadFile = File(..., description="Safety document file (.txt, .md, .pdf)"),

    title: str = Form(..., min_length=1, max_length=500),
    description: str | None = Form(None),
    current_user: User = Depends(require_permission("documents.upload")),
    db: Session = Depends(get_db),
):
    """Upload a safety document for ingestion into the knowledge base."""
    # Read file content
    content = await file.read()

    try:
        doc = DocumentService.ingest(
            db=db,
            org_id=current_user.org_id,
            filename=file.filename or "unknown.txt",
            content=content,
            title=title,
            description=description,
            uploaded_by=current_user.id,
        )
        db.commit()
        db.refresh(doc)
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None
    except Exception as e:
        db.rollback()
        log.error("document_upload_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed",
        ) from None

    return DocumentResponse.model_validate(doc)


# ==============================================================================
# GET /api/documents — List Documents
# ==============================================================================

@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List Documents",
    description="List safety documents in the organization. Requires documents.view permission.",
)
def list_documents(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_permission("documents.view")),
    db: Session = Depends(get_db),
):
    """List safety documents for the authenticated user's org."""
    docs, total = DocumentService.list_documents(
        db=db,
        org_id=current_user.org_id,
        page=page,
        size=size,
    )

    return DocumentListResponse(
        data=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        size=size,
    )


# ==============================================================================
# GET /api/documents/{id} — Document Detail
# ==============================================================================

@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Get Document",
    description="Get document detail with chunks. Requires documents.view permission.",
)
def get_document(
    document_id: str,
    current_user: User = Depends(require_permission("documents.view")),
    db: Session = Depends(get_db),
):
    """Get a document by ID with its chunks."""
    doc = DocumentService.get_document(db, document_id, current_user.org_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentDetailResponse(
        **DocumentResponse.model_validate(doc).model_dump(),
        chunks=[DocumentChunkResponse.model_validate(c) for c in doc.chunks],
    )


# ==============================================================================
# DELETE /api/documents/{id} — Delete Document
# ==============================================================================

@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Document",
    description="Delete a safety document and its vectors. Requires documents.delete permission.",
)
def delete_document(
    document_id: str,
    current_user: User = Depends(require_permission("documents.delete")),
    db: Session = Depends(get_db),
):
    """Soft-delete a document and remove its vectors."""
    deleted = DocumentService.delete_document(db, document_id, current_user.org_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    db.commit()


# ==============================================================================
# POST /api/knowledge/search — Semantic Search
# ==============================================================================

@router.post(
    "/knowledge/search",
    response_model=KnowledgeSearchResponse,
    summary="Search Safety Knowledge",
    description="Semantic search over safety documents. Requires ai.view permission.",
)
def search_knowledge(
    body: KnowledgeSearchRequest,
    current_user: User = Depends(require_permission("ai.view")),
):
    """Search the organization's safety knowledge base."""
    results = KnowledgeBase.search(
        org_id=current_user.org_id,
        query_text=body.query,
        top_k=body.top_k,
    )

    return KnowledgeSearchResponse(
        query=body.query,
        results=[
            KnowledgeSearchResult(
                chunk_id=r["chunk_id"],
                content=r["content"],
                score=r["score"],
                metadata=r["metadata"],
            )
            for r in results
        ],
        total_results=len(results),
    )
