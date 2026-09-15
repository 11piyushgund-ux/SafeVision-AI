SafeVision AI

AI-Powered Manufacturing Safety Monitoring & Safety Intelligence Platform

SafeVision AI is a full-stack industrial safety platform that combines Computer Vision, deterministic safety rules, risk assessment, AI reasoning, RAG-based safety knowledge, event intelligence, evidence management, and automated notifications.

The platform monitors workplace safety conditions from camera/video input, converts detections into structured safety events, evaluates their risk, generates contextual safety intelligence, and helps supervisors respond through a unified dashboard.

1. What SafeVision AI Does

SafeVision follows an end-to-end safety workflow:

Camera / Uploaded Video
        ↓
Computer Vision
        ↓
YOLO26 Detection + BoT-SORT Tracking
        ↓
Safety Rule Evaluation
        ↓
Safety Event
        ↓
Evidence Capture & Storage
        ↓
Risk Assessment
        ↓
AI Safety Intelligence
   ├── Specialized Safety Agents
   ├── RAG / Safety Knowledge
   └── Multimodal LLM Reasoning
        ↓
Risk Explanation & Recommendations
        ↓
Alert & Incident Management
        ↓
Email / WhatsApp Notifications
        ↓
Safety Review & Resolution

The system is designed to reduce dependence on continuous manual monitoring and provide safety teams with faster, structured, evidence-backed information about potentially dangerous situations.

2. Core Features

Computer Vision

PPE compliance detection

Worker/person detection

Fire detection

Smoke detection

Video ingestion and processing

Real-time safety event generation

Evidence frame capture and storage

BoT-SORT object tracking

Safety Rules & Event Intelligence

Configurable safety rules

PPE compliance evaluation

Restricted/exclusion zone evaluation

Confidence thresholds

Persistence-frame logic

Duplicate event suppression

Event cooldown handling

Structured Safety Event records

Risk assessment

Historical event analysis

Recurring violation detection

Incident and evidence management

AI Safety Intelligence

SafeVision includes a specialized AI reasoning layer coordinated by an AI Orchestrator.

Implemented reasoning/context components include:

Safety Policy Agent — connects events with relevant safety knowledge.

Investigation Agent — provides investigation-oriented event context.

Emergency Response Agent — provides emergency and response context for serious events.

Predictive Safety Agent — uses historical context to support recurring-risk analysis.

The AI layer is used for contextual interpretation and recommendations; deterministic event/risk/rule logic remains an important part of the safety decision pipeline.

3. AI / LLM Stack

SafeVision contains support for multiple LLM/provider configurations.

OpenRouter + Gemma

The current project has a verified multimodal OpenRouter path using:

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemma-4-26b-a4b-it:free

The multimodal path can send the event evidence image together with the analysis prompt and structured event context.

Verified report-generation flow:

Safety Event
   ↓
Event Metadata + Risk + History + RAG Context
   ↓
Evidence Image
   ↓
OpenRouter
   ↓
Google Gemma 4 26B A4B
   ↓
Multimodal Safety Analysis

Gemini

The backend also contains Gemini provider configuration/support:

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

Ollama

Local Ollama support is available for local inference/fallback configurations:

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M

Provider/model selection depends on the active local configuration. Never commit API keys or provider secrets.

4. RAG / Safety Knowledge Base

SafeVision includes a Retrieval-Augmented Generation pipeline for approved safety documentation.

The RAG layer is used to provide relevant safety context to the reasoning pipeline.

Current project configuration includes:

Embedding model: all-MiniLM-L6-v2

Embedding dimension: 384

Chunk size: 512 characters

Chunk overlap: 64 characters

Vector database: ChromaDB

Default retrieval: top 5 results

Conceptually:

Safety Documents
      ↓
Document Ingestion
      ↓
Text Chunking
      ↓
Embeddings
      ↓
ChromaDB
      ↓
Relevant Safety Context
      ↓
Safety Policy / AI Context
      ↓
AI Orchestrator

Supported safety knowledge can include:

SOPs

PPE policies

Emergency procedures

Safety guidelines

Compliance information

5. AI Safety Insight Output

For a selected safety event, SafeVision can generate detailed safety intelligence including:

Event Summary

Hazard Interpretation

Risk Explanation

Visual Evidence Validation

Visual Observations

Contributing Factors

Uncertainties / Epistemic Boundaries

Immediate Actions

Investigation Actions

Preventive Actions

Safety Policy Guidance

Historical Context

Recommended Actions

The system preserves the distinction between:

deterministic safety/risk decisions

