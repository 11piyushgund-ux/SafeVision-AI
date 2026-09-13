"""
SafeVision AI — AI Insight Model

AI-generated insights from the RAG pipeline. These are responses from
the LLM that analyze safety data, patterns, and provide recommendations.

Note: pgvector extension is NOT yet installed on the database server.
Architecture decision LOCKED IN: pgvector on the same PostgreSQL instance.
The embedding_vector column is deferred until Phase 21 (AI/RAG Pipeline).
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InsightType(str, enum.Enum):
    """Type of AI insight."""
    SAFETY_ANALYSIS = "safety_analysis"
    TREND_REPORT = "trend_report"
    RECOMMENDATION = "recommendation"
    RISK_ASSESSMENT = "risk_assessment"
    QUERY_RESPONSE = "query_response"


class InsightStatus(str, enum.Enum):
    """Insight review status."""
    PENDING = "pending"
    REVIEWED = "reviewed"
    ACTED_ON = "acted_on"
    DISMISSED = "dismissed"


class AiInsight(Base):
    __tablename__ = "ai_insights"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    insight_type: Mapped[str] = mapped_column(
        SAEnum(InsightType, name="insight_type", create_constraint=True),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # What query or context triggered this insight
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Source data references (event IDs, pattern IDs, date ranges)
    source_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # LLM metadata (model used, tokens, latency)
    llm_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum(InsightStatus, name="insight_status", create_constraint=True),
        default=InsightStatus.PENDING,
        nullable=False,
    )
    # embedding_vector column deferred to Phase 21 when pgvector is installed.
    # Architecture decision: pgvector on same PostgreSQL instance.
    # DO NOT change this decision without explicit approval.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    organization = relationship("Organization", backref="ai_insights")

    def __repr__(self) -> str:
        return f"<AiInsight(id={self.id}, type={self.insight_type})>"
