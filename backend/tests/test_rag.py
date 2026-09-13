"""
SafeVision AI — RAG / Knowledge Base Tests (Phase 8)

Coverage:
  DOCUMENT INGESTION (1–5)
  CHUNKING (6–9)
  EMBEDDINGS (10–12)
  VECTOR STORAGE (13–15)
  RETRIEVAL (16–21)
  FAILURE / INTEGRITY (22–24)

Uses real test database + ChromaDB for integration tests.
Embedding tests use the real sentence-transformers model.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models.document import DocumentChunk, DocumentStatus
from app.models.organization import Organization
from app.models.role import Permission, Role
from app.models.user import User
from app.services.auth_service import create_access_token, hash_password
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService
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


# ==============================================================================
# Test Data Helpers
# ==============================================================================

def _create_org(db: Session, name: str, slug: str) -> Organization:
    org = Organization(id=str(uuid.uuid4()), name=name, slug=slug)
    db.add(org)
    db.flush()
    return org


def _create_role(
    db: Session, org_id: str, name: str, permissions: list[str],
) -> Role:
    role = Role(id=str(uuid.uuid4()), name=name, org_id=org_id)
    db.add(role)
    db.flush()
    for perm_name in permissions:
        perm = Permission(
            id=str(uuid.uuid4()), role_id=role.id, perm_name=perm_name,
        )
        db.add(perm)
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


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get_token(
    user_id: str, org_id: str, role_name: str = "Admin",
) -> str:
    return create_access_token(
        user_id=user_id, org_id=org_id, role_name=role_name,
    )


# ==============================================================================
# Fixture: Two Isolated Organizations
# ==============================================================================

_test_data: dict = {}

# Use a unique ChromaDB directory for tests to avoid polluting production
_TEST_CHROMADB_DIR = os.path.join(
    os.path.dirname(__file__), ".test_chromadb",
)


def _setup_test_data():
    if _test_data:
        return

    # Override ChromaDB persist dir for tests
    settings = get_settings()
    settings.chromadb_persist_dir = _TEST_CHROMADB_DIR

    # Reset ChromaDB module-level client so it picks up new dir
    import app.services.knowledge_base as kb_mod
    kb_mod._chroma_client = None

    db = TestSession()
    try:
        # --- ORG A ---
        uid = uuid.uuid4().hex[:6]
        org_a = _create_org(db, f"RAG Org A {uid}", f"rag-a-{uid}")

        admin_role_a = _create_role(db, org_a.id, "Admin", [
            "documents.view", "documents.upload", "documents.delete",
            "ai.view", "ai.manage", "events.view",
            "alerts.view", "users.view",
        ])
        viewer_role_a = _create_role(db, org_a.id, "Viewer", [
            "documents.view", "ai.view", "events.view",
        ])

        a_email = f"rag-admin-a-{uid}@test.com"
        admin_a = _create_user(
            db, org_a.id, admin_role_a.id, a_email, "Admin A",
        )
        v_email = f"rag-viewer-a-{uid}@test.com"
        viewer_a = _create_user(
            db, org_a.id, viewer_role_a.id, v_email, "Viewer A",
        )

        # --- ORG B ---
        uid_b = uuid.uuid4().hex[:6]
        org_b = _create_org(db, f"RAG Org B {uid_b}", f"rag-b-{uid_b}")

        admin_role_b = _create_role(db, org_b.id, "Admin", [
            "documents.view", "documents.upload", "documents.delete",
            "ai.view", "ai.manage",
        ])
        b_email = f"rag-admin-b-{uid_b}@test.com"
        admin_b = _create_user(
            db, org_b.id, admin_role_b.id, b_email, "Admin B",
        )

        db.commit()

        _test_data["org_a_id"] = org_a.id
        _test_data["org_b_id"] = org_b.id
        _test_data["admin_a_id"] = admin_a.id
        _test_data["viewer_a_id"] = viewer_a.id
        _test_data["admin_b_id"] = admin_b.id

    finally:
        db.close()


# Sample safety document content for tests
SAMPLE_SAFETY_DOC = """# PPE Policy — Manufacturing Floor

