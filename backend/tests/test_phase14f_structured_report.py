"""
SafeVision AI — Phase 14F Report Quality & Structured Guidance Tests

Validates:
1. Structured SafetyActionItem model validation and field types.
2. AIAnalysisResult coercion of:
   - fully structured action objects
   - legacy flat string arrays
   - mixed object/string arrays
3. Orchestrator _parse_response():
   - Parsing structured action items (immediate, investigation, preventive)
   - Auto-splitting legacy recommended_actions when structured categories missing
   - Preserving backward-compatible flattened recommended_actions as list[str]
   - Epistemic hazard_interpretation retention
   - Uncertainties and visual_validation retention
   - Malformed/truncated JSON resilience
4. Prompt requirements:
   - Mandatory minimums present in prompt templates (>=3 immediate, >=2 investigation, >=2 preventive)
   - Structural action object schema instructions in prompts
"""

import json
import pytest
from datetime import datetime, timezone

from app.schemas.ai_analysis import AIAnalysisResult, SafetyActionItem
from app.services.llm.orchestrator import AIOrchestrator
from app.services.llm.prompts import (
    SAFETY_SYSTEM_PROMPT,
    SAFETY_MULTIMODAL_SYSTEM_PROMPT,
    SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT,
)


# ==============================================================================
# 1. Schema Unit Tests
# ==============================================================================

def test_safety_action_item_model():
    item = SafetyActionItem(
        title="Isolate Circuit Breaker",
        procedure="Locate panel 4B, switch off breaker #12, apply lockout padlock.",
        rationale="Prevents electrical fire re-ignition.",
        role="Maintenance Lead",
        timeframe="Immediate (<15m)",
        expected_outcome="Zero energy state confirmed.",
    )
    assert item.title == "Isolate Circuit Breaker"
    assert "lockout padlock" in item.procedure
    assert item.role == "Maintenance Lead"
    assert item.timeframe == "Immediate (<15m)"
    assert item.expected_outcome == "Zero energy state confirmed."


def test_ai_analysis_result_coerces_structured_dicts():
    raw_immediate = [
        {
            "title": "Evacuate Hazard Zone",
            "procedure": "Sound evacuation tone, escort personnel past boundary marker B.",
            "rationale": "Life safety containment.",
            "role": "Floor Supervisor",
            "timeframe": "Immediate (<15m)",
            "expected_outcome": "Zone fully cleared.",
        }
    ]
    result = AIAnalysisResult(
        summary="Smoke event detected",
        risk_explanation="Deterministic score 0.85",
        immediate_actions=raw_immediate,
        provider="ollama",
        model="qwen2.5:3b-instruct",
    )
    assert len(result.immediate_actions) == 1
    action = result.immediate_actions[0]
    assert isinstance(action, SafetyActionItem)
    assert action.title == "Evacuate Hazard Zone"
    assert action.role == "Floor Supervisor"


def test_ai_analysis_result_coerces_legacy_strings():
    raw_immediate = [
        "Isolate Valve: Turn yellow manual shutoff valve 90 degrees clockwise.",
        "Clear personnel from area immediately",
    ]
    result = AIAnalysisResult(
        summary="Hazard detected",
        risk_explanation="High risk",
        immediate_actions=raw_immediate,
        provider="ollama",
        model="qwen2.5:3b-instruct",
    )
    assert len(result.immediate_actions) == 2
    act0 = result.immediate_actions[0]
    assert isinstance(act0, SafetyActionItem)
    assert act0.title == "Isolate Valve"
    assert "Turn yellow manual" in act0.procedure

    act1 = result.immediate_actions[1]
    assert isinstance(act1, SafetyActionItem)
    assert "Clear personnel" in act1.title
    assert act1.role == "Floor Supervisor"


