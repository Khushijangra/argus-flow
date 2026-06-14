from typing import Optional, Dict, Any, List
import logging
import json
from datetime import datetime
logger = logging.getLogger(__name__)

def _log_event(module: str, event_type: str, **fields) -> None:
    payload = {
        "timestamp": round(time.time(), 3),
        "module": module,
        "event": event_type,
    }
    payload.update(fields)
    logger.info(json.dumps(payload, default=str))



def _append_audit_event(event_type: str, junction: str, action: str, details: Optional[Dict[str, Any]] = None) -> None:
    ctx = _current_frame_context()
    entry = {
        "type": event_type,
        "junction": junction,
        "action": action,
        "timestamp": ctx["tick_timestamp"],
        "frame_id": ctx["frame_id"],
        "details": details or {},
    }
    _audit_log.append(entry)



def _consistency_warnings(system_state: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    frame_id = system_state.get("frame_id")
    junctions = system_state.get("junctions", {})
    selected = system_state.get("selected_junction")
    emergency = system_state.get("emergency", {})
    decisions = system_state.get("ai_decisions", [])

    if decisions:
        top = decisions[0]
        if top.get("frame_id") not in (None, frame_id):
            warnings.append("ai_decision_frame_mismatch")
        jid = top.get("junction_id")
        if jid and jid in junctions and top.get("frame_id") == frame_id:
            sig = (junctions.get(jid, {}) or {}).get("signal", "")
            if isinstance(top.get("action"), str) and "EW_GREEN" in top["action"] and sig not in ("EW_GREEN", "YELLOW"):
                warnings.append("ai_decision_signal_mismatch")

    if emergency.get("active"):
        corridor = emergency.get("corridor", [])
        if corridor:
            if not any((junctions.get(j, {}) or {}).get("mode") == "emergency" for j in corridor):
                warnings.append("emergency_corridor_mode_mismatch")

    incidents = system_state.get("incidents", [])
    if incidents:
        latest = incidents[0]
        if latest.get("frame_id") not in (None, frame_id):
            warnings.append("incident_frame_mismatch")

    health = system_state.get("health", {})
    if health.get("pipeline_guard", {}).get("status") == "failure" and selected and selected in junctions:
        vc = int((junctions.get(selected, {}) or {}).get("vehicle_count", 0))
        if vc > 0:
            warnings.append("pipeline_guard_inconsistent")

    return warnings



