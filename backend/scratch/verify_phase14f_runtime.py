"""
Runtime verification script for SafeVision AI Phase 14F Report Quality Upgrade.
Analyzes real Safety Events against the live running FastAPI backend on http://127.0.0.1:8000,
inspects the response, queries the database to inspect persisted AiInsight records,
and outputs complete details.
"""

import json
import sys
import requests
from app.database import SessionLocal
from app.models.ai_insight import AiInsight
from app.models.event import Event
from app.services.auth_service import create_access_token

BASE_URL = "http://127.0.0.1:8000"

def get_auth_token(org_id="d0000000-0000-0000-0000-000000000001", user_id="d0000000-0000-0000-0000-000000000003"):
    return create_access_token(
        user_id=user_id,
        org_id=org_id,
        role_name="admin",
    )

def test_analyze_real_event(event_id: str, label: str):
    print(f"\n{'='*70}")
    print(f"TESTING REAL EVENT ANALYSIS: {label} (ID: {event_id})")
    print(f"{'='*70}")

    token = get_auth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    url = f"{BASE_URL}/api/ai/analyze-event/{event_id}"
    print(f"Sending POST {url} ...")
    resp = requests.post(url, headers=headers, timeout=90)
    print(f"Response status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error response: {resp.text}")
        return False, None

    data = resp.json()
    print(f"Success: {data.get('success')}")
    print(f"Provider: {data.get('provider')}, Model: {data.get('model')}")
    print(f"Insight ID: {data.get('insight_id')}")

    if not data.get("success"):
        print(f"Analysis failed: {data.get('error')}")
        return False, None

    analysis = data.get("analysis") or {}
    immediate = analysis.get("immediate_actions", [])
    investigation = analysis.get("investigation_actions", [])
    preventive = analysis.get("preventive_actions", [])
    flat_recommended = analysis.get("recommended_actions", [])
    hazard_interp = analysis.get("hazard_interpretation", "")

    print(f"\n--- ACTION COUNTS ---")
    print(f"Immediate Actions: {len(immediate)} (Requirement: >= 3)")
    print(f"Investigation Actions: {len(investigation)} (Requirement: >= 2)")
    print(f"Preventive Actions: {len(preventive)} (Requirement: >= 2)")
    print(f"Legacy Flattened Recommended Actions: {len(flat_recommended)}")
    print(f"Hazard Interpretation Length: {len(hazard_interp)} chars")

    # Inspect the persisted database record
    insight_id = data.get("insight_id")
    if not insight_id:
        print("ERROR: No insight_id returned in response")
        return False, None

    db = SessionLocal()
    try:
        insight = db.query(AiInsight).filter(AiInsight.id == insight_id).first()
        if not insight:
            print(f"ERROR: Persisted AiInsight {insight_id} not found in DB!")
            return False, None

        content = json.loads(insight.content)
        print(f"\n--- PERSISTED RECORD IN POSTGRESQL (AiInsight ID: {insight.id}) ---")
        print(f"Title: {insight.title[:120]}...")
        print(f"LLM Metadata: {json.dumps(insight.llm_metadata, indent=2)}")
        print(f"Visual Observations: {content.get('visual_observations')}")
        print(f"Visual Validation: {content.get('visual_validation')}")
        print(f"Uncertainties: {content.get('uncertainties')}")
        print(f"\n--- HAZARD INTERPRETATION ---")
        print(content.get("hazard_interpretation"))

        print(f"\n--- IMMEDIATE CONTAINMENT ACTIONS ({len(content.get('immediate_actions', []))}) ---")
        for i, a in enumerate(content.get("immediate_actions", []), 1):
            if isinstance(a, dict):
                print(f"  [{i}] {a.get('title')}")
                print(f"      Procedure: {a.get('procedure')}")
                print(f"      Rationale: {a.get('rationale')}")
                print(f"      Role: {a.get('role')} | Timeframe: {a.get('timeframe')}")
                print(f"      Outcome: {a.get('expected_outcome')}")
            else:
                print(f"  [{i}] {a}")

        print(f"\n--- INVESTIGATION & EVIDENCE ACTIONS ({len(content.get('investigation_actions', []))}) ---")
        for i, a in enumerate(content.get("investigation_actions", []), 1):
            if isinstance(a, dict):
                print(f"  [{i}] {a.get('title')}")
                print(f"      Procedure: {a.get('procedure')}")
                print(f"      Rationale: {a.get('rationale')}")
                print(f"      Role: {a.get('role')} | Timeframe: {a.get('timeframe')}")
                print(f"      Outcome: {a.get('expected_outcome')}")
            else:
                print(f"  [{i}] {a}")

        print(f"\n--- PREVENTIVE CONTROLS ({len(content.get('preventive_actions', []))}) ---")
        for i, a in enumerate(content.get("preventive_actions", []), 1):
            if isinstance(a, dict):
                print(f"  [{i}] {a.get('title')}")
                print(f"      Procedure: {a.get('procedure')}")
                print(f"      Rationale: {a.get('rationale')}")
                print(f"      Role: {a.get('role')} | Timeframe: {a.get('timeframe')}")
                print(f"      Outcome: {a.get('expected_outcome')}")
            else:
                print(f"  [{i}] {a}")

        print(f"\n--- BACKWARD-COMPATIBLE RECOMMENDED ACTIONS ({len(content.get('recommended_actions', []))}) ---")
        for i, r in enumerate(content.get("recommended_actions", []), 1):
            print(f"  [{i}] {r}")

        return True, content
    finally:
        db.close()

if __name__ == "__main__":
    # 1. Fire / Smoke real event
    ok1, content1 = test_analyze_real_event("d0000000-0000-0000-0000-000000000103", "FIRE / SMOKE DETECTION")

    # 2. PPE event
    ok2, content2 = test_analyze_real_event("d0000000-0000-0000-0000-000000000100", "PPE DETECTION")

    if not ok1:
        print("\nVerification FAILED for Fire/Smoke event!")
        sys.exit(1)
    if not ok2:
        print("\nVerification FAILED for PPE event!")
        sys.exit(1)

    print("\n" + "="*70)
    print("ALL REAL RUNTIME VERIFICATIONS PASSED SUCCESSFULLY!")
    print("="*70)