def test_ai_analysis_result_coerces_mixed_array():
    raw_actions = [
        {
            "title": "Stop Line 2",
            "procedure": "Press emergency stop button at station 4.",
            "role": "Safety Marshal",
        },
        "Inspect conveyor belt joint for friction heat",
    ]
    result = AIAnalysisResult(
        summary="Conveyor hazard",
        risk_explanation="Elevated friction risk",
        investigation_actions=raw_actions,
        provider="test",
        model="test-model",
    )
    assert len(result.investigation_actions) == 2
    assert result.investigation_actions[0].title == "Stop Line 2"
    assert result.investigation_actions[0].role == "Safety Marshal"
    assert isinstance(result.investigation_actions[1], SafetyActionItem)


# ==============================================================================
# 2. Orchestrator _parse_response() Tests
# ==============================================================================

def test_orchestrator_parse_structured_actions():
    llm_payload = {
        "summary": "Smoke detected near motor assembly.",
        "risk_explanation": "Risk engine assessed HIGH severity due to recurrence and high confidence.",
        "hazard_interpretation": "Thermal breakdown produces toxic smoke and potential flash ignition. The hazard can escalate to adjacent hydraulic fluid lines if not contained. Downstream consequences include assembly line shutdown and smoke inhalation hazards for personnel.",
        "contributing_factors": ["High motor temperature", "Recurrence count: 3"],
        "immediate_actions": [
            {
                "title": "Isolate Motor Circuit",
                "procedure": "Cut power at main MCC panel breaker #14. Verify zero voltage.",
                "rationale": "Eliminates thermal energy feed.",
                "role": "Maintenance Lead",
                "timeframe": "Immediate (<15m)",
                "expected_outcome": "Motor de-energized safely.",
            },
            {
                "title": "Establish 10m Buffer",
                "procedure": "Deploy safety cones and barriers 10m around the smoking motor.",
                "rationale": "Protects floor workers from airborne particulates.",
                "role": "Floor Supervisor",
                "timeframe": "Within 20m",
                "expected_outcome": "Exclusion boundary secured.",
            },
            {
                "title": "Prepare Suppression Ready",
                "procedure": "Stage CO2 extinguisher 5 meters upwind of assembly cell.",
                "rationale": "Guarantees rapid response if open flame develops.",
                "role": "Safety Marshal",
                "timeframe": "Immediate (<15m)",
                "expected_outcome": "Suppression equipment verified ready.",
            },
        ],
        "investigation_actions": [
            {
                "title": "Inspect Motor Bearings",
                "procedure": "Disassemble bearing housing and inspect for lubrication breakdown and metal scoring.",
                "rationale": "Identifies mechanical friction cause.",
                "role": "Maintenance Lead",
                "timeframe": "Current Shift (<4h)",
                "expected_outcome": "Mechanical wear quantified.",
            },
            {
                "title": "Review Thermal Sensor Logs",
                "procedure": "Export telemetry from SCADA for past 72 hours leading to smoke detection.",
                "rationale": "Determines heating curve and operating conditions.",
                "role": "EHS Specialist",
                "timeframe": "Within 24h",
                "expected_outcome": "Thermal timeline mapped.",
            },
        ],
        "preventive_actions": [
            {
                "title": "Upgrade Thermal Interlock",
                "procedure": "Install automated temperature cutoff switch on motor casing set to 80C threshold.",
                "rationale": "Automates shutdown before smoke generation can recur.",
                "role": "Operations Manager",
                "timeframe": "Next Maintenance Cycle",
                "expected_outcome": "Automated failsafe active.",
            },
            {
                "title": "SOP Review on Bearing Greasing",
                "procedure": "Revise pre-shift greasing intervals from weekly to bi-weekly with signoff sheet.",
                "rationale": "Prevents recurrence due to dry bearing friction.",
                "role": "EHS Specialist",
                "timeframe": "Within 7 Days",
                "expected_outcome": "Updated SOP published.",
            },
        ],
        "uncertainties": [
            "Exact internal winding temperature cannot be confirmed without disassembly."
        ],
    }

    raw_json = json.dumps(llm_payload)
    result = AIOrchestrator._parse_response(
        raw_content=raw_json,
        provider="openrouter",
        model="google/gemma-4-26b-a4b-it:free",
    )

    assert isinstance(result, AIAnalysisResult)
    assert len(result.immediate_actions) == 3
    assert len(result.investigation_actions) == 2
    assert len(result.preventive_actions) == 2
    assert "Thermal breakdown produces toxic smoke" in result.hazard_interpretation
    assert len(result.uncertainties) == 1

    # Verify backward-compatible recommended_actions was auto-populated with strings
    assert isinstance(result.recommended_actions, list)
    assert len(result.recommended_actions) == 7
    for act_str in result.recommended_actions:
        assert isinstance(act_str, str)
        assert ":" in act_str