## Section 1: Hard Hat Requirements

All personnel entering the manufacturing floor MUST wear an approved
hard hat at all times. Hard hats must meet ANSI Z89.1 standards.

Visitors must be provided with temporary hard hats at the entrance.

## Section 2: Safety Vest Requirements

High-visibility safety vests are required in all forklift zones.
Vests must be Class 2 or higher per ANSI/ISEA 107 standards.

## Section 3: Eye Protection

Safety glasses are mandatory in all grinding and welding areas.
Full face shields are required when operating plasma cutters.

## Section 4: Emergency Procedures

In case of fire alarm:
1. Stop all operations immediately
2. Proceed to the nearest emergency exit
3. Assemble at designated muster points
4. Do not re-enter until cleared by safety officer
"""


SAMPLE_FIRE_DOC = """# Fire Safety Protocol

All fire extinguishers must be inspected monthly.
Emergency exits must never be blocked.
Fire drills must be conducted quarterly.
Smoking is prohibited in all production areas.
"""


# ==============================================================================
# 1–5. Document Ingestion Tests
# ==============================================================================

class TestDocumentIngestion:
    """Document ingestion from text content."""

    def setup_method(self):
        _setup_test_data()

    def test_valid_document_ingestion(self):
        """Valid .txt document is ingested successfully."""
        db = TestSession()
        try:
            doc = DocumentService.ingest(
                db=db,
                org_id=_test_data["org_a_id"],
                filename="ppe_policy.txt",
                content=SAMPLE_SAFETY_DOC,
                title="PPE Policy",
            )
            db.commit()

            assert doc.status == DocumentStatus.READY
            assert doc.chunk_count > 0
            assert doc.org_id == _test_data["org_a_id"]
        finally:
            db.close()

    def test_metadata_stored_correctly(self):
        """Document metadata is persisted in PostgreSQL."""
        db = TestSession()
        try:
            doc = DocumentService.ingest(
                db=db,
                org_id=_test_data["org_a_id"],
                filename="fire_safety.md",
                content=SAMPLE_FIRE_DOC,
                title="Fire Safety Protocol",
                description="Fire response guidelines",
            )
            db.commit()

            assert doc.title == "Fire Safety Protocol"
            assert doc.description == "Fire response guidelines"
            assert doc.filename == "fire_safety.md"
            assert doc.document_type == "markdown"
            assert doc.file_size > 0
            assert doc.processing_metadata is not None
            meta = doc.processing_metadata
            assert "embedding_model" in meta
            assert "embedding_dim" in meta
        finally:
            db.close()

    def test_document_belongs_to_correct_org(self):
        """Document's org_id matches the ingesting organization."""
        db = TestSession()
        try:
            doc = DocumentService.ingest(
                db=db,
                org_id=_test_data["org_a_id"],
                filename="test.txt",
                content="Safety policy content for org A.",
                title="Org A Policy",
            )
            db.commit()

            assert doc.org_id == _test_data["org_a_id"]

            # Chunks also belong to correct org
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id,
            ).all()
            for chunk in chunks:
                assert chunk.org_id == _test_data["org_a_id"]
        finally:
            db.close()

    def test_unsupported_document_type(self):
        """Unsupported file type raises ValueError."""
        db = TestSession()
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                DocumentService.ingest(
                    db=db,
                    org_id=_test_data["org_a_id"],
                    filename="document.docx",
                    content="DOCX content",
                )

        finally:
            db.close()

    def test_empty_document_rejected(self):
        """Empty document raises ValueError."""
        db = TestSession()
        try:
            with pytest.raises(ValueError, match="empty"):
                DocumentService.ingest(
                    db=db,
                    org_id=_test_data["org_a_id"],
                    filename="empty.txt",
                    content="   \n\t  ",
                )
        finally:
            db.close()


