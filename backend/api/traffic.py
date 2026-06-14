from typing import Optional, List, Dict, Any
from backend.core.schemas import CameraSourceModeRequest, JunctionSelectRequest, JunctionModeRequest
from fastapi import APIRouter, Request, HTTPException, Query, Header, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
import backend.dependencies as deps
from backend.services.video_service import _get_cam_renderer, _demo_placeholder_jpeg, _read_demo_video_frame
from backend.services.traffic_service import live_runtime
from backend.core.config import *
from backend.core.utils import *
from backend.core.utils import _import_errors
router = APIRouter(tags=['Traffic'])

@router.get("/api/status")
async def status():
    modules_status = {}
    module_map = {
        "emergency": deps.emergency_engine,
        "carbon": deps.carbon_engine,
        "pedestrian_safety": deps.pedestrian_ai,
        "cybersecurity": deps.security_detector,
        "road_maintenance": deps.maintenance_ai,
        "nl_command": deps.nl_parser,
        "deps.counterfactual": deps.counterfactual,
        "voice_broadcast": deps.voice,
    }
    for name, instance in module_map.items():
        modules_status[name] = "active" if instance else f"failed: {_import_errors.get(f'modules.{name}', 'unknown')}"

    runtime_status = live_runtime.status()
    return {
        "status": "running",
        "version": "2.0.0",
        "demo_mode": getattr(deps, "demo_gen", None) is not None,
        "live_mode": getattr(deps, "live_runtime", None) is not None,
        "decision_engine": dict(_rl_engine_info) if "_rl_engine_info" in globals() else {},
        "ws_clients": deps.ws_manager.count,
        "junctions": len(deps._junction_states),
        "modules": modules_status,
        "runtime": runtime_status,
        "runtime_health": runtime_status,
        "camera_source": getattr(deps, "_camera_source_payload", lambda: {})(),
    }



@router.get("/api/schema/system_state")
async def system_state_schema():
    return {
        "name": "system_state",
        "version": "1.0.0",
        "schema": SYSTEM_STATE_SCHEMA,
    }



@router.get("/api/audit/logs")
async def audit_logs(limit: int = Query(200, ge=1, le=5000)):
    items = list(deps._audit_log)
    return {
        "count": min(limit, len(items)),
        "logs": items[:limit],
    }



@router.get("/api/replay")
async def replay(seconds: int = Query(30, ge=1, le=300)):
    now_ms = int(time.time() * 1000)
    cutoff = now_ms - (seconds * 1000)
    frames = [f for f in list(deps._state_replay_buffer) if int(f.get("tick_timestamp", 0)) >= cutoff]
    return {
        "seconds": seconds,
        "frames": frames,
        "count": len(frames),
    }



@router.get("/api/live/video")
async def live_video_stream():
    """MJPEG stream for annotated live detection frames."""

    async def _frame_gen():
        boundary = b"--frame\r\n"
        while True:
            if live_runtime.enabled:
                await live_runtime.tick()

            frame_bytes = live_runtime.latest_frame_jpeg
            if frame_bytes:
                yield (
                    boundary
                    + b"Content-Type: image/jpeg\r\n\r\n"
                    + frame_bytes
                    + b"\r\n"
                )
            await asyncio.sleep(0.12)

    return StreamingResponse(
        _frame_gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )



@router.get("/api/map/state")
async def map_state():
    """Real-time map telemetry derived from CV detections."""
    if live_runtime.enabled:
        await live_runtime.tick()
    return {
        "timestamp": time.time(),
        "map": live_runtime.map_payload(),
    }



@router.get("/api/live/source")
async def live_source_status():
    return _camera_source_payload()



@router.post("/api/live/source/mode")
async def live_source_mode(req: CameraSourceModeRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    mode = str(req.mode or "").strip().lower()
    if mode not in {"live", "upload"}:
        raise HTTPException(status_code=400, detail="mode must be 'live' or 'upload'")
    if mode == "upload" and not _uploaded_video_exists():
        raise HTTPException(status_code=400, detail="No uploaded video available. Upload a video first.")

    _camera_input_mode = mode
    _camera_source_updated_at = int(time.time() * 1000)
    _invalidate_cam_renderers()
    _apply_live_runtime_camera_source(blocking_reopen=False)
    return _camera_source_payload()



@router.post("/api/live/upload-video")
async def live_upload_video(video: UploadFile = File(...), x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)

    filename = os.path.basename(video.filename or "")
    ext = Path(filename).suffix.lower()
    allowed_ext = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Unsupported video type: {ext or 'unknown'}")

    out_name = f"uploaded_{int(time.time())}{ext}"
    out_path = _upload_video_dir / out_name
    try:
        with out_path.open("wb") as f:
            shutil.copyfileobj(video.file, f)

        if _uploaded_video_path and os.path.isfile(_uploaded_video_path):
            try:
                os.remove(_uploaded_video_path)
            except OSError:
                pass

        _uploaded_video_path = str(out_path)
        _camera_input_mode = "upload"
        _camera_source_updated_at = int(time.time() * 1000)
        _invalidate_cam_renderers()
        _apply_live_runtime_camera_source(blocking_reopen=False)

        return {
            "ok": True,
            "message": "Video uploaded and camera source switched to upload mode",
            **_camera_source_payload(),
        }
    except Exception as exc:
        logger.exception("[Upload] Video upload failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "Upload failed, service remains running in safe mode.",
                "error": str(exc),
            },
        )
    finally:
        await video.close()