def test_orchestrator_parse_legacy_flat_strings():
    llm_payload = {
        "summary": "PPE violation detected: missing safety helmet.",
        "risk_explanation": "Risk Engine assigned HIGH severity.",
        "hazard_interpretation": "Worker operating under overhead hoist without helmet protection. Potential falling object can cause severe cranial injury. Secondary risk of crane operator not noticing unequipped worker.",
        "recommended_actions": [
            "Immediately halt overhead crane movement above station 3.",
            "Instruct worker to step out of active hoist zone and don certified hard hat.",
            "Inspect hard hat condition and fit before authorizing reentry.",
            "Review pre-shift toolbox talk records for PPE compliance.",
        ],
    }

    raw_json = json.dumps(llm_payload)
    result = AIOrchestrator._parse_response(
        raw_content=raw_json,
        provider="ollama",
        model="qwen2.5:3b-instruct",
    )

    assert isinstance(result, AIAnalysisResult)
    # When categorized actions are not in the LLM JSON, structured fields preserve empty defaults
    assert result.immediate_actions == []
    assert result.investigation_actions == []
    assert result.preventive_actions == []
    # recommended_actions is preserved as flat list of strings
    assert len(result.recommended_actions) == 4
    for r in result.recommended_actions:
        assert isinstance(r, str)


def test_orchestrator_parse_markdown_code_fences():
    raw = """```json
    {
      "summary": "Forklift proximity violation",
      "risk_explanation": "Speed and distance violation",
      "hazard_interpretation": "Forklift operating within 2m of pedestrian walkway. Risk of collision and crush injury. Facility operations impacted if pedestrian path is blocked.",
      "immediate_actions": [
        {
          "title": "Halt Forklift",
          "procedure": "Sound horn, signal operator to set parking brake.",
          "role": "Safety Marshal",
          "timeframe": "Immediate (<15m)",
          "expected_outcome": "Vehicle stopped."
        },
        {
          "title": "Clear Pedestrian Path",
          "procedure": "Direct workers behind guard rail.",
          "role": "Floor Supervisor",
          "timeframe": "Immediate (<15m)",
          "expected_outcome": "Pedestrians safe."
        },
        {
          "title": "Inspect Proximity Sensor",
          "procedure": "Verify audible warning alarm activates on approach.",
          "role": "Maintenance Lead",
          "timeframe": "Within 1h",
          "expected_outcome": "Alarm verified functional."
        }
      ],
      "investigation_actions": [
        {
          "title": "Check Floor Demarcation",
          "procedure": "Inspect yellow line visibility at intersection.",
          "role": "EHS Specialist",
          "timeframe": "Current Shift",
          "expected_outcome": "Line wear noted."
        },
        {
          "title": "Review Vehicle Telemetry",
          "procedure": "Check speed sensor log for speed limit breach.",
          "role": "Maintenance Lead",
          "timeframe": "Current Shift",
          "expected_outcome": "Speed verified."
        }
      ],
      "preventive_actions": [
        {
          "title": "Install Physical Bollards",
          "procedure": "Install steel impact bollards along walkway edge.",
          "role": "Operations Manager",
          "timeframe": "Next Maintenance Cycle",
          "expected_outcome": "Physical separation established."
        },
        {
          "title": "Repaint Hazard Markings",
          "procedure": "Repaint high-visibility hatch markings at blind corner.",
          "role": "Maintenance Lead",
          "timeframe": "Within 14 Days",
          "expected_outcome": "Demarcation renewed."
        }
      ]
    }
    ```"""

    result = AIOrchestrator._parse_response(
        raw_content=raw,
        provider="ollama",
        model="qwen2.5:3b-instruct",
    )
    assert isinstance(result, AIAnalysisResult)
    assert len(result.immediate_actions) == 3
    assert len(result.investigation_actions) == 2
    assert len(result.preventive_actions) == 2


