# SafeVision-AI Project Repository Inventory
## Excluded Directories
The following directories were intentionally skipped as they contain generated, vendor, or cache files:
- `.git`: Version control history
- `node_modules`: Frontend dependencies
- `.venv`: Python virtual environment
- `__pycache__`: Python bytecode caches
- `.pytest_cache`: Test caches
- `dist` / `build` / `.next` / `out`: Frontend build output
- `docs`: The generated documentation itself
- `D:\SafeVision-AI_BACKUP_PHASE10B`: Backup directory

## Inventory
| Path | Category | Purpose | Important Classes/Functions | Contributes to Prod? | Report Sections | Status |
|------|----------|---------|-----------------------------|-----------------------|-----------------|--------|
| `deep-research-report.md` | Documentation | Implementation | N/A | Yes | General | [x] Verified |
| `PHASE_13_IMPLEMENTATION_PLAN.md` | Documentation | Implementation | N/A | Yes | General | [x] Verified |
| `PHASE_13_TASKS.md` | Documentation | Implementation | N/A | Yes | General | [x] Verified |
| `backend/pyproject.toml` | Unknown | Implementation | N/A | Yes | 4. Backend | [x] Verified |
| `backend/requirements.txt` | Dependency Manifest | Implementation | N/A | Yes | 4. Backend | [x] Verified |
| `backend/test_output.txt` | Unknown | Testing | N/A | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/app/config.py` | Unknown | Implementation | Settings, get_settings, cors_origins_list, is_production, log_level_int | Yes | 4. Backend | [x] Verified |
| `backend/app/database.py` | Unknown | Implementation | Base, get_engine, get_db | Yes | 4. Backend | [x] Verified |
| `backend/app/main.py` | Unknown | Implementation | create_app | Yes | 4. Backend | [x] Verified |
| `backend/app/__init__.py` | Unknown | Implementation | None | Yes | 4. Backend | [x] Verified |
| `backend/app/api/ai_analysis.py` | API Route | Implementation | analyze_safety_event, _require_ai_permission, analyze_real_event, list_insights, list_providers | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/alerts.py` | API Route | Implementation | list_alerts, get_alert, get_alert_evidence, transition_alert | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/auth.py` | API Route | Implementation | login | Yes | 4. Backend<br>4. APIs<br>6. Auth/RBAC | [x] Verified |
| `backend/app/api/cameras.py` | API Route | Implementation | list_cameras, list_zones | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/documents.py` | API Route | Implementation | list_documents, get_document, delete_document, search_knowledge | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/events.py` | API Route | Implementation | list_events, get_event, get_event_evidence | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/health.py` | API Route | Implementation | DependencyStatus, HealthResponse, health_check, _check_database, _check_redis | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/notifications.py` | API Route | Implementation | get_notification_settings, save_notification_settings, list_notifications, get_notification | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/patterns.py` | API Route | Implementation | list_patterns | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/rules.py` | API Route | Implementation | get_controls, update_detection_filter, update_restricted_area | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/stats.py` | API Route | Implementation | get_summary | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/users.py` | API Route | Implementation | get_me, list_users, create_user, get_user | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/video_stream.py` | API Route | Implementation | delete_video_session | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/api/__init__.py` | API Route | Implementation | None | Yes | 4. Backend<br>4. APIs | [x] Verified |
| `backend/app/cv/botsort.yaml` | Configuration | Implementation | N/A | Yes | 4. Backend<br>7. CV | [x] Verified |
| `backend/app/cv/__init__.py` | Unknown | Implementation | None | Yes | 4. Backend<br>7. CV | [x] Verified |
| `backend/app/middleware/auth.py` | Unknown | Implementation | get_current_user, get_current_org_id, require_permission, _check_permission | Yes | 4. Backend<br>6. Auth/RBAC | [x] Verified |
| `backend/app/middleware/__init__.py` | Unknown | Implementation | None | Yes | 4. Backend | [x] Verified |
| `backend/app/models/ai_insight.py` | Database Model | Implementation | InsightType, InsightStatus, AiInsight | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/alert.py` | Database Model | Implementation | AlertSeverity, AlertStatus, Alert, AlertState | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/audit_log.py` | Database Model | Implementation | AuditLog | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/camera.py` | Database Model | Implementation | CameraStatus, Camera | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/document.py` | Database Model | Implementation | DocumentStatus, DocumentType, SafetyDocument, DocumentChunk | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/event.py` | Database Model | Implementation | EventType, Event | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/notification.py` | Database Model | Implementation | NotificationChannel, NotificationStatus, Notification | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/organization.py` | Database Model | Implementation | OrgStatus, Organization | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/org_notification_settings.py` | Database Model | Implementation | NotificationMode, OrgNotificationSettings | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/pattern.py` | Database Model | Implementation | PatternType, PatternStatus, Pattern | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/role.py` | Database Model | Implementation | Role, Permission, has_permission | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/safety_rule.py` | Database Model | Implementation | RuleType, RuleSeverity, RuleStatus, SafetyRule | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/site.py` | Database Model | Implementation | SiteStatus, Site | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/user.py` | Database Model | Implementation | UserStatus, User, has_permission | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/zone.py` | Database Model | Implementation | ZoneType, ZoneStatus, Zone | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/models/__init__.py` | Database Model | Implementation | None | Yes | 4. Backend<br>5. Database | [x] Verified |
| `backend/app/schemas/ai_analysis.py` | Pydantic Schema | Implementation | SafetyActionItem, AIAnalysisResult, AIAnalysisRequest, AIAnalysisResponse, AiInsightResponse... | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/alert.py` | Pydantic Schema | Implementation | AlertTransitionRequest, AlertStateResponse, AlertResponse, AlertDetailResponse, AlertListResponse | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/auth.py` | Pydantic Schema | Implementation | LoginRequest, LoginResponse, TokenPayload, OrgCreate, OrgResponse... | Yes | 4. Backend<br>6. Auth/RBAC | [x] Verified |
| `backend/app/schemas/camera_schema.py` | Pydantic Schema | Implementation | CameraResponse, ZoneResponse | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/detection.py` | Pydantic Schema | Implementation | DetectionItem, DetectionPayload, RuleViolation, RuleEvaluationResult | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/document.py` | Pydantic Schema | Implementation | DocumentUploadRequest, KnowledgeSearchRequest, DocumentChunkResponse, DocumentResponse, DocumentDetailResponse... | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/event_schema.py` | Pydantic Schema | Implementation | EventResponse, EventListResponse | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/notification_schema.py` | Pydantic Schema | Implementation | NotificationResponse, NotificationListResponse, OrgNotificationSettingsResponse, OrgNotificationSettingsUpdate | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/pattern_schema.py` | Pydantic Schema | Implementation | DailyTrendItem, PatternResponse, PatternListResponse | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/risk.py` | Pydantic Schema | Implementation | RiskFactor, RiskAssessment | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/rule_schema.py` | Pydantic Schema | Implementation | DetectionFilterUpdate, RestrictedAreaUpdate, ControlsResponse | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/stats_schema.py` | Pydantic Schema | Implementation | DashboardSummary | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/video_schema.py` | Pydantic Schema | Implementation | VideoUploadResponse, WSAuthMessage, WSControlMessage, WSDetectionItem, WSZoneViolation... | Yes | 4. Backend | [x] Verified |
| `backend/app/schemas/__init__.py` | Pydantic Schema | Implementation | None | Yes | 4. Backend | [x] Verified |
| `backend/app/seeds/seed_roles.py` | Unknown | Implementation | seed_org_roles, seed_demo_data | Yes | 4. Backend | [x] Verified |
| `backend/app/seeds/__init__.py` | Unknown | Implementation | None | Yes | 4. Backend | [x] Verified |
| `backend/app/services/alert_engine.py` | Backend Service | Implementation | AlertEngine, InvalidTransitionError, _generate_title, _risk_level_to_severity, create_alert_from_risk... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/auth_service.py` | Backend Service | Implementation | hash_password, verify_password, create_access_token, decode_access_token | Yes | 4. Backend<br>6. Auth/RBAC | [x] Verified |
| `backend/app/services/cv_pipeline.py` | Backend Service | Implementation | CVPipeline, process_frame | Yes | 4. Backend<br>7. CV | [x] Verified |
| `backend/app/services/detection_adapter.py` | Backend Service | Implementation | DetectionAdapter, adapt, merge_payloads | Yes | 4. Backend | [x] Verified |
| `backend/app/services/document_service.py` | Backend Service | Implementation | DocumentService, ingest, extract_text_from_pdf, chunk_text, get_document... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/embedding_service.py` | Backend Service | Implementation | EmbeddingService, _get_model, embed_texts, embed_query, get_dimension | Yes | 4. Backend | [x] Verified |
| `backend/app/services/event_engine.py` | Backend Service | Implementation | ViolationState, ViolationTracker, EventEngine, _make_key, _get_rule_parameters... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/evidence_service.py` | Backend Service | Implementation | EvidenceService, get_storage_base_dir, get_tenant_dir, annotate_frame, capture_and_save... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/geometry.py` | Backend Service | Implementation | calculate_centroid, bbox_contains, point_in_polygon | Yes | 4. Backend | [x] Verified |
| `backend/app/services/inference.py` | Backend Service | Implementation | ModelType, InferenceService, get_inference_service, _get_model_path, _load_model... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/knowledge_base.py` | Backend Service | Implementation | KnowledgeBase, _get_chroma_client, _collection_name, store_chunks, search... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/notification_service.py` | Backend Service | Implementation | NotificationService, _build_message, _build_whatsapp_body, _mode_to_channel, _get_provider... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/pattern_engine.py` | Backend Service | Implementation | PatternEngine, _get_utc_date_str, _generate_pattern_title, _generate_pattern_description, reconcile_legacy_seed_patterns... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/risk_engine.py` | Backend Service | Implementation | RiskEngine, _extract_event_type, _extract_zone_type, _score_zone, _score_confidence... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/rule_engine.py` | Backend Service | Implementation | SafetyRuleEngine, _associate_ppe_to_persons, evaluate_ppe, evaluate_restricted_zone, evaluate_fire_smoke... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/video_service.py` | Backend Service | Implementation | VideoSession, VideoService, cleanup, get_upload_dir, create_session... | Yes | 4. Backend | [x] Verified |
| `backend/app/services/__init__.py` | Backend Service | Implementation | None | Yes | 4. Backend | [x] Verified |
| `backend/app/services/llm/agents.py` | Backend Service | Implementation | SafetyPolicyAgent, InvestigationAgent, EmergencyResponseAgent, PredictiveSafetyAgent, build_context... | Yes | 4. Backend<br>13. AI/LLM | [x] Verified |
| `backend/app/services/llm/gemini_provider.py` | Backend Service | Implementation | GeminiProvider, name, model_name, generate, health_check | Yes | 4. Backend<br>13. AI/LLM | [x] Verified |
| `backend/app/services/llm/ollama_provider.py` | Backend Service | Implementation | OllamaProvider, name, model_name, generate, health_check | Yes | 4. Backend<br>13. AI/LLM | [x] Verified |
| `backend/app/services/llm/openrouter_provider.py` | Backend Service | Implementation | OpenRouterProvider, name, model_name, generate, health_check... | Yes | 4. Backend<br>13. AI/LLM | [x] Verified |
| `backend/app/services/llm/orchestrator.py` | Backend Service | Implementation | AIOrchestrator, analyze, _parse_response, _robust_decode, _to_action_items... | Yes | 4. Backend<br>13. AI/LLM | [x] Verified |
| `backend/app/services/llm/prompts.py` | Backend Service | Implementation | build_event_context, build_risk_context, build_rag_context, build_historical_context, build_detection_metadata_context... | Yes | 4. Backend<br>13. AI/LLM | [x] Verified |
| `backend/app/services/llm/provider_factory.py` | Backend Service | Implementation | ProviderError, get_provider, generate_with_fallback | Yes | 4. Backend<br>13. AI/LLM | [x] Verified |
| `backend/app/services/llm/__init__.py` | Backend Service | Implementation | LLMRequest, LLMResponse, LLMProvider, name, model_name... | Yes | 4. Backend<br>13. AI/LLM | [x] Verified |
| `backend/app/services/notifications/base_provider.py` | Backend Service | Implementation | ProviderError, BaseNotificationProvider, send, provider_name | Yes | 4. Backend | [x] Verified |
| `backend/app/services/notifications/email_provider.py` | Backend Service | Implementation | EmailProvider, provider_name, _check_config, send | Yes | 4. Backend | [x] Verified |
| `backend/app/services/notifications/whatsapp_provider.py` | Backend Service | Implementation | WhatsAppProvider, provider_name, _check_config, _normalize_recipient, send | Yes | 4. Backend | [x] Verified |
| `backend/app/services/notifications/__init__.py` | Backend Service | Implementation | None | Yes | 4. Backend | [x] Verified |
| `backend/app/utils/__init__.py` | Unknown | Implementation | None | Yes | 4. Backend | [x] Verified |
| `backend/migrations/env.py` | Unknown | Implementation | run_migrations_offline, run_migrations_online | Yes | 4. Backend | [x] Verified |
| `backend/migrations/versions/8309e67a93a6_add_sites_zones_cameras_rules_events_.py` | Unknown | Implementation | upgrade, downgrade | Yes | 4. Backend | [x] Verified |
| `backend/migrations/versions/9421176104ed_add_safety_documents_and_chunks_tables.py` | Unknown | Implementation | upgrade, downgrade | Yes | 4. Backend | [x] Verified |
| `backend/migrations/versions/b7f3a21c90de_add_pdf_to_document_type.py` | Unknown | Implementation | upgrade, downgrade | Yes | 4. Backend | [x] Verified |
| `backend/migrations/versions/c3f5d89e1a2b_add_notifications_table_and_org_notification_settings.py` | Unknown | Implementation | upgrade, downgrade | Yes | 4. Backend | [x] Verified |
| `backend/migrations/versions/dff8a20ed80f_create_organizations_users_roles_.py` | Unknown | Implementation | upgrade, downgrade | Yes | 4. Backend | [x] Verified |
| `backend/scratch/capture_failing_response.py` | Unknown | Implementation | None | Yes | 4. Backend | [x] Verified |
| `backend/scratch/inspect_orchestrator_debug.py` | Unknown | Implementation | debug_parse | Yes | 4. Backend | [x] Verified |
| `backend/scratch/verify_phase14f_runtime.py` | Unknown | Implementation | get_auth_token, test_analyze_real_event | Yes | 4. Backend | [x] Verified |
| `backend/scripts/seed_dev_data.py` | Unknown | Implementation | get_or_create, seed | Yes | 4. Backend | [x] Verified |
| `backend/scripts/verify_real_model.py` | Unknown | Implementation | E2ETestRule, main | Yes | 4. Backend | [x] Verified |
| `backend/tests/conftest.py` | Test | Testing | client | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_ai_reasoning.py` | Test | Testing | TestProviderInterface, TestProviderBehavior, TestErrorHandling, TestStructuredOutput, TestRAGAndRiskIntegration... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_alert_engine.py` | Test | Testing | TestAlertCreation, TestValidLifecycle, TestInvalidLifecycle, TestPermissions, TestAuditTrail... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_auth_rbac_idor.py` | Test | Testing | TestAuth, TestRBAC, TestIDOR, _override_get_db, _create_org... | No | 4. Backend<br>6. Auth/RBAC<br>24. Testing | [x] Verified |
| `backend/tests/test_cv_integration.py` | Test | Testing | MockBoxes, MockResult, MockRule, MockZone, MockDBSession... | No | 4. Backend<br>7. CV<br>24. Testing | [x] Verified |
| `backend/tests/test_evidence_capture.py` | Test | Testing | db, setup_test_evidence_env, auth_header_a, auth_header_b, sample_frame... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_fire_smoke_pipeline.py` | Test | Testing | MockRule, test_fire_confidence_0_49_rejected, test_fire_confidence_0_499_rejected, test_fire_confidence_0_50_accepted, test_fire_confidence_0_51_accepted... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_health.py` | Test | Testing | TestHealthEndpoint, _mock_db_dependency, setup_method, teardown_method, test_health_returns_200... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_notifications.py` | Test | Testing | TestEmailProvider, TestWhatsAppProvider, TestProviderRouting, TestNotificationLifecycle, TestFailureIsolation... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_openrouter_provider.py` | Test | Testing | TestProviderInterface, TestProviderRegistration, TestRequestConstruction, TestSuccessResponse, TestErrorHandling... | No | 4. Backend<br>13. AI/LLM<br>24. Testing | [x] Verified |
| `backend/tests/test_pattern_engine.py` | Test | Testing | db_session, test_org_environment, test_pattern_engine_dynamic_database_assertions, test_reconcile_legacy_seed_patterns_marks_dismissed_no_deletion, test_pattern_status_no_inferred_resolution_for_inactivity... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_pdf_ingestion.py` | Test | Testing | TestPDFDetection, TestPDFExtraction, TestPDFIngestionAndProvenance, TestPDFAPI, TestBackwardCompatibility... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_phase10b_api.py` | Test | Testing | TestEventsAPI, TestCamerasAPI, TestZonesAPI, TestPatternsAPI, TestStatsAPI... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_phase11b_controls.py` | Test | Testing | db, setup_data, admin_headers, viewer_headers, test_get_controls_initial... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_phase14f_structured_report.py` | Test | Testing | test_safety_action_item_model, test_ai_analysis_result_coerces_structured_dicts, test_ai_analysis_result_coerces_legacy_strings, test_ai_analysis_result_coerces_mixed_array, test_orchestrator_parse_structured_actions... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_provider_fallback.py` | Test | Testing | _override_get_db, _mock_provider, test_primary_timeout_triggers_fallback, test_primary_http_429_triggers_fallback, test_primary_http_500_triggers_fallback... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_rag.py` | Test | Testing | TestDocumentIngestion, TestChunking, TestEmbeddings, TestVectorStorage, TestRetrieval... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_risk_engine.py` | Test | Testing | MockEvent, MockZone, TestRiskLevels, TestFactorWeighting, TestRecurrenceScale... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_rule_engine.py` | Test | Testing | MockRule, MockZone, TestGeometryUtilities, TestPPEAssociation, TestPPEViolations... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_video_pipeline.py` | Test | Testing | db, setup_test_data, auth_headers_a, auth_headers_b, sample_mp4_bytes... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_visual_observations_normalization.py` | Test | Testing | TestVisualObservationsNormalization, test_1_list_of_strings_preserved, test_2_structured_dicts_converted_to_strings, test_3_mixed_strings_and_dicts, test_4_malformed_and_unexpected_values... | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/test_whatsapp_live.py` | Test | Testing | load_dotenv | No | 4. Backend<br>24. Testing | [x] Verified |
| `backend/tests/__init__.py` | Test | Testing | None | No | 4. Backend<br>24. Testing | [x] Verified |
| `frontend/AGENTS.md` | Documentation | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/bun.lock` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/bunfig.toml` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/components.json` | Configuration | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/eslint.config.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/fix_api_types.py` | Unknown | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/package-lock.json` | Configuration | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/package.json` | Dependency Manifest | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/README.md` | Documentation | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/tsconfig.json` | Configuration | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/vite.config.ts` | Unknown | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/.lovable/project.json` | Configuration | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/nitro.json` | Configuration | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/package-lock.json` | Configuration | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/package.json` | Dependency Manifest | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/robots.txt` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/ai-safety-insights-D5AGunJy.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/alerts-B4-5MFil.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/auth-guard-BVCbQWRM.js` | Unknown | Implementation | N/A | Yes | 3. Frontend<br>6. Auth/RBAC | [x] Verified |
| `frontend/.output/public/assets/calendar-B0u-W6Py.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/camera-CT8wshwl.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/chart-line-BE7WWpcG.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/chevron-down-DWn-6J5Y.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/chevron-left-DhjuHQvO.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/chevron-right-kbliRY1h.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/clipboard-list-BbOdK4fw.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/clock-Vr48vc_f.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/clsx-CjueKrWZ.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/documents-DXi094SA.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/event-history-CaHsJoBh.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/eye-CMW8G031.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/file-text-Bf2ebOmY.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/image-off-8AQ3uxbC.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/index-DAgW_SCC.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/info-B7plZptV.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/lightbulb-CDGhwHj5.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/link-DWghAheB.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/live-monitoring-0NEMlMSQ.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/loader-circle-BUVaC0ud.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/login-i6TtLLQD.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/mail-D9Ox9Y6Q.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/map-pin-C1U1ks9j.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/minimize-2-BCpOj-TO.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/patterns-CuwgTQpQ.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/person-standing-CKEs7BJD.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/react-B2OhQbJN.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/routes-COt3XWzm.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/search-cjgu2WJx.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/settings-Cfnz5GH6.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/settings-Fs1Hg-BX.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/shield-alert-BV9x1azb.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/shield-BIRs3Kxn.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/shield-check-e9UmYx3_.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/sparkles-BVoBBc6L.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/trending-up-DIwk0hje.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/triangle-alert-Cp7xMKBp.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/users-CBKYK0D2.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/utils-zYpESZ_s.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/video-B-GbPrpB.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/public/assets/x-DvY57pSJ.js` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.output/server/wrangler.json` | Configuration | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/.wrangler/deploy/config.json` | Configuration | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/public/robots.txt` | Unknown | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/src/router.tsx` | Unknown | Implementation | getRouter | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routeTree.gen.ts` | Unknown | Implementation | FileRoutesByFullPath, FileRoutesByTo, FileRoutesById, FileRouteTypes, RootRouteChildren... | Yes | 3. Frontend | [x] Verified |
| `frontend/src/server.ts` | Unknown | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/start.ts` | Unknown | Implementation | startInstance | Yes | 3. Frontend | [x] Verified |
| `frontend/src/assets/login-factory.png.asset.json` | Configuration | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/AppHeader.tsx` | Frontend Component | Implementation | AppHeader | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/auth-guard.tsx` | Frontend Component | Implementation | AuthGuard | Yes | 3. Frontend<br>6. Auth/RBAC | [x] Verified |
| `frontend/src/components/safevision/EventEvidenceModal.tsx` | Frontend Component | Implementation | EventEvidenceModal | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/safevision/InsightDetail.tsx` | Frontend Component | Implementation | DetailTab, RecommendationAction, InsightDetailViewModel, InsightDetail | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/safevision/InsightIcon.tsx` | Frontend Component | Implementation | InsightIconName, InsightIcon | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/safevision/InsightsList.tsx` | Frontend Component | Implementation | InsightListItem, InsightsList | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/safevision/RiskBadge.tsx` | Frontend Component | Implementation | RiskLevel, RiskDotLabel, RiskChip | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/safevision/VideoCanvasOverlay.tsx` | Frontend Component | Implementation | VideoCanvasOverlay | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/site/BiggerPicture.tsx` | Frontend Component | Implementation | BiggerPicture | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/site/Header.tsx` | Frontend Component | Implementation | Header | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/site/HeroModules.tsx` | Frontend Component | Implementation | HeroModules | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/site/HowItWorks.tsx` | Frontend Component | Implementation | HowItWorks | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/site/ImpactInAction.tsx` | Frontend Component | Implementation | ImpactInAction | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/site/Reveal.tsx` | Frontend Component | Implementation | Reveal, RevealGroup, RevealItem | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/accordion.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/alert-dialog.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/alert.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/aspect-ratio.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/avatar.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/badge.tsx` | Frontend Component | Implementation | BadgeProps | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/breadcrumb.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/button.tsx` | Frontend Component | Implementation | ButtonProps | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/calendar.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/card.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/carousel.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/chart.tsx` | Frontend Component | Implementation | ChartConfig | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/checkbox.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/collapsible.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/command.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/context-menu.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/dialog.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/drawer.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/dropdown-menu.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/form.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/hover-card.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/input-otp.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/input.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/label.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/menubar.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/navigation-menu.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/pagination.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/popover.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/progress.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/radio-group.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/resizable.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/scroll-area.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/select.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/separator.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/sheet.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/sidebar.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/skeleton.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/slider.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/sonner.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/switch.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/table.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/tabs.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/textarea.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/toggle-group.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/toggle.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/components/ui/tooltip.tsx` | Frontend Component | Implementation | None | Yes | 3. Frontend | [x] Verified |
| `frontend/src/data/safety-events.ts` | Unknown | Implementation | EventStatus, SafetyEvent, eventTypes, eventLocations, riskLevels... | Yes | 3. Frontend | [x] Verified |
| `frontend/src/data/safety-insights.ts` | Unknown | Implementation | RiskLevel, HistoricalEvent, RecommendationAction, SafetyInsight, safetyInsights... | Yes | 3. Frontend | [x] Verified |
| `frontend/src/hooks/use-mobile.tsx` | Unknown | Implementation | useIsMobile | Yes | 3. Frontend | [x] Verified |
| `frontend/src/lib/api-client.ts` | Frontend Utility/Service | Implementation | ApiError, getAuthToken, setAuthToken, clearAuthToken, getWebSocketUrl | Yes | 3. Frontend | [x] Verified |
| `frontend/src/lib/api-types.ts` | Frontend Utility/Service | Implementation | LoginRequest, LoginResponse, UserResponse, AlertResponse, AlertStateResponse... | Yes | 3. Frontend | [x] Verified |
| `frontend/src/lib/auth-context.tsx` | Frontend Utility/Service | Implementation | AuthProvider, useAuth | Yes | 3. Frontend<br>6. Auth/RBAC | [x] Verified |
| `frontend/src/lib/error-capture.ts` | Frontend Utility/Service | Implementation | describeError, consumeLastCapturedError | Yes | 3. Frontend | [x] Verified |
| `frontend/src/lib/error-page.ts` | Frontend Utility/Service | Implementation | renderErrorPage | Yes | 3. Frontend | [x] Verified |
| `frontend/src/lib/lovable-error-reporting.ts` | Frontend Utility/Service | Implementation | reportLovableError | Yes | 3. Frontend | [x] Verified |
| `frontend/src/lib/safety-types.ts` | Frontend Utility/Service | Implementation | AlertSeverity, AlertStatus, SafetyEventType, Zone, Camera... | Yes | 3. Frontend | [x] Verified |
| `frontend/src/lib/utils.ts` | Frontend Utility/Service | Implementation | cn | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/ai-safety-insights.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/alerts.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/documents.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/event-history.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/index.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/live-monitoring.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/login.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/patterns.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/README.md` | Frontend Route | Implementation | N/A | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/settings.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `frontend/src/routes/__root.tsx` | Frontend Route | Implementation | Route | Yes | 3. Frontend | [x] Verified |
| `Old Forntend files/ai-safety-insights.tsx` | Unknown | Implementation | Route | Yes | General | [x] Verified |
| `Old Forntend files/InsightDetail.tsx` | Unknown | Implementation | DetailTab, InsightDetail | Yes | General | [x] Verified |
| `Old Forntend files/InsightIcon.tsx` | Unknown | Implementation | InsightIcon | Yes | General | [x] Verified |
| `Old Forntend files/InsightsList.tsx` | Unknown | Implementation | InsightsList | Yes | General | [x] Verified |
| `Old Forntend files/RiskBadge.tsx` | Unknown | Implementation | RiskDotLabel, RiskChip | Yes | General | [x] Verified |
| `scratch/generate_inventory.py` | Unknown | Implementation | None | Yes | General | [x] Verified |