@router.post("/api/live/upload-video/clear")
async def live_clear_uploaded_video(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)

    if _uploaded_video_path and os.path.isfile(_uploaded_video_path):
        try:
            os.remove(_uploaded_video_path)
        except OSError:
            pass

    _uploaded_video_path = None
    _camera_input_mode = "live"
    _camera_source_updated_at = int(time.time() * 1000)
    _invalidate_cam_renderers()
    _apply_live_runtime_camera_source(blocking_reopen=False)
    return {
        "ok": True,
        "message": "Uploaded video cleared. Switched to live camera mode.",
        **_camera_source_payload(),
    }



@router.get("/api/live/camera/{junction_id}/{direction}")
async def junction_camera_stream(junction_id: str, direction: str):
    """
    MJPEG stream for a specific junction approach camera.
    direction: north | south | east | west
    """
    ALLOWED_DIRS = {"north", "south", "east", "west"}
    dir_clean = direction.lower().strip()
    if dir_clean not in ALLOWED_DIRS:
        raise HTTPException(400, f"direction must be one of {ALLOWED_DIRS}")

    renderer = None
    if not live_runtime.enabled:
        renderer = _get_cam_renderer(junction_id, dir_clean)
        if renderer is None:
            logger.warning("[CamRenderer] Falling back to placeholder stream for %s (%s)", junction_id, dir_clean)

    async def _cam_gen():
        boundary = b"--frame\r\n"
        while True:
            jpeg = None
            try:
                # Prefer the single shared LiveRuntime capture pipeline when active.
                if live_runtime.enabled:
                    if live_runtime.latest_frame_jpeg is None:
                        await live_runtime.tick()
                    jpeg = live_runtime.latest_frame_jpeg
                elif renderer is not None:
                    # Sync renderer calls — run in thread pool to avoid blocking async loop
                    import asyncio
                    loop = asyncio.get_event_loop()
                    frame_data = await loop.run_in_executor(None, renderer.render)
                    frame, _ = frame_data
                    # Sync signal phase from junction state cache
                    phase = deps._junction_states.get(junction_id, {}).get("phase", "NS_GREEN")
                    renderer.set_phase(phase)
                    jpeg = _encode_jpeg_frame(frame)
            except Exception as exc:
                logger.debug("[CamRenderer] render error: %s", exc)

            if jpeg is None:
                jpeg = _demo_placeholder_jpeg("Camera feed unavailable", junction_id)

            if jpeg:
                yield (
                    boundary
                    + b"Content-Type: image/jpeg\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
            await asyncio.sleep(0.10)

    return StreamingResponse(
        _cam_gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )



@router.get("/api/live/camera/{junction_id}/{direction}/snapshot")
async def junction_camera_snapshot(junction_id: str, direction: str):
    """Return a single JPEG frame for the given camera."""
    dir_clean = direction.lower().strip()
    jpeg = None
    source_kind = "live"
    if live_runtime.enabled:
        if live_runtime.latest_frame_jpeg is None:
            await live_runtime.tick()
        jpeg = live_runtime.latest_frame_jpeg
    else:
        renderer = _get_cam_renderer(junction_id, dir_clean)
        if renderer is not None:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                frame, detections = await loop.run_in_executor(None, renderer.render)
                phase = deps._junction_states.get(junction_id, {}).get("phase", "NS_GREEN")
                renderer.set_phase(phase)
                jpeg = _encode_jpeg_frame(frame)
            except Exception as exc:
                logger.warning("[CamRenderer] snapshot render failed for %s (%s): %s", junction_id, dir_clean, exc)

    if not jpeg:
        source_kind = "placeholder"
        jpeg = _demo_placeholder_jpeg("Snapshot fallback", junction_id)
    if not jpeg:
        raise HTTPException(500, "JPEG encode failed")
    from fastapi.responses import Response
    return Response(content=jpeg, media_type="image/jpeg", headers={"X-Camera-Source": source_kind})



@router.get("/api/snapshot")
async def snapshot():
    if live_runtime.enabled:
        snap = await live_runtime.tick()
        if deps.counterfactual:
            queues = {
                "N": int(snap["queues"].get("north", 0)),
                "S": int(snap["queues"].get("south", 0)),
                "E": int(snap["queues"].get("east", 0)),
                "W": int(snap["queues"].get("west", 0)),
            }
            deps.counterfactual.record_comparison(
                ai_avg_wait=snap["avg_waiting_time"],
                ai_total_queue=int(snap["total_queue"]),
                ai_throughput=int(snap["throughput"]),
                queue_lengths=queues,
            )
        if deps.carbon_engine:
            idle_ai = snap["avg_waiting_time"] / 60.0
            idle_baseline = idle_ai * 1.35
            deps.carbon_engine.record_snapshot(idle_ai, idle_baseline, max(1, int(snap["total_queue"])))
        return snap

    if deps.demo_gen:
        snap = deps.demo_gen.get_snapshot()
        # Feed deps.counterfactual engine
        if deps.counterfactual:
            queues = {
                "N": int(snap["queues"].get("north", 0)),
                "S": int(snap["queues"].get("south", 0)),
                "E": int(snap["queues"].get("east", 0)),
                "W": int(snap["queues"].get("west", 0)),
            }
            deps.counterfactual.record_comparison(
                ai_avg_wait=snap["avg_waiting_time"],
                ai_total_queue=int(snap["total_queue"]),
                ai_throughput=int(snap["throughput"]),
                queue_lengths=queues,
            )
        # Feed carbon engine
        if deps.carbon_engine:
            idle_ai = snap["avg_waiting_time"] / 60.0
            idle_baseline = idle_ai * 1.4
            deps.carbon_engine.record_snapshot(idle_ai, idle_baseline, 100)
        return snap
    return {"error": "No data source available. Connect a live webcam or upload a video."}



@router.get("/api/history")
async def history(n: int = Query(100, ge=1, le=1000)):
    if live_runtime.enabled and live_runtime.latest_traffic:
        return [live_runtime.latest_traffic for _ in range(min(n, 10))]
    if deps.demo_gen:
        gen = DemoDataGenerator(mode="rl")
        return gen.get_history(n)
    return []



@router.get("/api/intersections")
async def intersections():
    _update_junction_telemetry_from_runtime()
    return list(deps._junction_states.values())



@router.get("/api/junction/{junction_id}/state")
async def junction_state(junction_id: str):
    _update_junction_telemetry_from_runtime()
    if junction_id not in deps._junction_states:
        return JSONResponse({"error": f"Unknown junction {junction_id}"}, status_code=404)
    return {
        "junction_id": junction_id,
        "selected": junction_id == deps._selected_junction_id,
        "state": _junction_state_payload(junction_id),
    }



@router.post("/api/junction/select")
async def junction_select(req: JunctionSelectRequest):
    jid = req.junction_id
    if jid not in deps._junction_states:
        return JSONResponse({"error": f"Unknown junction {jid}"}, status_code=404)
    deps._selected_junction_id = jid
    live_runtime.intersection_id = jid
    _log_event("control", "junction_selected", junction_id=jid)
    _append_audit_event("CONTROL", jid, "junction_select", {"input": _model_to_dict(req), "result": "selected"})
    return {"status": "ok", "selected": jid, "junction": deps._junction_states[jid], "state": _junction_state_payload(jid)}



@router.post("/api/mode/set")
async def mode_set(req: JunctionModeRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    jid = req.junction_id
    mode = req.mode.strip().lower()
    if jid not in deps._junction_states:
        return JSONResponse({"error": f"Unknown junction {jid}"}, status_code=404)
    if mode not in ("ai", "manual", "emergency"):
        return JSONResponse({"error": "mode must be ai/manual/emergency"}, status_code=400)

    st = deps._junction_states[jid]
    st["mode"] = mode

    if mode == "manual":
        phase = _phase_from_lane(req.lane)
        st["manual_lane"] = req.lane
        st["is_overridden"] = True
        _apply_phase_to_junction(jid, phase, source="manual", duration_s=req.duration)
    elif mode == "emergency":
        st["is_corridor"] = True
        _apply_phase_to_junction(jid, "NS_GREEN", source="emergency", duration_s=req.duration)
    else:
        st["manual_lane"] = None
        st["is_overridden"] = False
        st["is_corridor"] = False

    _log_event("control", "mode_set", junction_id=jid, mode=mode, lane=req.lane)
    _append_audit_event("CONTROL", jid, "mode_set", {"input": _model_to_dict(req), "result_mode": st.get("mode")})
    _push_incident("mode_change", jid, "active", f"Mode set to {mode}")
    _push_ai_decision(jid, f"mode_{mode}", st.get("ai_confidence", 0.9), st.get("ai_reason", "mode updated"))
    return {"status": "ok", "junction": st}