and

AI-generated contextual reasoning and recommendations.

6. Event Evidence / Visual Proof

Each Safety Event can have authoritative evidence associated with it.

The same event evidence used by the multimodal analysis pipeline can be displayed in the AI Safety Insights → Event Evidence view.

The interface supports:

authenticated evidence retrieval

event-specific evidence display

responsive image viewing

fullscreen evidence viewing

event metadata

clean empty state when evidence is unavailable

No duplicate evidence capture is required.

7. Alerts & Incident Management

Once a safety event passes the event/risk pipeline, SafeVision creates and manages alerts.

Alert data can include:

Alert ID

Event type

Camera/source

Zone/location

Timestamp

Confidence

Risk level

Risk score

Status

Description

Evidence

Supervisors can review alerts and manage their lifecycle, including acknowledgement and resolution workflows.

8. Notifications

SafeVision supports automated safety notifications through:

Email

Safety Alert
   ↓
NotificationService
   ↓
EmailProvider
   ↓
SMTP / Gmail
   ↓
Recipient Inbox

Email notifications can include:

alert information

event information

risk information

timestamps

camera/zone information

safety description

evidence image attachment when available

WhatsApp

Safety Alert
   ↓
NotificationService
   ↓
WhatsAppProvider
   ↓
Twilio
   ↓
WhatsApp Recipient

WhatsApp notifications are intentionally text-only in the current implementation.

Typical flow:

Fire / Smoke / PPE Alert
        ↓
WhatsApp text notification

The same organization notification settings support both channels.

9. Dual Notification Recipients

Notification settings support independent recipients for both channels:

Notification Mode:
    Email
    or
    WhatsApp

Email Recipient:
    user@example.com

WhatsApp Recipient:
    +919xxxxxxxxx

Both recipient values are stored independently.

Changing the active notification mode does not erase the recipient configured for the other channel.

10. Authentication & Security

SafeVision uses a custom backend authentication and authorization architecture.

Authentication

JWT-based authentication

hashed passwords

authenticated API access

persistent/session login behavior

protected routes

logout and session cleanup

RBAC

The backend uses role/permission based access control for protected functionality.

Examples include permissions for:

alerts

events

documents

users

AI functions

notifications

settings

cameras

zones

Authorization is enforced server-side.

Multi-Tenancy

Organization ownership is enforced server-side.

Organization-owned resources are isolated by org_id and authenticated user context.

Client-supplied organization identifiers are not treated as a trust boundary.

11. Technology Stack

Backend

Python

FastAPI

SQLAlchemy

Alembic

PostgreSQL

Redis

Pydantic

pydantic-settings

JWT authentication

Structlog / structured logging

Frontend

React

TypeScript

Vite

TanStack Start / Router

Tailwind CSS

Recharts

React Hook Form

Zod

Computer Vision / ML

Python

Ultralytics

YOLO26

PyTorch

BoT-SORT

PPE detection model

Fire/Smoke detection model

AI / RAG

OpenRouter

Google Gemma

Gemini support

Ollama

Sentence Transformers

all-MiniLM-L6-v2

ChromaDB

Notifications

SMTP

Gmail SMTP / STARTTLS

Twilio WhatsApp

12. Project Structure

SafeVision-AI/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── cv/
│   │   ├── middleware/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── llm/
│   │   │   └── notifications/
│   │   ├── utils/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   │
│   ├── migrations/
│   ├── scripts/
│   ├── tests/
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── .env.sample
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
│
├── models/
│   ├── ppe/
│   └── fire_smoke/
│
├── RAG_test_docs/
│
└── README.md

13. Backend API Modules

The FastAPI backend exposes modules for:

Authentication

Users

Health

Cameras

Zones / Rules

Events

Alerts

AI Safety Analysis

Safety Documents / RAG

Patterns

Statistics

Video Streaming

Notifications

Interactive API documentation is available through FastAPI Swagger UI.

14. Database

SafeVision uses PostgreSQL as its primary transactional database.

Development example:

Database: safevision_db
Host: localhost
Port: 5432

Use environment variables for actual credentials.

Alembic manages schema migrations.

Do not commit database passwords or other credentials to source control.

15. Running the Project — Windows

Prerequisites

Install:

Python 3.x

Node.js + npm

PostgreSQL

Redis

Git

Optional depending on your active AI configuration:

Ollama

Gemini API access

OpenRouter API access

Backend

cd D:\SafeVision-AI\backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

Backend:

http://127.0.0.1:8000

Swagger:

http://127.0.0.1:8000/docs

