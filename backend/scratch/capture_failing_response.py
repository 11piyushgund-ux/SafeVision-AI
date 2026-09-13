import json
import sys
from app.database import SessionLocal
from app.models.event import Event
from app.services.llm.orchestrator import AIOrchestrator
from app.services.risk_engine import RiskEngine
from app.services.evidence_service import EvidenceService
from app.services.llm.provider_factory import generate_with_fallback
from app.services.llm import LLMRequest
from app.services.llm.prompts import (
    SAFETY_SYSTEM_PROMPT,
    SAFETY_MULTIMODAL_SYSTEM_PROMPT,
    build_event_context,
    build_risk_context,
    build_rag_context,
    build_historical_context,
    build_detection_metadata_context,
    build_analysis_prompt,
)
from app.config import get_settings

db = SessionLocal()
event_id = "caadc73f-fb25-44b7-a779-553a038f45de"
ev = db.query(Event).filter(Event.id == event_id).first()
if not ev:
    print(f"Event {event_id} not found!")
    sys.exit(1)

risk_obj = RiskEngine.assess_with_db(event=ev, db=db, lookback_hours=24)
risk_data = {
    "risk_score": risk_obj.risk_score,
    "risk_level": risk_obj.risk_level,
    "factors": [f.model_dump() for f in risk_obj.factors],
    "explanation": risk_obj.explanation,
}

p = EvidenceService.resolve_evidence_path(ev.evidence_path, ev.org_id)
evidence_image = p.read_bytes() if p else None

event_context = build_event_context(
    event_type="fire_smoke",
    event_details=ev.detection_data or {},
    camera_id=ev.camera_id,
    zone_name="Assembly Zone A",
)
risk_context = build_risk_context(risk_data)
rag_context = build_rag_context([])
historical_context = build_historical_context(206, [], None)
detection_metadata = build_detection_metadata_context(ev.detection_data or {})
has_image = evidence_image is not None and len(evidence_image) > 0

user_prompt = build_analysis_prompt(
    event_context=event_context,
    risk_context=risk_context,
    rag_context=rag_context,
    historical_context=historical_context,
    user_query=None,
    detection_metadata=detection_metadata or None,
    has_image=has_image,
)

settings = get_settings()
system_prompt = SAFETY_MULTIMODAL_SYSTEM_PROMPT if has_image else SAFETY_SYSTEM_PROMPT

llm_request = LLMRequest(
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    temperature=settings.llm_temperature,
    max_output_tokens=settings.llm_max_output_tokens,
    timeout_seconds=settings.llm_timeout_seconds,
    images=[evidence_image] if has_image else [],
)

print(f"Calling generate_with_fallback...")
resp = generate_with_fallback(llm_request)

print(f"\nProvider: {resp.provider}")
print(f"Model: {resp.model}")
print(f"Success: {resp.success}")
print(f"Error: {resp.error}")
print(f"Metadata: {json.dumps(resp.metadata, indent=2)}")
print(f"\nRAW CONTENT LENGTH: {len(resp.content)}")
print(f"--- START RAW CONTENT ---")
print(resp.content)
print(f"--- END RAW CONTENT ---")

# Now run _parse_response directly
parse_res = AIOrchestrator._parse_response(
    raw_content=resp.content,
    provider=resp.provider,
    model=resp.model,
    provider_metadata=resp.metadata,
)
print(f"\n_parse_response result type: {type(parse_res)}")
if isinstance(parse_res, dict):
    print(f"Dictionary output: {json.dumps(parse_res, indent=2)}")
else:
    print(f"AIAnalysisResult dump:\n{parse_res.model_dump_json(indent=2)}")
