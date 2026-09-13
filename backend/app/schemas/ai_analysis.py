"""
SafeVision AI — AI Analysis Schemas (Phase 9)

Structured output contracts for AI safety reasoning.
Validates LLM responses before returning to consumers.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# Structured Action Item (Phase 14F)
# ==============================================================================

class SafetyActionItem(BaseModel):
    """
    Structured safety action item with operational guidance.

    Provides specific title, execution procedure, operational rationale,
    assigned functional role, target timeframe, and expected outcome.
    """

    title: str = Field(..., description="Concise action title (e.g., 'Isolate Local Electrical Panel')")
    procedure: str = Field(..., description="Detailed step-by-step procedural execution guidance")
    rationale: str = Field(default="", description="Operational rationale explaining why this action is required")
    role: str = Field(default="Floor Supervisor", description="Assigned functional role (not personal names)")
    timeframe: str = Field(default="Immediate (<15m)", description="Operational target timeframe")
    expected_outcome: str = Field(default="", description="Measurable expected safety outcome upon completion")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.procedure == other or self.title == other
        if isinstance(other, SafetyActionItem):
            return (
                self.title == other.title
                and self.procedure == other.procedure
                and self.rationale == other.rationale
                and self.role == other.role
                and self.timeframe == other.timeframe
                and self.expected_outcome == other.expected_outcome
            )
        return False


# ==============================================================================
# AI Analysis Result (Validated LLM Output)
# ==============================================================================

def _format_visual_observation(item: object) -> str | None:
    """Format a visual observation item (string, dict, or scalar) into a readable string."""
    if isinstance(item, str):
        text = item.strip()
        return text if text else None

    if isinstance(item, dict):
        raw_title = (
            item.get("title")
            or item.get("label")
            or item.get("hazard")
            or item.get("name")
        )
        raw_details = (
            item.get("details")
            or item.get("description")
            or item.get("observation")
            or item.get("text")
            or item.get("content")
            or item.get("note")
        )

        title = str(raw_title).strip() if raw_title is not None else ""
        if isinstance(raw_details, list):
            details = ", ".join(str(d).strip() for d in raw_details if d is not None)
        elif raw_details is not None:
            details = str(raw_details).strip()
        else:
            details = ""

        if title and details:
            if details.lower().startswith(title.lower()):
                return details
            return f"{title}: {details}"
        if details:
            return details
        if title:
            return title

        # Generic fallback for any other dictionary keys
        parts: list[str] = []
        for k, v in item.items():
            if v is not None:
                v_str = str(v).strip()
                if v_str:
                    k_str = str(k).strip()
                    if v_str.lower().startswith(k_str.lower()):
                        parts.append(v_str)
                    else:
                        parts.append(f"{k_str}: {v_str}")
        if parts:
            return "; ".join(parts)
        return None

    if item is not None:
        text = str(item).strip()
        return text if text else None

    return None


class AIAnalysisResult(BaseModel):
    """
    Validated structured AI safety analysis result.

    Produced by the AI Orchestrator after LLM generation + validation.
    """

    summary: str = Field(
        ..., description="Brief 1-2 sentence summary of the safety situation",
    )
    risk_explanation: str = Field(
        ..., description="Explanation of the deterministic risk level",
    )
    contributing_factors: list[str] = Field(
        default_factory=list, description="Contributing factors identified by AI",
    )
    safety_policy_guidance: str = Field(
        default="No specific policy documents available",
        description="Relevant safety policy guidance from RAG context",
    )
    historical_context: str = Field(
        default="No historical context available",
        description="Analysis of historical patterns",
    )
    recommended_actions: list[str] = Field(
        default_factory=list, description="Recommended safety actions (flat backward-compatible string list)",
    )
    # Provider metadata
    provider: str = Field(..., description="LLM provider that generated this (gemini/ollama/openrouter)")
    model: str = Field(..., description="Model used for generation")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Timestamp when this analysis was generated",
    )
    # Phase 14 — multimodal visual analysis (optional, backward-compatible)
    visual_observations: list[str] = Field(
        default_factory=list,
        description="Visual observations from the evidence image",
    )
    visual_validation: dict | None = Field(
        default=None,
        description="AI visual validation of machine detection (advisory only)",
    )
    # Phase 14d/14f — structured intelligence fields (backward-compatible)
    hazard_interpretation: str = Field(
        default="",
        description="AI interpretation of what hazard is present, physical mechanism, and escalation risks",
    )
    immediate_actions: list[SafetyActionItem] = Field(
        default_factory=list,
        description="Actions required immediately (within minutes to hours)",
    )
    investigation_actions: list[SafetyActionItem] = Field(
        default_factory=list,
        description="Actions required to determine root cause and preserve evidence",
    )
    preventive_actions: list[SafetyActionItem] = Field(
        default_factory=list,
        description="Long-term corrective and systemic preventive measures",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Explicit statements of what is unknown or cannot be determined",
    )
    provider_metadata: dict = Field(
        default_factory=dict,
        exclude=True,
        description="Internal provider and fallback execution metadata",
    )

    @field_validator("immediate_actions", "investigation_actions", "preventive_actions", mode="before")
    @classmethod
    def _coerce_action_items(cls, value: object) -> list[SafetyActionItem]:
        if not value:
            return []
        if isinstance(value, (str, dict, SafetyActionItem)):
            value = [value]
        if not isinstance(value, list):
            return []
        coerced: list[SafetyActionItem] = []
        for item in value:
            if isinstance(item, SafetyActionItem):
                coerced.append(item)
            elif isinstance(item, dict):
                title = str(item.get("title") or "Safety Action").strip()
                procedure = str(item.get("procedure") or item.get("description") or title).strip()
                coerced.append(
                    SafetyActionItem(
                        title=title,
                        procedure=procedure,
                        rationale=str(item.get("rationale") or "").strip(),
                        role=str(item.get("role") or "Floor Supervisor").strip(),
                        timeframe=str(item.get("timeframe") or "Immediate (<15m)").strip(),
                        expected_outcome=str(item.get("expected_outcome") or "").strip(),
                    )
                )
            elif isinstance(item, str):
                text = item.strip()
                if not text:
                    continue
                title = text[:60] + ("..." if len(text) > 60 else "")
                procedure = text
                if ":" in text:
                    parts = text.split(":", 1)
                    if len(parts[0].strip()) < 50:
                        title = parts[0].strip()
                        procedure = parts[1].strip()
                coerced.append(
                    SafetyActionItem(
                        title=title,
                        procedure=procedure,
                        rationale="Standard containment procedure for this hazard",
                        role="Floor Supervisor",
                        timeframe="Immediate (<15m)",
                        expected_outcome="Hazard contained and verified safe",
                    )
                )
        return coerced

    @field_validator("visual_observations", mode="before")
    @classmethod
    def _coerce_visual_observations(cls, value: object) -> list[str]:
        if not value:
            return []
        if isinstance(value, (str, dict)):
            value = [value]
        if not isinstance(value, list):
            return []
        coerced: list[str] = []
        for item in value:
            formatted = _format_visual_observation(item)
            if formatted:
                coerced.append(formatted)
        return coerced


# ==============================================================================
# API Request / Response Schemas
# ==============================================================================

class AIAnalysisRequest(BaseModel):
    """Request for AI safety analysis."""

    event_type: str = Field(..., description="Type of safety event")
    event_details: dict = Field(default_factory=dict, description="Event details")
    risk_score: float = Field(
        ..., ge=0.0, le=1.0, description="Deterministic risk score",
    )
    risk_level: str = Field(..., description="Risk level from Risk Engine")
    risk_factors: list[dict] = Field(
        default_factory=list, description="Risk assessment factors",
    )
    risk_explanation: str = Field(default="", description="Risk Engine explanation")
    camera_id: str | None = Field(None, description="Source camera ID")
    zone_name: str | None = Field(None, description="Zone name")
    event_id: str | None = Field(None, description="Source event ID")
    recurrence_count: int = Field(0, ge=0, description="Similar event count")
    user_query: str | None = Field(
        None, description="Optional supervisor question",
    )
    use_rag: bool = Field(True, description="Whether to retrieve RAG context")
    rag_top_k: int = Field(5, ge=1, le=20, description="RAG retrieval top_k")


class AIAnalysisResponse(BaseModel):
    """Response containing AI analysis result."""

    success: bool
    analysis: AIAnalysisResult | None = None
    error: str | None = None
    provider: str | None = None
    model: str | None = None
    insight_id: str | None = None



# ==============================================================================
# AI Insight Read Schemas (for GET /api/ai/insights)
# ==============================================================================

class AiInsightResponse(BaseModel):
    """Single AI insight record returned to the frontend.

    Note: org_id is intentionally excluded — tenant isolation is enforced
    at the query level, never exposed in the response.
    """

    id: str
    insight_type: str
    title: str
    content: str  # raw JSON string — frontend parses
    query: str | None = None
    source_context: dict | None = None
    llm_metadata: dict | None = None
    status: str
    created_at: datetime


class AiInsightListResponse(BaseModel):
    """Paginated list of AI insights."""

    data: list[AiInsightResponse]
    total: int
    page: int
    size: int
