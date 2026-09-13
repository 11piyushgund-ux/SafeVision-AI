from app.database import SessionLocal
from app.models.event import Event
from app.services.llm.orchestrator import AIOrchestrator
from app.services.risk_engine import RiskEngine
from app.services.evidence_service import EvidenceService

db = SessionLocal()
ev = db.query(Event).filter(Event.id == 'caadc73f-fb25-44b7-a779-553a038f45de').first()
risk_obj = RiskEngine.assess_with_db(event=ev, db=db, lookback_hours=24)
risk_data = {
    'risk_score': risk_obj.risk_score,
    'risk_level': risk_obj.risk_level,
    'factors': [f.model_dump() for f in risk_obj.factors],
    'explanation': risk_obj.explanation,
}
p = EvidenceService.resolve_evidence_path(ev.evidence_path, ev.org_id)
img = p.read_bytes() if p else None

# Monkey-patch _parse_response to print raw_content
orig_parse = AIOrchestrator._parse_response
def debug_parse(raw_content, provider, model, provider_metadata=None):
    print("\n" + "="*50 + " RAW CONTENT RECEIVED " + "="*50)
    print(raw_content)
    print("="*120 + "\n")
    return orig_parse(raw_content, provider, model, provider_metadata)
AIOrchestrator._parse_response = debug_parse

res = AIOrchestrator.analyze(
    org_id=ev.org_id,
    event_type='fire_smoke',
    risk_assessment=risk_data,
    event_details=ev.detection_data or {},
    camera_id=ev.camera_id,
    zone_name='Assembly Zone A',
    recurrence_count=206,
    use_rag=True,
    rag_top_k=5,
    evidence_image=img,
)
print("FINAL RESULT TYPE:", type(res))
if hasattr(res, 'model_dump_json'):
    print(res.model_dump_json(indent=2))
else:
    print(res)
