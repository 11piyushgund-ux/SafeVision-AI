"""
SafeVision AI — Safety Agents (Phase 9)

Lightweight specialized reasoning components that assist the AI Orchestrator.

These agents are reasoning/context-building components, NOT decision-makers.
They CANNOT:
  - change event severity
  - change risk score
  - bypass authorization
  - modify alerts directly
  - alter deterministic CV decisions

They CAN:
  - build specialized prompt context
  - analyze patterns in historical data
  - identify relevant safety policy implications
  - suggest investigation angles
"""

from __future__ import annotations

import structlog

from app.services.llm.prompts import (
    build_event_context,
    build_historical_context,
    build_rag_context,
    build_risk_context,
)

log = structlog.get_logger()


class SafetyPolicyAgent:
    """
    Uses RAG context to explain relevant policy/SOP implications.

    Builds the safety-policy section of the analysis prompt using
    retrieved document chunks from the Phase 8 Knowledge Base.
    """

    @staticmethod
    def build_context(
        event_type: str,
        rag_chunks: list[dict],
    ) -> str:
        """
        Build safety policy context from RAG retrieval results.

        Args:
            event_type: The type of safety event.
            rag_chunks: Retrieved chunks from KnowledgeBase.search().

        Returns:
            Formatted policy context string for the LLM prompt.
        """
        if not rag_chunks:
            return build_rag_context([])

        log.info(
            "safety_policy_context_built",
            event_type=event_type,
            chunk_count=len(rag_chunks),
        )
        return build_rag_context(rag_chunks)


class InvestigationAgent:
    """
    Analyzes event + history to identify contributing context.

    Builds the investigation section of the analysis prompt.
    """

    @staticmethod
    def build_context(
        event_type: str,
        event_details: dict,
        camera_id: str | None = None,
        zone_name: str | None = None,
    ) -> str:
        """
        Build investigation context from event details.

        Args:
            event_type: Safety event type.
            event_details: Raw event details dict.
            camera_id: Source camera.
            zone_name: Zone where event occurred.

        Returns:
            Formatted event context string.
        """
        context = build_event_context(
            event_type=event_type,
            event_details=event_details,
            camera_id=camera_id,
            zone_name=zone_name,
        )
        log.info(
            "investigation_context_built",
            event_type=event_type,
            has_camera=bool(camera_id),
            has_zone=bool(zone_name),
        )
        return context


class EmergencyResponseAgent:
    """
    Handles emergency/high-severity reasoning context.

    MUST NOT override deterministic Risk Engine decisions.
    Adds urgency framing to the prompt for critical events.
    """

    EMERGENCY_TYPES = {"fire_smoke", "chemical_spill", "structural_hazard"}
    CRITICAL_LEVELS = {"critical", "high"}

    @staticmethod
    def build_context(
        event_type: str,
        risk_level: str,
        risk_assessment: dict,
    ) -> str:
        """
        Build risk context with emergency framing when appropriate.

        Args:
            event_type: Safety event type.
            risk_level: Deterministic risk level.
            risk_assessment: Full risk assessment dict.

        Returns:
            Formatted risk context, potentially with emergency prefix.
        """
        base_context = build_risk_context(risk_assessment)

        is_emergency = (
            event_type in EmergencyResponseAgent.EMERGENCY_TYPES
            or risk_level.lower() in EmergencyResponseAgent.CRITICAL_LEVELS
        )

        if is_emergency:
            prefix = (
                "⚠️ EMERGENCY SITUATION — This event has been flagged as "
                f"{risk_level.upper()} severity. The deterministic Risk Engine "
                "has assigned this level. Provide URGENT recommendations.\n\n"
            )
            base_context = prefix + base_context
            log.info(
                "emergency_context_built",
                event_type=event_type,
                risk_level=risk_level,
            )

        return base_context


class PredictiveSafetyAgent:
    """
    Uses recurrence/historical context to identify preventive patterns.

    Builds the historical section of the analysis prompt.
    """

    @staticmethod
    def build_context(
        recurrence_count: int = 0,
        recent_events: list[dict] | None = None,
        pattern_summary: dict | None = None,
    ) -> str:
        """
        Build historical/predictive context.

        Args:
            recurrence_count: Number of similar events recently.
            recent_events: List of recent related event dicts.
            pattern_summary: Optional summary of active pattern.

        Returns:
            Formatted historical context string.
        """
        context = build_historical_context(
            recurrence_count=recurrence_count,
            recent_events=recent_events,
            pattern_summary=pattern_summary,
        )

        if recurrence_count >= 3:
            context += (
                f"\n\n⚠️ RECURRING PATTERN DETECTED: {recurrence_count} similar events. "
                "Investigate root cause and recommend preventive measures."
            )
            log.info(
                "recurring_pattern_detected",
                recurrence_count=recurrence_count,
            )

        return context