def test_orchestrator_malformed_json_fallback():
    raw = "This is not valid json at all { invalid: 123"
    result = AIOrchestrator._parse_response(
        raw_content=raw,
        provider="openrouter",
        model="test",
    )
    assert isinstance(result, dict)
    assert result["success"] is False
    assert "malformed" in result["error"].lower() or "no json" in result["error"].lower()


# ==============================================================================
# 3. Prompt Template Validation Tests
# ==============================================================================

def test_prompts_contain_mandatory_minimum_counts():
    for prompt in [
        SAFETY_SYSTEM_PROMPT,
        SAFETY_MULTIMODAL_SYSTEM_PROMPT,
        SAFETY_TEXT_ONLY_FALLBACK_SYSTEM_PROMPT,
    ]:
        assert "AT LEAST 3 distinct" in prompt
        assert "AT LEAST 2 distinct" in prompt
        assert "Minimum 3 detailed sentences" in prompt
        assert '"procedure"' in prompt
        assert '"rationale"' in prompt
        assert '"role"' in prompt
        assert '"timeframe"' in prompt
        assert '"expected_outcome"' in prompt


# ==============================================================================
# 4. Phase 14F.1 Real Runtime JSON Reliability Tests (All 10 Requirements)
# ==============================================================================

def test_json_reliability_1_valid_structured_json():
    raw = json.dumps({
        "summary": "Fire/smoke detected in Assembly Zone A.",
        "risk_explanation": "Deterministic score 0.82.",
        "hazard_interpretation": "Primary hazard is fire spread. Escalation pathway leads to work cell contamination. Downstream consequences affect personnel safety.",
        "immediate_actions": [
            {
                "title": "Evacuate Area",
                "procedure": "Escort all personnel past safety boundary marker B.",
                "rationale": "Life safety protection.",
                "role": "Floor Supervisor",
                "timeframe": "Immediate (<15m)",
                "expected_outcome": "Zone clear.",
            }
        ],
        "investigation_actions": [
            {
                "title": "Inspect Equipment",
                "procedure": "Examine conveyor drive motor for overheating.",
                "rationale": "Identify failure mode.",
                "role": "Maintenance Lead",
                "timeframe": "Current Shift (<4h)",
                "expected_outcome": "Thermal log recorded.",
            }
        ],
        "preventive_actions": [
            {
                "title": "Update SOP",
                "procedure": "Revise pre-shift electrical checklist.",
                "rationale": "Prevent recurrence.",
                "role": "Operations Manager",
                "timeframe": "Next Maintenance Cycle",
                "expected_outcome": "Checklist approved.",
            }
        ],
        "uncertainties": ["Exact ignition mechanism unknown."],
    })
    result = AIOrchestrator._parse_response(raw, "ollama", "qwen2.5:3b-instruct")
    assert isinstance(result, AIAnalysisResult)
    assert result.summary == "Fire/smoke detected in Assembly Zone A."
    assert len(result.immediate_actions) == 1
    assert len(result.investigation_actions) == 1
    assert len(result.preventive_actions) == 1


