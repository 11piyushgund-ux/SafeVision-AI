"""
SafeVision AI — PDF Document Ingestion Tests (Phase 8A)

Coverage:
  1. PDF type detection
  2. Multi-page PDF text extraction
  3. Image-only/scanned PDF rejection (OCR not enabled)
  4. Corrupt PDF rejection
  5. Page-aware chunking & provenance (source_metadata & ChromaDB metadata)
  6. PDF semantic retrieval & score verification
  7. Tenant isolation for PDF documents
  8. API endpoint upload (POST /api/documents/upload)
  9. Backward compatibility with TXT and Markdown
"""

import io
import os
import uuid

import pypdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models.document import (
    DocumentChunk,
    DocumentStatus,
    DocumentType,
)
from app.models.organization import Organization
from app.models.role import Permission, Role
from app.models.user import User
from app.services.auth_service import create_access_token, hash_password
from app.services.document_service import DocumentService
from app.services.knowledge_base import KnowledgeBase

# ==============================================================================
# Test Database Setup
# ==============================================================================

settings = get_settings()
test_engine = create_engine(settings.database_url, echo=False)
TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def _override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)

_TEST_CHROMADB_DIR = os.path.join(
    os.path.dirname(__file__), ".test_chromadb_pdf",
)


# ==============================================================================
# Helper Functions
# ==============================================================================

def _create_org(db: Session, name: str, slug: str) -> Organization:
    org = Organization(id=str(uuid.uuid4()), name=name, slug=slug)
    db.add(org)
    db.flush()
    return org


def _create_role(db: Session, org_id: str, name: str, permissions: list[str]) -> Role:
    role = Role(id=str(uuid.uuid4()), name=name, org_id=org_id)
    db.add(role)
    db.flush()
    for perm in permissions:
        db.add(Permission(id=str(uuid.uuid4()), role_id=role.id, perm_name=perm))
    db.flush()
    return role


def _create_user(
    db: Session, org_id: str, role_id: str, email: str,
    name: str = "Test User", password: str = "testpassword123",
) -> User:
    user = User(
        id=str(uuid.uuid4()), org_id=org_id, email=email,
        name=name, pwd_hash=hash_password(password), role_id=role_id,
    )
    db.add(user)
    db.flush()
    return user


def _get_token(user_id: str, org_id: str, role_name: str = "Admin") -> str:
    return create_access_token(user_id=user_id, org_id=org_id, role_name=role_name)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_sample_pdf_bytes() -> bytes:
    """Create a sample 2-page PDF with searchable text using real test docs."""
    real_doc_path = r"D:\SafeVision-AI\RAG_test_docs\OSHA3151.pdf"
    if os.path.exists(real_doc_path):
        reader = pypdf.PdfReader(real_doc_path)
        writer = pypdf.PdfWriter()
        writer.add_page(reader.pages[0])
        writer.add_page(reader.pages[1])
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    # Fallback to pure memory PDF if test doc path is absent
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(autouse=True)
def setup_chromadb(monkeypatch):
    """Use isolated ChromaDB directory for tests."""
    monkeypatch.setattr(settings, "chromadb_persist_dir", _TEST_CHROMADB_DIR)
    yield
    # Cleanup collections
    import shutil
    if os.path.exists(_TEST_CHROMADB_DIR):
        shutil.rmtree(_TEST_CHROMADB_DIR, ignore_errors=True)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_org(db: Session):
    uid = uuid.uuid4().hex[:8]
    org = _create_org(db, f"PDF Test Org {uid}", f"pdf-org-{uid}")
    role = _create_role(db, org.id, "Admin", [
        "documents.upload", "documents.view", "documents.delete",
        "ai.manage", "ai.view",
    ])
    user = _create_user(db, org.id, role.id, f"admin-{uid}@test.com")
    db.commit()
    return {"org": org, "user": user, "token": _get_token(user.id, org.id)}


# ==============================================================================
# Tests
# ==============================================================================

class TestPDFDetection:
    """Tests for file extension and type detection."""

    def test_pdf_extension_detected(self):
        assert DocumentService._detect_type("safety_manual.pdf") == DocumentType.PDF
        assert DocumentService._detect_type("SAFETY_MANUAL.PDF") == DocumentType.PDF
        assert DocumentService._detect_type("path/to/doc.pdf") == DocumentType.PDF

    def test_existing_extensions_preserved(self):
        assert DocumentService._detect_type("doc.txt") == DocumentType.TXT
        assert DocumentService._detect_type("doc.md") == DocumentType.MARKDOWN
        assert DocumentService._detect_type("doc.markdown") == DocumentType.MARKDOWN
        assert DocumentService._detect_type("doc.docx") is None


class TestPDFExtraction:
    """Tests for page-by-page text extraction."""

    def test_extract_text_from_pdf_success(self):
        pdf_bytes = _make_sample_pdf_bytes()
        pages = DocumentService.extract_text_from_pdf(pdf_bytes)
        assert len(pages) >= 1
        assert pages[0]["page_number"] == 1
        assert len(pages[0]["text"]) > 0

    def test_extract_text_from_blank_pdf_raises(self):
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=100, height=100)
        buf = io.BytesIO()
        writer.write(buf)
        blank_pdf_bytes = buf.getvalue()

        with pytest.raises(ValueError, match="PDF contains no extractable text; OCR is not currently enabled"):
            DocumentService.extract_text_from_pdf(blank_pdf_bytes)

    def test_extract_text_from_corrupt_bytes_raises(self):
        corrupt_bytes = b"Not a valid PDF file at all"
        with pytest.raises(ValueError, match="Failed to parse PDF document"):
            DocumentService.extract_text_from_pdf(corrupt_bytes)


