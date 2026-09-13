"""
SafeVision AI — AI Orchestrator (Phase 9)

Coordinates the AI reasoning workflow:
  1. Receives structured safety analysis request
  2. Uses agents to build specialized context sections
  3. Optionally retrieves RAG safety knowledge
  4. Selects configured LLM provider (with optional fallback)
  5. Builds the complete prompt
  6. Requests structured output from LLM
  7. Validates and normalizes the response
  8. Returns AIAnalysisResult

The orchestrator does NOT:
  - recalculate risk
  - modify alerts
  - change event severity
  - bypass authorization
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import structlog

from app.schemas.ai_analysis import (
    AIAnalysisResult,
    SafetyActionItem,
    _format_visual_observation,
)
from app.services.knowledge_base import KnowledgeBase
from app.services.llm import LLMRequest
from app.services.llm.agents import (
    EmergencyResponseAgent,
    InvestigationAgent,
    PredictiveSafetyAgent,
    SafetyPolicyAgent,
)
from app.services.llm.prompts import (
    SAFETY_MULTIMODAL_SYSTEM_PROMPT,
    SAFETY_SYSTEM_PROMPT,
    build_analysis_prompt,
    build_detection_metadata_context,
)
from app.services.llm.provider_factory import generate_with_fallback

log = structlog.get_logger()


class AIOrchestrator:
    """
    Coordinates AI safety reasoning across agents and LLM providers.

    Stateless — all context is passed per-request.
    """

    @staticmethod
    def analyze(
        org_id: str,
        event_type: str,
        risk_assessment: dict,
        event_details: dict | None = None,
        camera_id: str | None = None,
        zone_name: str | None = None,
        recurrence_count: int = 0,
        recent_events: list[dict] | None = None,
        pattern_summary: dict | None = None,
        user_query: str | None = None,
        use_rag: bool = True,
        rag_top_k: int = 5,
        evidence_image: bytes | None = None,
    ) -> AIAnalysisResult | dict:
        """
        Run the full AI safety analysis pipeline.

        Args:
            org_id: Organization ID for tenant-scoped RAG retrieval.
            event_type: Type of safety event.
            risk_assessment: Dict from RiskAssessment (consumed as-is).
            event_details: Additional event details.
            camera_id: Source camera.
            zone_name: Zone name.
            recurrence_count: Number of similar past events.
            recent_events: Recent related events.
            pattern_summary: Optional active pattern summary.
            user_query: Optional supervisor question.
            use_rag: Whether to retrieve RAG context.
            rag_top_k: Number of RAG chunks to retrieve.
            evidence_image: Optional JPEG bytes of the evidence frame (Phase 14).

        Returns:
            AIAnalysisResult on success, or dict with error info on failure.
        """
        # --- 1. Build context via agents ---
        event_context = InvestigationAgent.build_context(
            event_type=event_type,
            event_details=event_details or {},
            camera_id=camera_id,
            zone_name=zone_name,
        )

        risk_level = risk_assessment.get("risk_level", "unknown")
        risk_context = EmergencyResponseAgent.build_context(
            event_type=event_type,
            risk_level=risk_level,
            risk_assessment=risk_assessment,
        )

        historical_context = PredictiveSafetyAgent.build_context(
            recurrence_count=recurrence_count,
            recent_events=recent_events,
            pattern_summary=pattern_summary,
        )

        # --- 2. RAG retrieval (org-scoped) ---
        rag_chunks: list[dict] = []
        if use_rag:
            try:
                query = f"{event_type} safety policy"
                if zone_name:
                    query += f" {zone_name}"
                rag_chunks = KnowledgeBase.search(
                    org_id=org_id,
                    query_text=query,
                    top_k=rag_top_k,
                )
                log.info(
                    "rag_retrieval_complete",
                    org_id=org_id,
                    chunks_retrieved=len(rag_chunks),
                )
            except Exception as e:
                log.warning("rag_retrieval_failed", error=str(e))

        rag_context = SafetyPolicyAgent.build_context(
            event_type=event_type,
            rag_chunks=rag_chunks,
        )

        # --- 3. Build detection metadata (Phase 14) ---
        detection_metadata = build_detection_metadata_context(event_details)
        has_image = evidence_image is not None and len(evidence_image) > 0

        # --- 4. Build complete prompt ---
        user_prompt = build_analysis_prompt(
            event_context=event_context,
            risk_context=risk_context,
            rag_context=rag_context,
            historical_context=historical_context,
            user_query=user_query,
            detection_metadata=detection_metadata or None,
            has_image=has_image,
        )

        # --- 5. Call LLM provider ---
        from app.config import get_settings

        settings = get_settings()

        # Select multimodal system prompt when evidence image is provided
        system_prompt = SAFETY_MULTIMODAL_SYSTEM_PROMPT if has_image else SAFETY_SYSTEM_PROMPT

        llm_request = LLMRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
            images=[evidence_image] if has_image else [],
        )

        log.info(
            "ai_analysis_request",
            event_type=event_type,
            multimodal=has_image,
            image_bytes=len(evidence_image) if has_image else 0,
        )

        llm_response = generate_with_fallback(llm_request)

        if not llm_response.success:
            log.error(
                "ai_analysis_llm_failed",
                provider=llm_response.provider,
                error=llm_response.error,
            )
            return {
                "success": False,
                "error": llm_response.error,
                "provider": llm_response.provider,
                "model": llm_response.model,
            }

        # --- 6. Parse and validate structured output ---
        result = AIOrchestrator._parse_response(
            raw_content=llm_response.content,
            provider=llm_response.provider,
            model=llm_response.model,
            provider_metadata=llm_response.metadata,
        )

        return result

    @staticmethod
    def _parse_response(
        raw_content: str,
        provider: str,
        model: str,
        provider_metadata: dict | None = None,
    ) -> AIAnalysisResult | dict:
        """
        Parse and validate the LLM's JSON response into AIAnalysisResult.

        Handles malformed output safely.
        """
        if not raw_content or not raw_content.strip():
            return {
                "success": False,
                "error": "LLM returned empty response",
                "provider": provider,
                "model": model,
            }

        # Try to extract JSON from the response
        content = raw_content.strip()

        # Remove markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last line (fences)
            lines = [line for line in lines if not line.strip().startswith("```")]
            content = "\n".join(lines)

        # Resilient JSON decoding: handles clean JSON, code fences, trailing commas,
        # concatenated objects from prompt echoing, unescaped control chars, and truncated payloads
        def _robust_decode(text: str) -> dict | None:
            if not text or not text.strip():
                return None

            s = text.strip()

            # 1. Strip markdown code fences if present
            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s, re.IGNORECASE)
            if fence_match:
                s = fence_match.group(1).strip()
            elif s.startswith("```"):
                lines = [line for line in s.splitlines() if not line.strip().startswith("```")]
                s = "\n".join(lines).strip()

            def _quick_parse(cand: str) -> dict | None:
                try:
                    val = json.loads(cand)
                    if isinstance(val, dict):
                        return val
                except Exception:
                    pass
                cleaned = re.sub(r",\s*([\]}])", r"\1", cand)
                try:
                    val = json.loads(cleaned)
                    if isinstance(val, dict):
                        return val
                except Exception:
                    pass
                return None

            # Try direct parse
            res = _quick_parse(s)
            if res is not None:
                return res

            # 2. Extract multiple JSON objects using JSONDecoder.raw_decode
            # Specifically handles cases where LLM echoed prompt context as one JSON object
            # followed by the actual analysis report as a second JSON object
            decoder = json.JSONDecoder()
            pos = 0
            candidate_objects: list[dict] = []
            while pos < len(s):
                start_br = s.find("{", pos)
                if start_br == -1:
                    break
                try:
                    obj, end_idx = decoder.raw_decode(s, start_br)
                    if isinstance(obj, dict):
                        candidate_objects.append(obj)
                    pos = max(end_idx, start_br + 1)
                except Exception:
                    pos = start_br + 1

            valid_root_candidates = [
                obj for obj in candidate_objects
                if any(k in obj for k in ("summary", "hazard_interpretation", "immediate_actions", "recommended_actions"))
                and not ("title" in obj and "procedure" in obj and "summary" not in obj)
            ]
            if valid_root_candidates:
                def _score(d: dict) -> int:
                    return sum(1 for k in ("summary", "hazard_interpretation", "immediate_actions", "investigation_actions", "preventive_actions", "recommended_actions", "risk_explanation") if k in d)
                return max(valid_root_candidates, key=_score)

            # 3. Sanitize unescaped control characters inside string literals (newlines/tabs inside quotes)
            def _sanitize_string_literals(input_str: str) -> str:
                chars = []
                in_str = False
                esc = False
                for c in input_str:
                    if esc:
                        chars.append(c)
                        esc = False
                        continue
                    if c == "\\":
                        chars.append(c)
                        esc = True
                        continue
                    if c == '"':
                        in_str = not in_str
                        chars.append(c)
                        continue
                    if in_str:
                        if c == "\n":
                            chars.append("\\n")
                        elif c == "\r":
                            chars.append("\\r")
                        elif c == "\t":
                            chars.append("\\t")
                        else:
                            chars.append(c)
                    else:
                        chars.append(c)
                return "".join(chars)

            sanitized = _sanitize_string_literals(s)
            res = _quick_parse(sanitized)
            if res is not None:
                return res

            # 4. Search for root object starting at "{" containing "summary" or "hazard_interpretation"
            target_idx = sanitized.find('"summary"')
            if target_idx == -1:
                target_idx = sanitized.find('"hazard_interpretation"')
            if target_idx == -1:
                target_idx = sanitized.find('"recommended_actions"')

            if target_idx != -1:
                start_root = sanitized.rfind("{", 0, target_idx)
            else:
                start_root = sanitized.find("{")

            if start_root != -1:
                sub = sanitized[start_root:]
                res = _quick_parse(sub)
                if res is not None:
                    return res
                end_root = sub.rfind("}")
                if end_root > 0:
                    res = _quick_parse(sub[:end_root + 1])
                    if res is not None:
                        return res

            # 5. Safe Truncated JSON Repair with progressive rollback
            target_text = sanitized[start_root:] if start_root != -1 else sanitized

            def _repair_truncated(curr: str) -> dict | None:
                curr = curr.strip()
                if not curr:
                    return None

                for _ in range(25):
                    attempt = re.sub(r"[,:\s]+$", "", curr)

                    stack = []
                    in_string = False
                    escape = False
                    for ch in attempt:
                        if escape:
                            escape = False
                            continue
                        if ch == "\\":
                            escape = True
                            continue
                        if ch == '"':
                            in_string = not in_string
                            continue
                        if not in_string:
                            if ch in "{[":
                                stack.append("}" if ch == "{" else "]")
                            elif ch in "}]":
                                if stack and stack[-1] == ch:
                                    stack.pop()

                    repaired = attempt
                    if in_string:
                        repaired += '"'
                    repaired = re.sub(r"[,:\s]+$", "", repaired)
                    repaired += "".join(reversed(stack))
                    repaired = re.sub(r",\s*([\]}])", r"\1", repaired)

                    try:
                        res_val = json.loads(repaired)
                        if isinstance(res_val, dict) and any(
                            k in res_val
                            for k in ("summary", "hazard_interpretation", "immediate_actions", "recommended_actions")
                        ):
                            return res_val
                    except Exception:
                        pass

                    last_delim = max(curr.rfind(","), curr.rfind("{"), curr.rfind("["))
                    if last_delim <= 0:
                        break
                    curr = curr[:last_delim]

                return None

            return _repair_truncated(target_text)

        parsed = _robust_decode(content)
        if parsed is None:
            log.warning(
                "json_decode_failed",
                content_len=len(content),
                content_head=content[:500],
                content_tail=content[-500:],
            )
            return {
                "success": False,
                "error": "LLM returned malformed JSON",
                "provider": provider,
                "model": model,
                "raw_content": content[:500],
            }

        # Structured action item parsing with backward compatibility
        def _to_action_items(raw_items: object, category: str) -> list[SafetyActionItem]:
            if not raw_items:
                return []
            if isinstance(raw_items, (str, dict, SafetyActionItem)):
                raw_items = [raw_items]
            if not isinstance(raw_items, list):
                return []

            items: list[SafetyActionItem] = []
            default_role = (
                "Floor Supervisor"
                if category == "immediate"
                else ("Maintenance Lead" if category == "investigation" else "Operations Manager")
            )
            default_time = (
                "Immediate (<15m)"
                if category == "immediate"
                else ("Current Shift (<4h)" if category == "investigation" else "Next Maintenance Cycle")
            )

            for item in raw_items:
                if isinstance(item, SafetyActionItem):
                    items.append(item)
                elif isinstance(item, dict):
                    raw_proc = item.get("procedure") or item.get("description")
                    raw_title = item.get("title")
                    # If both are empty or procedure is missing from a truncated dict, do not fabricate fake actions
                    if not raw_proc and not raw_title:
                        continue
                    if not raw_proc:
                        continue
                    title = str(raw_title or "Safety Action").strip()
                    procedure = str(raw_proc).strip()
                    rationale = str(item.get("rationale") or "").strip()
                    role = str(item.get("role") or default_role).strip()
                    timeframe = str(item.get("timeframe") or default_time).strip()
                    outcome = str(
                        item.get("expected_outcome") or item.get("outcome") or ""
                    ).strip()
                    items.append(
                        SafetyActionItem(
                            title=title,
                            procedure=procedure,
                            rationale=rationale,
                            role=role,
                            timeframe=timeframe,
                            expected_outcome=outcome,
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
                    items.append(
                        SafetyActionItem(
                            title=title,
                            procedure=procedure,
                            rationale="Required operational control for this hazard",
                            role=default_role,
                            timeframe=default_time,
                            expected_outcome="Hazard contained and verified",
                        )
                    )
            return items

        immediate = _to_action_items(parsed.get("immediate_actions"), "immediate")
        investigation = _to_action_items(parsed.get("investigation_actions"), "investigation")
        preventive = _to_action_items(parsed.get("preventive_actions"), "preventive")

        raw_recommended = parsed.get("recommended_actions", [])
        if not isinstance(raw_recommended, list):
            raw_recommended = [str(raw_recommended)] if raw_recommended else []

        has_structured_fields = any(
            k in parsed for k in ("immediate_actions", "investigation_actions", "preventive_actions")
        )

        # If structured categorized actions are present but partially populated,
        # and raw_recommended contains distinct unmapped actions, assign them appropriately
        if has_structured_fields and raw_recommended and (len(immediate) < 3 or not investigation or not preventive):
            existing_signatures = {
                a.title.lower()[:30] for a in immediate + investigation + preventive
            }
            unmapped_items: list[object] = []
            for item in raw_recommended:
                sig = ""
                if isinstance(item, dict):
                    sig = str(item.get("title") or "").lower()[:30]
                elif isinstance(item, str):
                    sig = item.lower()[:30]
                if not any(es in sig or sig in es for es in existing_signatures if es):
                    unmapped_items.append(item)

            for item in unmapped_items:
                text_rep = ""
                if isinstance(item, dict):
                    text_rep = f"{item.get('title', '')} {item.get('procedure', '')}".lower()
                elif isinstance(item, str):
                    text_rep = item.lower()

                if not investigation and any(w in text_rep for w in ("investig", "inspect", "document", "log", "interview", "root cause", "audit", "review")):
                    investigation.extend(_to_action_items([item], "investigation"))
                elif not preventive and any(w in text_rep for w in ("prevent", "updat", "train", "sop", "maintenance", "procedur", "revis", "control", "policy")):
                    preventive.extend(_to_action_items([item], "preventive"))
                elif len(immediate) < 3 and any(w in text_rep for w in ("evacuat", "halt", "stop", "clear", "suppress", "isolate", "de-energiz", "shut down", "immediate", "urgent")):
                    immediate.extend(_to_action_items([item], "immediate"))
                elif len(investigation) < 2 and any(w in text_rep for w in ("investig", "inspect", "document", "log", "interview", "root cause", "audit", "review")):
                    investigation.extend(_to_action_items([item], "investigation"))
                elif len(preventive) < 2:
                    preventive.extend(_to_action_items([item], "preventive"))

        # Flatten all actions into recommended_actions strings for legacy API consumers
        flat_recommended: list[str] = []
        if raw_recommended:
            for item in raw_recommended:
                if isinstance(item, dict):
                    t = str(item.get("title") or "").strip()
                    p = str(item.get("procedure") or item.get("description") or "").strip()
                    flat_recommended.append(f"{t}: {p}" if t and p else (p or t))
                elif isinstance(item, str) and item.strip():
                    flat_recommended.append(item.strip())

        if not flat_recommended:
            for act in immediate + investigation + preventive:
                flat_recommended.append(f"{act.title}: {act.procedure}")

        uncertainties = parsed.get("uncertainties", [])
        if not isinstance(uncertainties, list):
            uncertainties = [str(uncertainties)] if uncertainties else []

        raw_visual_obs = parsed.get("visual_observations", [])
        if not isinstance(raw_visual_obs, list):
            raw_visual_obs = [raw_visual_obs] if raw_visual_obs else []

        visual_obs: list[str] = []
        for item in raw_visual_obs:
            formatted = _format_visual_observation(item)
            if formatted:
                visual_obs.append(formatted)

        contributing = parsed.get("contributing_factors", [])
        if not isinstance(contributing, list):
            contributing = [str(contributing)] if contributing else []

        # Validate against AIAnalysisResult schema
        try:
            result = AIAnalysisResult(
                summary=parsed.get("summary", "Analysis completed"),
                risk_explanation=parsed.get("risk_explanation", "See risk assessment"),
                contributing_factors=contributing,
                safety_policy_guidance=parsed.get(
                    "safety_policy_guidance",
                    "No specific policy documents available",
                ),
                historical_context=parsed.get(
                    "historical_context",
                    "No historical context available",
                ),
                recommended_actions=flat_recommended,
                provider=provider,
                model=model,
                generated_at=datetime.now(timezone.utc),
                # Phase 14 — multimodal visual fields (backward-compatible defaults)
                visual_observations=visual_obs,
                visual_validation=parsed.get("visual_validation"),
                # Phase 14d/14f — structured intelligence fields
                hazard_interpretation=parsed.get("hazard_interpretation", ""),
                immediate_actions=immediate,
                investigation_actions=investigation,
                preventive_actions=preventive,
                uncertainties=uncertainties,
                provider_metadata=provider_metadata or {},
            )
            log.info(
                "ai_analysis_complete",
                provider=provider,
                model=model,
                summary_len=len(result.summary),
                immediate_count=len(result.immediate_actions),
                investigation_count=len(result.investigation_actions),
                preventive_count=len(result.preventive_actions),
                has_visual=bool(result.visual_observations),
            )
            return result


        except Exception as e:
            return {
                "success": False,
                "error": f"Response validation failed: {e}",
                "provider": provider,
                "model": model,
            }