Frontend

Open a second PowerShell:

cd D:\SafeVision-AI\frontend
npm run dev -- --port 8080

Frontend:

http://localhost:8080

Redis

If Redis is not already running:

redis-server

16. Useful Development Commands

Backend tests

cd D:\SafeVision-AI\backend
python -m pytest tests/test_notifications.py -v

Frontend type check

cd D:\SafeVision-AI\frontend
npx tsc --noEmit

Frontend build

cd D:\SafeVision-AI\frontend
npm run build

Database migrations

cd D:\SafeVision-AI\backend
alembic upgrade head

17. Environment Variables

The real environment file is:

backend/.env

Never commit the real .env.

Use:

backend/.env.sample

as the safe template.

Provider/configuration examples include:

DATABASE_URL=
REDIS_URL=
JWT_SECRET_KEY=

OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemma-4-26b-a4b-it:free

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M

Notification provider credentials are also configured through environment variables.

Never commit:

API keys

JWT secrets

SMTP passwords / App Passwords

Twilio Auth Tokens

database passwords

OAuth client secrets

18. Report Export

SafeVision includes an Export Report function in AI Safety Insights.

The export is assembled from persisted data and does not regenerate the AI analysis.

The report can include:

SafeVision branding

Event information

Risk information

Event evidence

AI analysis

visual observations

recommendations

safety guidance

historical context

audit metadata

The export uses the currently selected insight and its corresponding event evidence.

19. Testing Coverage

The backend test suite covers areas including:

authentication

authorization / RBAC

AI reasoning

rule engine

risk engine

event engine

alerts

patterns

RAG

document ingestion

evidence

computer vision integration

fire/smoke pipeline

notifications

OpenRouter provider

API behavior

Notification testing additionally covers:

email routing

WhatsApp routing

provider failures

duplicate protection

failure isolation

tenant isolation

recipient validation

channel-specific recipients

20. Safety Event Flow

A simplified production workflow is:

Camera / Video
      ↓
YOLO26 + BoT-SORT
      ↓
Detection
      ↓
Safety Rule Evaluation
      ↓
Temporal Persistence / Duplicate Suppression
      ↓
Safety Event
      ↓
Risk Assessment
      ↓
Evidence
      ↓
Alert
      ↓
AI Safety Intelligence
      ↓
Recommendations
      ↓
Notification
      ↓
Supervisor Review / Resolution

21. Key Design Principles

Deterministic safety controls

Safety rules and risk logic provide deterministic controls for event classification and prioritization.

AI as a reasoning layer

LLMs provide contextual interpretation, explanations, and recommendations rather than replacing deterministic safety controls.

Evidence-backed intelligence

AI analysis can use the event's authoritative evidence frame alongside structured event metadata.

Organization isolation

Safety data, settings, and operational records are scoped to the authenticated organization.

Provider abstraction

Email and WhatsApp share the common notification architecture while using separate provider implementations.

22. Current Project Capabilities

The current project includes verified workflows for:

PPE detection

Fire/Smoke detection

Safety event generation

Risk assessment

Evidence capture

AI Safety Insights

Multimodal Gemma analysis through OpenRouter

RAG-based safety knowledge

Event Evidence display

Exportable safety reports

Email safety notifications

WhatsApp safety notifications through Twilio

Independent email and WhatsApp recipients

RBAC and organization-level access control

23. Future Scope

Potential extensions include:

Multi-Agent AI specialization and orchestration improvements

Predictive risk analysis

Additional safety scenarios and detection classes

Expanded CCTV/IP camera integrations

Advanced safety analytics

Enhanced recurring-violation reporting

Voice-based safety assistant

Broader deployment across manufacturing and industrial environments

24. Production Considerations

Before production deployment:

replace development database credentials

generate a strong random JWT secret

enable HTTPS

restrict CORS to trusted origins

store API keys in a secure secret manager/environment

secure PostgreSQL

secure Redis

review SMTP/Twilio configuration

review file upload limits

secure evidence storage

review RBAC assignments

review authentication flows

monitor safety events and application logs

protect all secrets from Git history

25. Project Status

SafeVision AI is a final-year AI/ML software project focused on AI-powered industrial safety monitoring and safety intelligence.

The platform combines:

Computer Vision + YOLO26 + BoT-SORT + Safety Rules + Risk Assessment + Evidence + Multi-Agent AI + RAG + Multimodal LLM Reasoning + Alerts + Email + WhatsApp + Incident Intelligence

26. License

This project is intended for academic and project development unless a separate license is provided by the project owner.