def test_json_reliability_2_markdown_fenced_json():
    raw = """```json
    {
      "summary": "Fenced smoke report",
      "hazard_interpretation": "Smoke spread risk. Escalation could impair breathing. Facility continuity at risk.",
      "immediate_actions": [
        {
          "title": "Ventilate Bay",
          "procedure": "Activate emergency exhaust dampers in Bay 3.",
          "rationale": "Clear airborne particulates.",
          "role": "Safety Marshal",
          "timeframe": "Immediate (<15m)",
          "expected_outcome": "Air quality restored."
        }
      ]
    }
    ```"""
    result = AIOrchestrator._parse_response(raw, "openrouter", "google/gemma-4-26b-a4b-it:free")
    assert isinstance(result, AIAnalysisResult)
    assert result.summary == "Fenced smoke report"
    assert len(result.immediate_actions) == 1


def test_json_reliability_3_trailing_commas():
    raw = """{
      "summary": "Trailing commas in payload",
      "hazard_interpretation": "Risk of arc flash. Escalation could cause burns. Production line halted.",
      "immediate_actions": [
        {
          "title": "Lockout Breaker",
          "procedure": "Apply lockout padlock to main breaker 4.",
          "role": "Floor Supervisor",
          "timeframe": "Immediate (<15m)",
        },
      ],
      "recommended_actions": [
        "Lockout Breaker",
      ],
    }"""
    result = AIOrchestrator._parse_response(raw, "ollama", "qwen2.5:3b-instruct")
    assert isinstance(result, AIAnalysisResult)
    assert result.summary == "Trailing commas in payload"
    assert len(result.immediate_actions) == 1
    assert result.immediate_actions[0].title == "Lockout Breaker"


def test_json_reliability_4_truncated_nested_json():
    raw = """{
      "summary": "Truncated nested report",
      "hazard_interpretation": "Thermal anomaly. Escalation to smoldering fire. Cell damage risk.",
      "immediate_actions": [
        {
          "title": "Sound Alarm",
          "procedure": "Pull manual call point at gate 2.",
          "role": "Safety Marshal",
          "timeframe": "Immediate (<15m)"
        }
      ],
      "investigation_actions": [
        {
          "title": "Thermal Camera Scan",
          "procedure": "Scan electrical enclosure with FLIR imager."
    """
    result = AIOrchestrator._parse_response(raw, "ollama", "qwen2.5:3b-instruct")
    assert isinstance(result, AIAnalysisResult)
    assert result.summary == "Truncated nested report"
    assert len(result.immediate_actions) == 1
    assert result.immediate_actions[0].title == "Sound Alarm"


def test_json_reliability_5_truncated_action_object():
    raw = """{
      "summary": "Truncated action object payload",
      "hazard_interpretation": "Chemical vapor hazard. Escalation to toxic exposure. Facility evacuation required.",
      "immediate_actions": [
        {
          "title": "Shut Supply Valve",
          "procedure": "Turn off solvent supply line at manifold 1.",
          "role": "Floor Supervisor",
          "timeframe": "Immediate (<15m)",
          "expected_outcome": "Flow halted."
        },
        {
          "title": "Partial Incomplete Action",
          "procedure": 
    """
    result = AIOrchestrator._parse_response(raw, "ollama", "qwen2.5:3b-instruct")
    assert isinstance(result, AIAnalysisResult)
    assert result.summary == "Truncated action object payload"
    # The complete action object is preserved; the truncated partial action object is safely discarded
    assert len(result.immediate_actions) == 1
    assert result.immediate_actions[0].title == "Shut Supply Valve"


def test_json_reliability_6_escaped_quote_case():
    raw = r"""{
      "summary": "Operator reported \"crackling noise\" before smoke appeared.",
      "hazard_interpretation": "Mechanical friction failure. Escalation to bearing seizure. Downstream gearbox failure.",
      "immediate_actions": [
        {
          "title": "Press E-Stop",
          "procedure": "Depress the emergency stop button on console \"Alpha\".",
          "rationale": "Immediate kinetic shutdown.",
          "role": "Floor Supervisor",
          "timeframe": "Immediate (<15m)",
          "expected_outcome": "Drive halted."
        }
      ]
    }"""
    result = AIOrchestrator._parse_response(raw, "openrouter", "google/gemma-4-26b-a4b-it:free")
    assert isinstance(result, AIAnalysisResult)
    assert 'crackling noise' in result.summary
    assert 'console "Alpha"' in result.immediate_actions[0].procedure


