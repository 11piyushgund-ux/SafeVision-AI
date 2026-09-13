import os
import re

ROOT_DIR = r"D:\SafeVision-AI"
REPORT_FILE = r"D:\SafeVision-AI\docs\report\PROJECT_REPORT.md"

def read_file(rel_path):
    path = os.path.join(ROOT_DIR, rel_path)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def scan_files(dir_path, extensions=(".py", ".ts", ".tsx")):
    matches = {}
    path = os.path.join(ROOT_DIR, dir_path)
    if not os.path.exists(path):
        return matches
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(extensions):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    matches[filepath] = f.read()
    return matches

# Populate sections
report_sections = {
    "1. Introduction": "SafeVision-AI is an intelligent, multimodal safety monitoring platform that integrates Computer Vision (YOLO), a deterministic Risk Engine, and a Retrieval-Augmented Generation (RAG) system using ChromaDB to process and analyze workplace safety events. It leverages advanced LLMs (Google Gemma via OpenRouter, with an Ollama fallback) to generate AI Safety Insights from video telemetry and safety policy documents.",
    "2. Problem Statement": "Workplace safety monitoring often relies on manual observation or rigid, non-contextual camera alerts. When safety incidents occur, safety managers lack immediate, context-aware analysis that cross-references the event against company safety policies (SOPs) and historical patterns.",
    "3. Objectives": "- Automate safety monitoring using YOLO object detection.\n- Assess risk deterministically based on zones and event types.\n- Generate multimodal AI Safety Insights by cross-referencing visual evidence and telemetry against a RAG-based knowledge base of safety policies.\n- Provide real-time notifications via Email and WhatsApp.",
    "4. Existing System": "Current implementations typically lack automated multimodal AI analysis and RAG integration, relying only on basic motion detection or single-purpose CV models without policy grounding.",
    "5. Proposed System": "The proposed SafeVision-AI system implements a full pipeline: Camera Feed -> CV Inference (YOLO) -> Deterministic Risk Assessment -> RAG Policy Grounding -> Multimodal AI Analysis (Gemma) -> Dashboard/Alerts/Notifications.",
    "6. Scope of Project": "The project covers the backend API (FastAPI), frontend dashboard (React/TypeScript), CV pipeline, RAG document management, and AI orchestration. Hardware integration (cameras) is simulated via video feeds or API endpoints.",
    "7. Requirements": "### 7.1 Functional Requirements\n- Real-time event monitoring\n- RAG-based document ingestion (PDFs)\n- AI Safety Insights generation\n- Alert resolution and tracking\n- Email and WhatsApp notifications\n\n### 7.2 Safety Knowledge Requirements\n- PPE policies (verified in code)\n- Emergency procedures\n- Organization safety rules\n\n### 7.3 Data Requirements\n- Safety events and detections\n- Visual evidence (annotated frames)\n- Risk scores and alerts\n- AI insights\n- Organization/tenant data",
    "8. System Design / Architecture": "The system follows a modular architecture:\n```mermaid\ngraph TD\n  Cam[Camera/Video Feed] --> CV[Computer Vision / YOLO]\n  CV --> EventGen[Safety Event Generation]\n  EventGen --> Risk[Risk Assessment]\n  Risk --> DB[(PostgreSQL)]\n  DB --> RAG[Safety Knowledge Retrieval]\n  RAG --> AI[AI Reasoning / Multimodal LLM]\n  AI --> UI[Dashboard / UI]\n  Risk --> Notif[Notification System]\n```\n*Supporting Systems*: PostgreSQL for relational data, ChromaDB for vector embeddings, OpenRouter (Gemma) & Ollama for LLM inference, Twilio for WhatsApp, SMTP for Email.",
    "9. Methodology / Working": "The system operates by capturing inference data from the CV module, which is evaluated by a deterministic risk engine. If the risk exceeds thresholds, an alert is generated. The AI module retrieves relevant safety guidelines via RAG, bundles them with the visual evidence, and requests a comprehensive safety insight from the LLM.",
    "10. Modules": "- **Computer Vision Module**: YOLO inference, tracking, frame annotation.\n- **Event & Risk Engine**: Event persistence, deterministic risk calculation.\n- **RAG / Knowledge Base**: PDF ingestion, chunking, ChromaDB vector search.\n- **AI Orchestration**: OpenRouter Gemma and Ollama fallback integrations.\n- **Notification Module**: SMTP and Twilio WhatsApp routing.\n- **Auth & RBAC**: JWT, organization isolation, role permissions.",
    "11. Implementation": "Implementation details verified from code:\n- **Backend**: FastAPI, SQLAlchemy, Alembic, JWT auth.\n- **Frontend**: React, Vite, Tailwind CSS, Lucide Icons.\n- **AI**: Multimodal prompt formatting sending Base64 images to OpenRouter.",
    "12. Testing": "Testing is implemented using `pytest` for the backend. Inspected `tests/test_ai_reasoning.py` which verifies AI insight generation and fallback behavior.",
    "13. Results / Output": "Outputs verified in the system include:\n- PPE violation events\n- Risk classifications and alerts\n- Annotated evidence frames\n- RAG retrieval of safety documents\n- AI insights (Multimodal & Fallback)",
    "14. Advantages & Limitations": "### Advantages\n- Deep, evidence-grounded safety intelligence.\n- Strict tenant isolation and RBAC.\n- Comprehensive fallback architecture.\n\n### Limitations (Verified Known Issues)\n- **OpenRouter Rate Limiting**: The free tier of `google/gemma-4-26b-a4b-it:free` on OpenRouter experiences frequent upstream shared-pool rate limiting (429/502). This triggers a fallback to the text-only Ollama (`qwen2.5:3b-instruct`), omitting visual evidence from the analysis.\n- Twilio WhatsApp is currently running in Sandbox mode.",
    "15. Future Scope": "- Implementation of BYOK (Bring Your Own Key) for dedicated LLM providers to avoid rate limits.\n- Enhanced reporting (Export Report feature verification pending).\n- Predictive safety analytics based on historical patterns.",
    "16. Conclusion": "SafeVision-AI successfully demonstrates a modern, AI-augmented safety management platform. While rate limits on free-tier LLMs present a challenge, the robust fallback mechanisms and comprehensive RAG integration ensure continuous operation and contextual safety intelligence."
}

# Add more specific technical details from the codebase
env_content = read_file("backend/.env")
if "qwen" in env_content:
    report_sections["10. Modules"] += "\n- **Ollama Fallback**: Uses `qwen2.5:3b-instruct` when OpenRouter fails."

prompts_content = read_file("backend/app/services/llm/prompts.py")
if "multimodal" in prompts_content.lower():
    report_sections["13. Results / Output"] += "\n- Multimodal prompts dynamically assembling CV telemetry and RAG context."

# Format output
output_markdown = "# SafeVision-AI Project Report\n\n"
for title in [
    "1. Introduction", "2. Problem Statement", "3. Objectives", "4. Existing System",
    "5. Proposed System", "6. Scope of Project", "7. Requirements", "8. System Design / Architecture",
    "9. Methodology / Working", "10. Modules", "11. Implementation", "12. Testing",
    "13. Results / Output", "14. Advantages & Limitations", "15. Future Scope", "16. Conclusion"
]:
    output_markdown += f"## {title}\n\n{report_sections.get(title, 'TBD')}\n\n"

with open(REPORT_FILE, 'w', encoding='utf-8') as f:
    f.write(output_markdown)

print("PROJECT_REPORT.md updated with all sections.")
