# SafeVision-AI Feature Mapping (Phase 2)

## 1. Computer Vision & Tracking
- **Status:** IMPLEMENTED
- **UI:** Video feed overlay, live monitoring dashboard
- **API:** WebSockets/Video Streaming endpoints
- **Backend Service:** YOLO inference, tracking logic, frame gap/cooldown
- **Database:** Events, zones, cameras
- **Execution Flow:** Camera/Video -> CV inference -> tracking -> detection adapter -> safety rules -> safety event
- **Tests:** CV inference tests present

## 2. Safety Event + Risk Engine
- **Status:** IMPLEMENTED
- **UI:** Event history, alerts list
- **API:** `GET /events`, risk assessment triggers
- **Backend Service:** Deterministic risk engine
- **Database:** `safety_events` table (risk score, confidence, etc.)
- **Execution Flow:** Detection -> Risk Engine -> Event Persistence

## 3. Evidence System
- **Status:** IMPLEMENTED
- **UI:** Evidence modal, annotated frame display
- **API:** `GET /evidence/{id}`
- **Backend Service:** Evidence capture and storage
- **Database:** File references linked to events

## 4. RAG / Safety Knowledge System
- **Status:** IMPLEMENTED
- **UI:** Document management
- **API:** PDF ingestion endpoints, search endpoints
- **Backend Service:** ChromaDB vector store, document parsing/chunking
- **Database:** ChromaDB (embeddings), Postgres (document metadata)

## 5. AI Safety Insights & Multimodal LLM
- **Status:** IMPLEMENTED (with limitations)
- **UI:** AI Insights page/modal
- **API:** OpenRouter Gemma API, Ollama fallback
- **Backend Service:** Prompt formatting, model selection, error handling
- **External Provider:** OpenRouter (Gemma), Ollama (Qwen)
- **Known Issue:** Free tier of Gemma subject to rate limiting, falls back to text-only Ollama.

## 6. Alert System
- **Status:** IMPLEMENTED
- **UI:** Alerts dashboard
- **API:** Alert resolution, acknowledgement
- **Backend Service:** Event-to-Alert mapping
- **Database:** Alerts table

## 7. Notifications (Email & WhatsApp)
- **Status:** PARTIALLY IMPLEMENTED
- **UI:** Settings page for notifications
- **External Provider:** Twilio, SMTP
- **Backend Service:** Notification service
- **Database:** Notification logs
- **Known Issue:** User reported Twilio Sandbox testing in recent prompt. Email implemented.

## 8. Authentication & RBAC
- **Status:** IMPLEMENTED
- **UI:** Login, protected routes
- **API:** JWT auth endpoints
- **Database:** Users, roles, permissions

## 9. Recurring Patterns
- **Status:** IMPLEMENTED / PARTIALLY IMPLEMENTED
- **UI:** Trends/Patterns dashboard
- **API:** Analytics endpoints

## 10. Export Report
- **Status:** TO BE VERIFIED
- **UI:** Export button
- **API:** Report generation endpoint