def test_json_reliability_7_legacy_flat_recommended_actions():
    raw = json.dumps({
        "summary": "Legacy report format",
        "hazard_interpretation": "Forklift proximity violation. Escalation to collision. Structural and bodily injury risk.",
        "recommended_actions": [
            "Immediate Action: Halt forklift movement in aisle 4",
            "Secondary Action: Verify pedestrian barrier integrity",
            "Investigation Action: Review vehicle telematics and speed log",
            "Preventive Action: Install blind corner motion sensor alarm",
        ],
    })
    result = AIOrchestrator._parse_response(raw, "ollama", "qwen2.5:3b-instruct")
    assert isinstance(result, AIAnalysisResult)
    assert result.summary == "Legacy report format"
    # Backward compatibility: flat strings preserved in recommended_actions, no invented structured categories
    assert len(result.recommended_actions) == 4
    for r in result.recommended_actions:
        assert isinstance(r, str)
    assert result.immediate_actions == []
    assert result.investigation_actions == []
    assert result.preventive_actions == []


def test_json_reliability_8_mixed_string_and_object_actions():
    raw = """{
      "summary": "Mixed actions format",
      "hazard_interpretation": "Worker without hard hat. Escalation to impact injury. Overhead hazard present.",
      "immediate_actions": [
        {
          "title": "Stop Worker",
          "procedure": "Instruct worker to step outside overhead crane perimeter.",
          "role": "Floor Supervisor",
          "timeframe": "Immediate (<15m)"
        },
        "Immediate PPE Provision: Issue certified hard hat from PPE station."
      ]
    }"""
    result = AIOrchestrator._parse_response(raw, "ollama", "qwen2.5:3b-instruct")
    assert isinstance(result, AIAnalysisResult)
    assert len(result.immediate_actions) == 2
    assert result.immediate_actions[0].title == "Stop Worker"
    assert "hard hat" in result.immediate_actions[1].title or "hard hat" in result.immediate_actions[1].procedure


def test_json_reliability_9_completely_unrecoverable_garbage():
    raw = "<html><head><title>502 Bad Gateway</title></head><body>Server Error</body></html>"
    result = AIOrchestrator._parse_response(raw, "openrouter", "google/gemma-4-26b-a4b-it:free")
    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["error"] == "LLM returned malformed JSON"
    assert result["provider"] == "openrouter"


