"""
SafeVision AI — Video Ingestion & WebSocket Streaming API (Phase 11)

Endpoints:
- POST /api/cv/video/upload: Uploads video file, validates, creates session
- WebSocket /api/cv/video/ws/{session_id}: Frame-by-frame stream with immediate auth
- DELETE /api/cv/video/session/{session_id}: Cleans up active session and temporary files
"""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from pathlib import Path

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.middleware.auth import get_current_user
from app.models.camera import Camera
from app.models.user import User, UserStatus
from app.models.zone import Zone
from app.schemas.video_schema import (
    VideoUploadResponse,
    WSAuthOkMessage,
    WSCompletedMessage,
    WSErrorMessage,
)
from app.services.auth_service import decode_access_token
from app.services.video_service import (
    ALLOWED_EXTENSIONS,
    VideoService,
    VideoSession,
)

log = structlog.get_logger()

router = APIRouter(prefix="/cv/video", tags=["Video Stream & Live Monitoring"])


# ==============================================================================
# POST /api/cv/video/upload
# ==============================================================================

@router.post(
    "/upload",
    response_model=VideoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Video for Live Monitoring",
    description="Upload a recorded MP4/video file for frame-by-frame CV safety monitoring.",
)
async def upload_video_for_monitoring(
    file: UploadFile = File(..., description="Video file (.mp4, .avi, .mov, etc.)"),
    camera_id: str = Form(..., description="Camera ID to associate with this video stream"),
    zone_id: str | None = Form(None, description="Optional Zone ID for ROI evaluation"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload and register a video file for CV pipeline monitoring.
    Validates file format, size limits, and camera/zone tenant ownership.
    """
    settings = get_settings()

    # 1. Validate file extension
    filename = file.filename or "unknown.mp4"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video format: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Verify camera ownership
    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id, Camera.org_id == current_user.org_id)
        .first()
    )
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} not found in your organization",
        )

    # 3. Verify zone ownership if specified
    zone = None
    if zone_id:
        zone = (
            db.query(Zone)
            .filter(Zone.id == zone_id, Zone.org_id == current_user.org_id)
            .first()
        )
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Zone {zone_id} not found in your organization",
            )
    elif camera.zone_id:
        zone = db.query(Zone).filter(Zone.id == camera.zone_id).first()

    # 4. Save to temporary upload directory with unique filename
    upload_dir = VideoService.get_upload_dir()
    temp_filename = f"{uuid.uuid4()}{ext}"
    temp_file_path = upload_dir / temp_filename

    total_bytes = 0
    try:
        with open(temp_file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_bytes += len(chunk)
                if total_bytes > settings.max_video_upload_bytes:
                    buffer.close()
                    if temp_file_path.exists():
                        os.remove(temp_file_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Video exceeds maximum allowed size of {settings.max_video_upload_bytes / (1024*1024):.0f} MB",
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if temp_file_path.exists():
            os.remove(temp_file_path)
        log.error("video_upload_save_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded video file",
        )

    # 5. Initialize VideoSession using OpenCV validation
    try:
        session = VideoService.create_session(
            temp_file_path=str(temp_file_path),
            filename=filename,
            camera=camera,
            zone=zone,
            user_id=current_user.id,
            org_id=current_user.org_id,
        )
    except ValueError as e:
        if temp_file_path.exists():
            os.remove(temp_file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return VideoUploadResponse(
        session_id=session.session_id,
        filename=session.filename,
        camera_id=session.camera_id,
        zone_id=session.zone_id,
        total_frames=session.total_frames,
        source_fps=session.source_fps,
        duration_seconds=session.duration_seconds,
        width=session.width,
        height=session.height,
    )


# ==============================================================================
# WebSocket /api/cv/video/ws/{session_id}
# ==============================================================================

@router.websocket("/ws/{session_id}")
async def video_monitoring_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint streaming frame-by-frame CV inference.
    Enforces Immediate Authenticated First Message Protocol:
      1. Transport handshake connects unauthenticated.
      2. Client must send {"type": "auth", "token": "<JWT>"} within 3.0s.
      3. Server verifies token and tenant isolation (user.org_id == session.org_id).
      4. Server responds with {"type": "auth_ok", ...}
      5. Frame streaming begins on {"action": "start"}.
    """
    await websocket.accept()

    session = VideoService.get_session(session_id)
    if not session:
        await websocket.send_json(
            WSErrorMessage(type="error", message=f"Session {session_id} not found or expired").model_dump()
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # --- Step 1: Enforce 3-Second Auth Handshake ---
    authenticated_user: User | None = None
    db = SessionLocal()

    try:
        raw_msg = await asyncio.wait_for(websocket.receive_json(), timeout=3.0)
        msg_type = raw_msg.get("type")
        token = raw_msg.get("token")

        if msg_type != "auth" or not token:
            await websocket.send_json(
                WSErrorMessage(type="auth_error", message="Expected {'type': 'auth', 'token': '...'}").model_dump()
            )
            await websocket.close(code=4401)
            return

        payload = decode_access_token(token)
        if not payload:
            await websocket.send_json(
                WSErrorMessage(type="auth_error", message="Invalid or expired JWT token").model_dump()
            )
            await websocket.close(code=4401)
            return

        user_id = payload.get("sub")
        authenticated_user = (
            db.query(User)
            .filter(User.id == user_id, User.status == UserStatus.ACTIVE)
            .first()
        )

        if not authenticated_user:
            await websocket.send_json(
                WSErrorMessage(type="auth_error", message="User not found or inactive").model_dump()
            )
            await websocket.close(code=4401)
            return

        # Enforce strict tenant isolation
        if authenticated_user.org_id != session.org_id:
            await websocket.send_json(
                WSErrorMessage(type="auth_error", message="Tenant isolation violation: organization mismatch").model_dump()
            )
            await websocket.close(code=4401)
            return

        # Authentication successful
        await websocket.send_json(
            WSAuthOkMessage(
                type="auth_ok",
                user_id=authenticated_user.id,
                user_name=authenticated_user.name,
                org_id=authenticated_user.org_id,
            ).model_dump()
        )
        log.info("ws_client_authenticated", session_id=session_id, user_id=authenticated_user.id)

    except asyncio.TimeoutError:
        log.warning("ws_auth_timeout", session_id=session_id)
        try:
            await websocket.send_json(
                WSErrorMessage(type="auth_error", message="Authentication timeout (3s limit exceeded)").model_dump()
            )
            await websocket.close(code=4401)
        except Exception:
            pass
        return
    except Exception as e:
        log.error("ws_auth_exception", session_id=session_id, error=str(e))
        try:
            await websocket.close(code=4401)
        except Exception:
            pass
        return

    # --- Step 2: Streaming Control Loop ---
    paused = False
    stopped = False

    async def listen_for_client_controls():
        nonlocal paused, stopped
        try:
            while session.is_active and not stopped:
                msg = await websocket.receive_json()
                action = msg.get("action")
                if action == "pause":
                    paused = True
                    log.info("ws_stream_paused", session_id=session_id)
                elif action == "resume":
                    paused = False
                    log.info("ws_stream_resumed", session_id=session_id)
                elif action == "stop":
                    stopped = True
                    session.is_active = False
                    log.info("ws_stream_stopped", session_id=session_id)
                    break
        except WebSocketDisconnect:
            stopped = True
            session.is_active = False
        except Exception:
            stopped = True
            session.is_active = False

    control_task = asyncio.create_task(listen_for_client_controls())

    # --- Step 3: Frame Processing and Streaming ---
    frames_processed = 0
    total_events = 0

    try:
        # Run synchronous frame generation in worker thread to prevent event loop blocking
        for frame_payload in VideoService.process_video_generator(session=session, db=db):
            if stopped or not session.is_active:
                break

            # Handle pause state
            while paused and not stopped:
                await asyncio.sleep(0.1)

            # Transmit frame packet
            await websocket.send_json(frame_payload.model_dump())
            frames_processed += 1
            total_events = frame_payload.stats.total_events_generated

            # Yield briefly to event loop to allow incoming control messages to be processed
            await asyncio.sleep(0.001)

        # Finished all frames
        if not stopped:
            await websocket.send_json(
                WSCompletedMessage(
                    type="completed",
                    total_frames_processed=frames_processed,
                    total_events_generated=total_events,
                ).model_dump()
            )
            log.info(
                "ws_stream_completed",
                session_id=session_id,
                frames=frames_processed,
                events=total_events,
            )

    except WebSocketDisconnect:
        log.info("ws_client_disconnected", session_id=session_id)
    except Exception as e:
        import traceback
        log.error("ws_stream_error", session_id=session_id, error=str(e), traceback=traceback.format_exc())
        try:
            await websocket.send_json(
                WSErrorMessage(type="error", message=f"Streaming error: {str(e)}").model_dump()
            )
        except Exception:
            pass
    finally:
        control_task.cancel()
        db.close()
        # Clean up temporary session video file
        VideoService.delete_session(session_id)
        try:
            await websocket.close()
        except Exception:
            pass


# ==============================================================================
# DELETE /api/cv/video/session/{session_id}
# ==============================================================================

@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Video Session",
    description="Abort video monitoring session and clean up temporary uploaded video file.",
)
def delete_video_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    session = VideoService.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if session.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    VideoService.delete_session(session_id)
    return None
