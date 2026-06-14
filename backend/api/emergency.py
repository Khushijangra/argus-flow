from backend.core.schemas import EmergencyActivateRequest
from typing import Optional, List, Dict, Any
from fastapi import Header, Query, APIRouter, Request, HTTPException
import backend.dependencies as deps
from backend.core.config import *
from backend.core.utils import *
router = APIRouter(tags=['Emergency'])

# ---------------------------------------------------------------
# REST Endpoints — Emergency
# ---------------------------------------------------------------
@router.post("/api/emergency/activate")
async def emergency_activate(req: EmergencyActivateRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    if not deps.emergency_engine:
        return JSONResponse({"error": "Emergency module not available"}, status_code=503)

    event = deps.emergency_engine.activate_corridor(
        vehicle_id=req.vehicle_id,
        vehicle_type=req.vehicle_type,
        origin=req.origin,
        destination=req.destination,
    )
    if not event:
        return JSONResponse({"error": "Could not compute corridor path"}, status_code=400)

    # Mark junctions as corridor
    for jid in event.path:
        if jid in deps._junction_states:
            deps._junction_states[jid]["is_corridor"] = True
            deps._junction_states[jid]["mode"] = "emergency"
            _apply_phase_to_junction(jid, "NS_GREEN", source="emergency", duration_s=45)
            _push_ai_decision(jid, "corridor_priority", 0.99, "Emergency vehicle corridor override")

    # Voice announcement
    if deps.voice:
        deps.voice.announce_emergency_corridor(req.vehicle_type, req.origin, req.destination)

    eta_seconds = getattr(event, "eta_seconds", None)
    if eta_seconds is None:
        eta_seconds = getattr(event, "estimated_time_s", 0)

    _append_audit_event(
        "EMERGENCY",
        req.origin,
        "activate_corridor",
        {"input": _model_to_dict(req), "path": event.path, "eta_seconds": eta_seconds},
    )
    _push_incident("emergency_corridor", " -> ".join(event.path), "active", f"{req.vehicle_type} corridor activated")

    return {
        "event_id": event.event_id,
        "vehicle_id": event.vehicle_id,
        "path": event.path,
        "eta_seconds": eta_seconds,
        "signal_overrides": deps.emergency_engine.get_corridor_signal_overrides(),
    }



@router.get("/api/emergency/active")
async def emergency_active():
    if not deps.emergency_engine:
        return []
    return [
        {
            "event_id": e.event_id,
            "vehicle_id": e.vehicle_id,
            "vehicle_type": e.vehicle_type,
            "path": e.path,
            "current_junction": (e.path[0] if e.path else ""),
            "eta_seconds": round(max(0.0, e.estimated_time_s - (time.time() - e.activated_at)), 1),
        }
        for e in deps.emergency_engine._active_events.values()
    ]