def test_json_reliability_10_real_captured_failing_response():
    # Exact structure captured from real runtime execution in task-8256.log
    # Prompt echoing created an input event dictionary followed by the structured analysis report
    raw = '''{
  "event_type": "fire_smoke",
  "camera": "d0000000-0000-0000-0000-000000000020",
  "zone": "Assembly Zone A",
  "source": {
    "type": "uploaded_video",
    "filename": "fire_02.mp4",
    "frame_index": 241,
    "evidence_image": "d0000000-0000-0000-0000-000000000001/caadc73f-fb25-44b7-a779-553a038f45de.jpg"
  },
  "details": {
    "bbox": [469.00885009765625, 8.87384033203125, 821.6253662109375, 385.5184020996094],
    "track_id": 17,
    "confidence": 0.79282546043396,
    "detected_class": "fire"
  },
  "recent_related_events": [
    "fire_smoke at 2026-09-10T01:14:47.514080+05:30 (severity: unknown)"
  ]
}
{
  "summary": "Fire/smoke detected with 79.3% confidence in Assembly Zone A.",
  "risk_explanation": "Critical severity assigned based on deterministic Risk Engine and high recurrence.",
  "hazard_interpretation": "Smoke density indicates active combustion. Escalation pathway includes rapid flame propagation across electrical raceways. Plant operations and adjoining zones face catastrophic interruption if uncontained.",
  "immediate_actions": [
    {
      "title": "Evacuate Assembly Zone A",
      "procedure": "Initiate emergency evacuation horn. Direct workers toward exit 4 away from smoke plume.",
      "rationale": "Immediate life safety protection from asphyxiation.",
      "role": "Floor Supervisor",
      "timeframe": "Immediate (<15m)",
      "expected_outcome": "100% headcount verified outside zone."
    },
    {
      "title": "Activate Deluge Pre-Action",
      "procedure": "Confirm dry-pipe system pre-action valve trip and inspect gauge pressure.",
      "rationale": "Prepare fire suppression boundary.",
      "role": "Safety Marshal",
      "timeframe": "Within 30m",
      "expected_outcome": "Water pressure verified at 120 PSI."
    },
    {
      "title": "De-energize Busbar 3",
      "procedure": "Open breaker 3A on main electrical panel to eliminate electrical ignition sources.",
      "rationale": "Prevents electrical fire escalation.",
      "role": "Maintenance Lead",
      "timeframe": "Within 1h",
      "expected_outcome": "Power disconnected confirmed via volt meter."
    }
  ],
  "investigation_actions": [
    {
      "title": "Physical Origin Inspection",
      "procedure": "Examine cable tray for insulation thermal degradation and arcing signs.",
      "rationale": "Isolate physical failure point.",
      "role": "Maintenance Lead",
      "timeframe": "Current Shift (<4h)",
      "expected_outcome": "Failure cause documented with photo evidence."
    },
    {
      "title": "YOLO Detection Frame Audit",
      "procedure": "Cross-reference camera timestamp against telemetry spikes.",
      "rationale": "Corroborate computer vision evidence with equipment load.",
      "role": "EHS Specialist",
      "timeframe": "Within 24h",
      "expected_outcome": "Timeline synchronization completed."
    }
  ],
  "preventive_actions": [
    {
      "title": "Install Thermal Imaging Cam",
      "procedure": "Mount fixed infrared radiometer above raceway junction.",
      "rationale": "Continuous automated temperature monitoring.",
      "role": "Operations Manager",
      "timeframe": "Next Maintenance Cycle",
      "expected_outcome": "Automated alarm threshold set at 65C."
    },
    {
      "title": "Update Hot Work Pre-Check SOP",
      "procedure": "Require 60-minute post-work fire watch for all maintenance in Zone A.",
      "rationale": "Prevent delayed smoldering fires.",
      "role": "EHS Specialist",
      "timeframe": "Within 7 Days",
      "expected_outcome": "SOP revised and signed by shift supervisors."
    }
  ],
  "recommended_actions": [
    "Evacuate Assembly Zone A: Initiate emergency evacuation horn.",
    "Activate Deluge Pre-Action: Confirm dry-pipe system pre-action valve trip.",
    "De-energize Busbar 3: Open breaker 3A on main electrical panel.",
    "Physical Origin Inspection: Examine cable tray for insulation thermal degradation."
  ],
  "safety_policy_guidance": "Adhere strictly to plant fire evacuation and isolation protocols.",
  "historical_context": "54 prior fire/smoke detections recorded in 30-day lookback window.",
  "uncertainties": [
    "Exact source of smoke cannot be confirmed from telemetry alone; physical inspection required."
  ]
}'''
    result = AIOrchestrator._parse_response(raw, "ollama", "qwen2.5:3b-instruct")
    assert isinstance(result, AIAnalysisResult)
    assert result.summary == "Fire/smoke detected with 79.3% confidence in Assembly Zone A."
    assert len(result.immediate_actions) == 3
    assert len(result.investigation_actions) == 2
    assert len(result.preventive_actions) == 2
    assert len(result.recommended_actions) == 4
    assert result.immediate_actions[0].role == "Floor Supervisor"
    assert result.preventive_actions[0].timeframe == "Next Maintenance Cycle"