class TestPDFIngestionAndProvenance:
    """Tests for full PDF ingestion pipeline and page provenance."""

    def test_pdf_ingestion_stores_chunks_and_page_provenance(self, db: Session, test_org: dict):
        org_id = test_org["org"].id
        pdf_bytes = _make_sample_pdf_bytes()

        doc = DocumentService.ingest(
            db=db,
            org_id=org_id,
            filename="osha_ppe_sample.pdf",
            content=pdf_bytes,
            title="OSHA PPE Sample",
        )
        db.commit()

        assert doc.status == DocumentStatus.READY
        assert doc.document_type == DocumentType.PDF
        assert doc.chunk_count > 0
        assert doc.processing_metadata is not None
        assert "page_count" in doc.processing_metadata

        # Verify chunks have page_number in source_metadata
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
        assert len(chunks) == doc.chunk_count
        for c in chunks:
            assert "page_number" in c.source_metadata
            assert c.source_metadata["page_number"] >= 1

        # Verify ChromaDB vectors
        vector_count = KnowledgeBase.get_collection_count(org_id)
        assert vector_count == doc.chunk_count

        # Clean up
        DocumentService.delete_document(db, doc.id, org_id)
        db.commit()

    def test_pdf_semantic_retrieval_returns_page_metadata(self, db: Session, test_org: dict):
        org_id = test_org["org"].id
        pdf_bytes = _make_sample_pdf_bytes()

        doc = DocumentService.ingest(
            db=db,
            org_id=org_id,
            filename="osha_ppe_sample.pdf",
            content=pdf_bytes,
            title="OSHA PPE Sample",
        )
        db.commit()

        results = KnowledgeBase.search(org_id=org_id, query_text="personal protective equipment", top_k=2)
        assert len(results) > 0
        top_result = results[0]
        assert "page_number" in top_result["metadata"]
        assert top_result["metadata"]["document_title"] == "OSHA PPE Sample"
        assert top_result["score"] > 0

        # Clean up
        DocumentService.delete_document(db, doc.id, org_id)
        db.commit()

    def test_pdf_tenant_isolation(self, db: Session, test_org: dict):
        org_a_id = test_org["org"].id
        uid = uuid.uuid4().hex[:8]
        org_b = _create_org(db, f"Org B {uid}", f"org-b-{uid}")
        db.commit()

        pdf_bytes = _make_sample_pdf_bytes()
        doc = DocumentService.ingest(
            db=db,
            org_id=org_a_id,
            filename="osha_ppe_sample.pdf",
            content=pdf_bytes,
            title="OSHA PPE Sample",
        )
        db.commit()

        # Org B should get 0 results when searching for Org A's document
        org_b_results = KnowledgeBase.search(org_id=org_b.id, query_text="personal protective equipment")
        assert len(org_b_results) == 0

        # Clean up
        DocumentService.delete_document(db, doc.id, org_a_id)
        db.commit()


class TestPDFAPI:
    """Tests for PDF upload and management via FastAPI endpoints."""

    def test_api_upload_pdf_success(self, test_org: dict):
        pdf_bytes = _make_sample_pdf_bytes()
        headers = _auth_header(test_org["token"])

        response = client.post(
            "/api/documents/upload",
            files={"file": ("safety_test.pdf", pdf_bytes, "application/pdf")},
            data={"title": "API Uploaded PDF"},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["document_type"] == "pdf"
        assert data["status"] == "ready"
        assert data["chunk_count"] > 0

        # Cleanup via delete endpoint
        doc_id = data["id"]
        del_resp = client.delete(f"/api/documents/{doc_id}", headers=headers)
        assert del_resp.status_code == 204


    def test_api_upload_scanned_blank_pdf_fails(self, test_org: dict):
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=100, height=100)
        buf = io.BytesIO()
        writer.write(buf)
        blank_pdf_bytes = buf.getvalue()

        headers = _auth_header(test_org["token"])
        response = client.post(
            "/api/documents/upload",
            files={"file": ("blank.pdf", blank_pdf_bytes, "application/pdf")},
            data={"title": "Blank Scanned PDF"},
            headers=headers,
        )
        assert response.status_code == 400
        assert "PDF contains no extractable text" in response.json()["detail"]


class TestBackwardCompatibility:
    """Ensures TXT and Markdown files continue working unchanged."""

    def test_txt_and_md_still_work(self, db: Session, test_org: dict):
        org_id = test_org["org"].id

        txt_content = "General Safety Rule: All employees must wear hard hats in designated hard hat areas."
        doc_txt = DocumentService.ingest(
            db=db, org_id=org_id, filename="rules.txt", content=txt_content, title="Rules TXT",
        )
        assert doc_txt.status == DocumentStatus.READY
        assert doc_txt.document_type == DocumentType.TXT

        md_content = "# Emergency Response\nIn case of evacuation, assemble at Zone 4."
        doc_md = DocumentService.ingest(
            db=db, org_id=org_id, filename="evac.md", content=md_content, title="Evacuation MD",
        )
        assert doc_md.status == DocumentStatus.READY
        assert doc_md.document_type == DocumentType.MARKDOWN

        # Clean up
        DocumentService.delete_document(db, doc_txt.id, org_id)
        DocumentService.delete_document(db, doc_md.id, org_id)
        db.commit()