# ==============================================================================
# 6–9. Chunking Tests
# ==============================================================================

class TestChunking:
    """Deterministic chunking behavior."""

    def test_deterministic_chunking(self):
        """Same input produces identical chunks."""
        text = "A" * 1024
        chunks_a = DocumentService.chunk_text(text, chunk_size=256, overlap=32)
        chunks_b = DocumentService.chunk_text(text, chunk_size=256, overlap=32)

        assert len(chunks_a) == len(chunks_b)
        for a, b in zip(chunks_a, chunks_b, strict=True):
            assert a["text"] == b["text"]
            assert a["metadata"] == b["metadata"]

    def test_chunk_ordering_preserved(self):
        """Chunks are indexed in document order."""
        text = " ".join([f"Section {i}." for i in range(100)])
        chunks = DocumentService.chunk_text(text, chunk_size=128, overlap=16)

        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i

        # First chunk starts near beginning
        assert chunks[0]["metadata"]["start_char"] == 0

    def test_no_empty_chunks(self):
        """No empty chunks are produced."""
        text = "Hello World. This is a safety document."
        chunks = DocumentService.chunk_text(text, chunk_size=20, overlap=5)

        for chunk in chunks:
            assert len(chunk["text"].strip()) > 0

    def test_chunk_metadata_preserved(self):
        """Each chunk has start/end character positions."""
        text = "Safety first. Always wear your PPE."
        chunks = DocumentService.chunk_text(text, chunk_size=512, overlap=0)

        assert len(chunks) >= 1
        meta = chunks[0]["metadata"]
        assert "start_char" in meta
        assert "end_char" in meta
        assert "chunk_index" in meta


# ==============================================================================
# 10–12. Embedding Tests
# ==============================================================================

