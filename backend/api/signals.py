from backend.core.schemas import SignalOverrideRequest, NLCommandRequest
from typing import Optional, List, Dict, Any
from fastapi import Header, Query, APIRouter, Request, HTTPException
import backend.dependencies as deps
from backend.core.config import *
from backend.core.utils import *
router = APIRouter(tags=['Signals'])

# ---------------------------------------------------------------
# REST Endpoints — Signal Override
# ---------------------------------------------------------------
@router.post("/api/signal/override")
async def signal_override(req: SignalOverrideRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    jid = req.junction_id
    if jid not in deps._junction_states:
        return JSONResponse({"error": f"Unknown junction {jid}"}, status_code=404)

    # Security check
    if deps.security_detector:
        result = deps.security_detector.validate_command(jid, hash(req.phase) % 8, source=req.source)
        if not result.get("allowed"):
            return JSONResponse({"error": "Security blocked", "details": result}, status_code=403)

    deps._junction_states[jid]["phase"] = req.phase
    deps._junction_states[jid]["signal_state"] = req.phase
    deps._junction_states[jid]["mode"] = "manual"
    deps._junction_states[jid]["is_overridden"] = True
    deps._signal_overrides[jid] = {"phase": req.phase, "expires": time.time() + req.duration}
    _apply_phase_to_junction(jid, req.phase, source=req.source, duration_s=req.duration)
    _append_audit_event(
        "CONTROL",
        jid,
        "signal_override",
        {"input": _model_to_dict(req), "result_phase": deps._junction_states[jid].get("phase")},
    )
    _push_incident("signal_override", jid, "active", f"Signal forced to {req.phase} for {req.duration}s")
    _push_ai_decision(jid, f"override_{req.phase}", 0.98, f"Manual override from {req.source}")

    return {"status": "ok", "junction": jid, "phase": req.phase, "duration": req.duration}



# ---------------------------------------------------------------
# REST Endpoints — NL Command
# ---------------------------------------------------------------
@router.post("/api/nl/command")
async def nl_command(req: NLCommandRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    if not deps.nl_parser:
        return JSONResponse({"error": "NL command module not available"}, status_code=503)
    parsed = deps.nl_parser.parse(req.text)
    response = {
        "intent": parsed.intent,
        "confidence": parsed.confidence,
        "junctions": parsed.junctions,
        "duration_minutes": parsed.duration_minutes,
        "direction": parsed.direction,
        "vehicle_type": parsed.vehicle_type,
        "phase": parsed.phase,
        "parameters": parsed.parameters,
        "raw_text": parsed.raw_text,
    }

    # Auto-execute high-confidence commands
    if parsed.confidence >= 0.8:
        if parsed.intent == "emergency" and deps.emergency_engine:
            origin = parsed.junctions[0] if parsed.junctions else "J0_0"
            destination = parsed.junctions[1] if len(parsed.junctions) > 1 else "J3_3"
            vtype = parsed.vehicle_type or "ambulance"
            event = deps.emergency_engine.activate_corridor("nl_" + str(int(time.time())), vtype, origin, destination)
            if event:
                response["action_taken"] = {"emergency_activated": True, "path": event.path}
                _push_incident("nl_emergency", " -> ".join(event.path), "active", f"NL command: {req.text}")
                _push_ai_decision(event.path[0] if event.path else "J1_1", "nl_emergency", parsed.confidence, parsed.intent)
                _append_audit_event(
                    "CONTROL",
                    event.path[0] if event.path else "J1_1",
                    "nl_command_emergency",
                    {
                        "input": _model_to_dict(req),
                        "intent": parsed.intent,
                        "confidence": parsed.confidence,
                        "result": response.get("action_taken", {}),
                    },
                )

        elif parsed.intent == "override_signal":
            jid = parsed.junctions[0] if parsed.junctions else "J1_1"
            phase = "NS_GREEN" if parsed.direction == "NS" else "EW_GREEN"
            if jid in deps._junction_states:
                deps._junction_states[jid]["phase"] = phase
                deps._junction_states[jid]["is_overridden"] = True
                response["action_taken"] = {"signal_overridden": True, "junction": jid, "phase": phase}
                _push_incident("nl_signal_override", jid, "active", f"NL command set phase {phase}")
                _push_ai_decision(jid, f"nl_{phase}", parsed.confidence, parsed.intent)
                _append_audit_event(
                    "CONTROL",
                    jid,
                    "nl_command_override",
                    {
                        "input": _model_to_dict(req),
                        "intent": parsed.intent,
                        "confidence": parsed.confidence,
                        "result": response.get("action_taken", {}),
                    },
                )

    _append_audit_event(
        "CONTROL",
        parsed.junctions[0] if parsed.junctions else "system",
        "nl_command",
        {
            "input": _model_to_dict(req),
            "intent": parsed.intent,
            "confidence": parsed.confidence,
            "result": response.get("action_taken", {}),
        },
    )
    return response