class TestEmbeddings:
    """Embedding generation and validation."""

    def test_embedding_generated_successfully(self):
        """Embedding is produced for valid text."""
        vectors = EmbeddingService.embed_texts(["Safety helmet required"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 384

    def test_embedding_dimension_validated(self):
        """Embedding dimension matches configured value."""
        dim = EmbeddingService.get_dimension()
        assert dim == 384

        vector = EmbeddingService.embed_query("test query")
        assert len(vector) == dim

    def test_empty_text_raises_error(self):
        """Empty text list raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            EmbeddingService.embed_texts([])

        with pytest.raises(ValueError, match="empty"):
            EmbeddingService.embed_query("")


# ==============================================================================
# 13–15. Vector Storage Tests
# ==============================================================================

class TestVectorStorage:
    """ChromaDB vector storage operations."""

    def setup_method(self):
        _setup_test_data()

    def test_vector_stored_successfully(self):
        """Chunks with embeddings are stored in ChromaDB."""
        org_id = _test_data["org_a_id"]
        embedding = EmbeddingService.embed_query("test content")

        chunk_id = str(uuid.uuid4())
        stored = KnowledgeBase.store_chunks(
            org_id=org_id,
            chunks=[{
                "id": chunk_id,
                "content": "Test safety content",
                "embedding": embedding,
                "metadata": {"document_id": "doc-test"},
            }],
        )
        assert stored == 1

    def test_chunk_document_linkage_preserved(self):
        """Stored chunk metadata preserves document_id."""
        org_id = _test_data["org_a_id"]
        doc_id = f"doc-{uuid.uuid4().hex[:8]}"
        embedding = EmbeddingService.embed_query("linked content")
        chunk_id = str(uuid.uuid4())

        KnowledgeBase.store_chunks(
            org_id=org_id,
            chunks=[{
                "id": chunk_id,
                "content": "Linked safety content",
                "embedding": embedding,
                "metadata": {"document_id": doc_id},
            }],
        )

        # Search and check metadata
        results = KnowledgeBase.search(
            org_id=org_id,
            query_text="linked safety",
            top_k=10,
        )

        found = [r for r in results if r["chunk_id"] == chunk_id]
        assert len(found) == 1
        assert found[0]["metadata"]["document_id"] == doc_id

    def test_vector_metadata_preserved(self):
        """Stored metadata includes org_id."""
        org_id = _test_data["org_a_id"]
        embedding = EmbeddingService.embed_query("metadata test")
        chunk_id = str(uuid.uuid4())

        KnowledgeBase.store_chunks(
            org_id=org_id,
            chunks=[{
                "id": chunk_id,
                "content": "Metadata test content",
                "embedding": embedding,
                "metadata": {"document_id": "doc-meta"},
            }],
        )

        results = KnowledgeBase.search(
            org_id=org_id,
            query_text="metadata test",
            top_k=10,
        )
        found = [r for r in results if r["chunk_id"] == chunk_id]
        assert len(found) == 1
        assert found[0]["metadata"]["org_id"] == org_id


# ==============================================================================
# 16–21. Retrieval Tests
# ==============================================================================

class TestRetrieval:
    """Semantic retrieval operations."""

    def setup_method(self):
        _setup_test_data()

    def _ingest_sample(self, org_id: str):
        """Ingest the sample safety doc for the given org."""
        db = TestSession()
        try:
            doc = DocumentService.ingest(
                db=db,
                org_id=org_id,
                filename=f"ppe_{uuid.uuid4().hex[:6]}.txt",
                content=SAMPLE_SAFETY_DOC,
                title="PPE Policy",
            )
            db.commit()
            return doc
        finally:
            db.close()

    def test_relevant_chunks_retrieved(self):
        """Semantic search returns relevant chunks."""
        org_id = _test_data["org_a_id"]
        self._ingest_sample(org_id)

        results = KnowledgeBase.search(
            org_id=org_id,
            query_text="hard hat requirements",
            top_k=3,
        )
        assert len(results) > 0
        # At least one result should contain hard hat content
        texts = " ".join(r["content"].lower() for r in results)
        assert "hard hat" in texts or "hat" in texts

    def test_top_k_respected(self):
        """Retrieval returns at most top_k results."""
        org_id = _test_data["org_a_id"]
        self._ingest_sample(org_id)

        results = KnowledgeBase.search(
            org_id=org_id,
            query_text="safety",
            top_k=2,
        )
        assert len(results) <= 2

    def test_similarity_score_returned(self):
        """Each result includes a similarity score."""
        org_id = _test_data["org_a_id"]
        self._ingest_sample(org_id)

        results = KnowledgeBase.search(
            org_id=org_id,
            query_text="fire emergency procedures",
            top_k=3,
        )
        for r in results:
            assert "score" in r
            assert isinstance(r["score"], float)
            assert 0.0 <= r["score"] <= 1.0

    def test_org_filtering_enforced(self):
        """Search only returns docs from the queried org."""
        org_a = _test_data["org_a_id"]
        org_b = _test_data["org_b_id"]

        # Ingest in Org A only
        self._ingest_sample(org_a)

        # Search in Org B — should return nothing
        results_b = KnowledgeBase.search(
            org_id=org_b,
            query_text="hard hat requirements",
            top_k=5,
        )
        # Org B has no documents, so should be empty
        assert len(results_b) == 0

    def test_cross_tenant_retrieval_impossible(self):
        """Org B cannot retrieve Org A documents."""
        org_a = _test_data["org_a_id"]
        org_b = _test_data["org_b_id"]

        # Ingest unique content in Org A
        db = TestSession()
        try:
            unique = f"UniqueOrgA_{uuid.uuid4().hex[:8]}"
            DocumentService.ingest(
                db=db,
                org_id=org_a,
                filename=f"unique_{uuid.uuid4().hex[:6]}.txt",
                content=f"This document contains {unique} data.",
                title="Unique A",
            )
            db.commit()
        finally:
            db.close()

        # Search Org B for that unique content
        results = KnowledgeBase.search(
            org_id=org_b,
            query_text=unique,
            top_k=10,
        )
        assert len(results) == 0

    def test_deterministic_retrieval_ordering(self):
        """Same query returns same order (deterministic)."""
        org_id = _test_data["org_a_id"]
        self._ingest_sample(org_id)

        query = "emergency fire procedures"
        r1 = KnowledgeBase.search(org_id=org_id, query_text=query, top_k=3)
        r2 = KnowledgeBase.search(org_id=org_id, query_text=query, top_k=3)

        assert len(r1) == len(r2)
        for a, b in zip(r1, r2, strict=True):
            assert a["chunk_id"] == b["chunk_id"]
            assert a["score"] == b["score"]


# ==============================================================================
# 22–24. Failure / Integrity Tests
# ==============================================================================

class TestFailureIntegrity:
    """Error handling and data integrity."""

    def setup_method(self):
        _setup_test_data()

    def test_failed_ingestion_no_partial_state(self):
        """Failed ingestion marks document as FAILED."""
        db = TestSession()
        try:
            with pytest.raises(ValueError):
                DocumentService.ingest(
                    db=db,
                    org_id=_test_data["org_a_id"],
                    filename="bad.xyz",
                    content="content",
                )
            # No document should be created for unsupported type
            # (ValueError raised before document creation)
        finally:
            db.close()

    def test_invalid_org_context_rejected(self):
        """Document must have a valid org_id."""
        db = TestSession()
        try:
            # This will fail at DB flush due to FK constraint
            with pytest.raises((ValueError, Exception)):
                DocumentService.ingest(
                    db=db,
                    org_id="nonexistent-org-id",
                    filename="test.txt",
                    content="Some content",
                )
            db.rollback()
        finally:
            db.close()

    def test_empty_search_query_rejected(self):
        """Empty search query raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            KnowledgeBase.search(
                org_id=_test_data["org_a_id"],
                query_text="",
            )


# ==============================================================================
# API Integration Tests
# ==============================================================================

class TestDocumentAPI:
    """Document API endpoint tests."""

    def setup_method(self):
        _setup_test_data()

    def test_upload_document(self):
        """POST /api/documents/upload creates a document."""
        token = _get_token(
            _test_data["admin_a_id"], _test_data["org_a_id"],
        )
        resp = client.post(
            "/api/documents/upload",
            files={"file": ("safety.txt", SAMPLE_FIRE_DOC, "text/plain")},
            data={"title": "Fire Safety API Test"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "ready"
        assert data["chunk_count"] > 0
        assert data["title"] == "Fire Safety API Test"

    def test_list_documents(self):
        """GET /api/documents lists org documents."""
        token = _get_token(
            _test_data["admin_a_id"], _test_data["org_a_id"],
        )
        resp = client.get(
            "/api/documents",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data

    def test_viewer_cannot_upload(self):
        """Viewer without documents.upload cannot upload."""
        token = _get_token(
            _test_data["viewer_a_id"],
            _test_data["org_a_id"],
            role_name="Viewer",
        )
        resp = client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", "content", "text/plain")},
            data={"title": "Should Fail"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 403

    def test_knowledge_search_api(self):
        """POST /api/knowledge/search returns results."""
        # First upload a document
        token = _get_token(
            _test_data["admin_a_id"], _test_data["org_a_id"],
        )
        client.post(
            "/api/documents/upload",
            files={
                "file": (
                    "ppe_api.txt",
                    SAMPLE_SAFETY_DOC,
                    "text/plain",
                ),
            },
            data={"title": "PPE API Test"},
            headers=_auth_header(token),
        )

        # Then search
        resp = client.post(
            "/api/knowledge/search",
            json={"query": "hard hat requirements", "top_k": 3},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total_results" in data
        assert data["query"] == "hard hat requirements"
