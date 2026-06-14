"""
NEXUS-ATMS — FastAPI Backend
===============================
Integrates all NEXUS modules into a unified REST + WebSocket API.

Endpoints:
  /api/status              — System status
  /api/snapshot            — Single traffic snapshot
  /api/history             — Historic traffic data
  /api/intersections       — All junction states
  /api/signal/override     — Manual signal override (POST)
  /api/emergency/activate  — Activate emergency corridor (POST)
  /api/emergency/active    — List active emergency events
  /api/carbon/today        — Carbon savings for today
  /api/carbon/certificate  — Download PDF certificate
  /api/pedestrian/analyze  — Pedestrian safety status
  /api/security/validate   — Validate a signal command (POST)
  /api/security/simulate   — Simulate an attack (POST)
  /api/security/events     — Recent security events
  /api/maintenance/orders  — Road maintenance work orders
  /api/nl/command          — Natural-language command (POST)
  /api/counterfactual      — AI vs baseline comparison
  /api/voice/announce      — Trigger voice broadcast (POST)
  /api/voice/log           — Broadcast log
  /api/metrics/overview    — Aggregated metrics overview
  /ws/live                 — WebSocket: live data stream (~1 Hz)
"""

import asyncio
import collections
import json
import logging
import os
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

# Add project root to path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from backend.demo_data import DemoDataGenerator

# Detect Railway runtime early and force safe demo defaults in cloud.
_IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))

# Determine boot mode early so optional heavy modules can be skipped in demo startup.
# Explicit DEMO_MODE must always win, including on Railway.
_demo_mode_env = os.getenv("DEMO_MODE")
if _demo_mode_env is None:
    # Default to live-capable local mode; keep cloud deployments in safe demo mode.
    _BOOT_DEMO_MODE = _IS_RAILWAY
else:
    _BOOT_DEMO_MODE = _demo_mode_env.lower() == "true"

# Module imports — guarded so backend still starts if a module fails
_import_errors: Dict[str, str] = {}


def _safe_import(module_path: str, class_name: str):
    """Import a class, returning None on failure."""
    if _BOOT_DEMO_MODE and module_path.startswith(("ai.", "modules.", "control.", "iot.")):
        if module_path.startswith("modules."):
            _import_errors[module_path] = "skipped in demo mode"
        return None
    try:
        mod = __import__(module_path, fromlist=[class_name])
        return getattr(mod, class_name)
    except Exception as exc:
        _import_errors[module_path] = str(exc)
        return None


EmergencyCorridorEngine = _safe_import("modules.emergency.corridor", "EmergencyCorridorEngine")
CarbonCreditEngine = _safe_import("modules.carbon.engine", "CarbonCreditEngine")
PedestrianSafetyAI = _safe_import("modules.pedestrian_safety.safety", "PedestrianSafetyAI")
SignalAnomalyDetector = _safe_import("modules.cybersecurity.signal_security", "SignalAnomalyDetector")
RoadMaintenanceAI = _safe_import("modules.road_maintenance.maintenance", "RoadMaintenanceAI")
NLCommandParser = _safe_import("modules.nl_command.parser", "NLCommandParser")
CounterfactualEngine = _safe_import("modules.counterfactual.engine", "CounterfactualEngine")
VoiceBroadcast = _safe_import("modules.voice_broadcast.broadcast", "VoiceBroadcast")

# Real data pipeline imports (optional; backend still runs if unavailable)
VehicleDetector = _safe_import("ai.vision.detector", "VehicleDetector")
VehicleTracker = _safe_import("ai.vision.tracker", "VehicleTracker")
ZoneCounter = _safe_import("ai.vision.counter", "ZoneCounter")
SpeedEstimator = _safe_import("ai.vision.speed_estimator", "SpeedEstimator")
IncidentDetector = _safe_import("ai.vision.incident_detector", "IncidentDetector")
TrafficRenderer = _safe_import("ai.vision.traffic_renderer", "TrafficRenderer")
RoadCameraRenderer = _safe_import("ai.vision.road_camera_renderer", "RoadCameraRenderer")
RoadGeoMapper = _safe_import("ai.vision.geo_mapper", "RoadGeoMapper")

SensorSimulator = _safe_import("iot.sensor_simulator", "SensorSimulator")
SensorFusion = _safe_import("iot.data_fusion", "SensorFusion")
MQTTClient = _safe_import("iot.mqtt_client", "MQTTClient")

LSTMPredictor = _safe_import("ai.prediction.lstm_predictor", "LSTMPredictor")
MLAnomalyDetector = _safe_import("ai.anomaly.ml_anomaly_detector", "MLAnomalyDetector")

RLController = _safe_import("control.rl_controller", "RLController")
MultiAgentCoordinator = _safe_import("control.rl_controller", "MultiAgentCoordinator")

logger = logging.getLogger("nexus-backend")

ANOMALY_MODEL_DIR = os.getenv("ANOMALY_MODEL_DIR", "models/ml_anomaly")
AI_STATUS_DQN_MODEL_PATH = os.getenv("AI_STATUS_DQN_MODEL_PATH", "models/dqn_20260226_014406/best/best_model.zip")
AI_STATUS_LSTM_MODEL_PATH = os.getenv("AI_STATUS_LSTM_MODEL_PATH", "models/lstm_predictor.pt")
AI_EXPLAIN_MODEL_PATH = os.getenv("AI_EXPLAIN_MODEL_PATH", AI_STATUS_DQN_MODEL_PATH)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )


def _log_event(module: str, event_type: str, **fields) -> None:
    payload = {
        "timestamp": round(time.time(), 3),
        "module": module,
        "event": event_type,
    }
    payload.update(fields)
    logger.info(json.dumps(payload, default=str))


def _model_to_dict(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _optional_cv2():
    try:
        import cv2  # type: ignore
        return cv2
    except Exception:
        return None


def _optional_torch():
    try:
        import torch  # type: ignore
        return torch
    except Exception:
        return None

# ---------------------------------------------------------------
# App Initialisation
# ---------------------------------------------------------------
app = FastAPI(title="NEXUS-ATMS Dashboard", version="2.0.0")
HARDENED_MODE = os.getenv("HARDENED_MODE", "false").lower() == "true"
CONTROL_API_KEY = os.getenv("CONTROL_API_KEY", "").strip()
_default_allowed_origins = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]
_cors_origins_raw = os.getenv("ALLOWED_ORIGINS", "").strip()
_frontend_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
_allowed_origins = list(
    dict.fromkeys(
        _default_allowed_origins
        + [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
        + ([_frontend_origin] if _frontend_origin else [])
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _enforce_control_access(x_api_key: Optional[str]) -> None:
    """Require API key for sensitive control endpoints when hardened mode is enabled."""
    if not HARDENED_MODE:
        return
    if not CONTROL_API_KEY:
        raise HTTPException(status_code=503, detail="HARDENED_MODE enabled but CONTROL_API_KEY is not configured")
    if (x_api_key or "").strip() != CONTROL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

# Serve frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# Demo mode flag
DEMO_MODE = _BOOT_DEMO_MODE
LIVE_MODE = (os.getenv("LIVE_MODE", "false").lower() == "true") and not DEMO_MODE
demo_gen = DemoDataGenerator(mode="rl") if DEMO_MODE else None


def _ensure_demo_mode(reason: str) -> None:
    """Switch runtime to demo mode without interrupting server startup."""
    global DEMO_MODE, LIVE_MODE, demo_gen
    DEMO_MODE = True
    LIVE_MODE = False
    if demo_gen is None:
        demo_gen = DemoDataGenerator(mode="rl")
    logger.warning("[Startup] Camera unavailable -> fallback to DEMO MODE (%s)", reason)

# ---------------------------------------------------------------
# Module Singletons
# ---------------------------------------------------------------
emergency_engine = None
carbon_engine = None
pedestrian_ai = None
security_detector = None
maintenance_ai = None
nl_parser = None
counterfactual = None
voice = None


def _init_module_singletons() -> None:
    """Initialize optional module singletons lazily during startup."""
    global emergency_engine, carbon_engine, pedestrian_ai, security_detector
    global maintenance_ai, nl_parser, counterfactual, voice

    if DEMO_MODE:
        emergency_engine = None
        carbon_engine = None
        pedestrian_ai = None
        security_detector = None
        maintenance_ai = None
        nl_parser = None
        counterfactual = None
        voice = None
        return

    emergency_engine = EmergencyCorridorEngine() if EmergencyCorridorEngine else None
    carbon_engine = CarbonCreditEngine() if CarbonCreditEngine else None
    pedestrian_ai = PedestrianSafetyAI(device="cpu") if PedestrianSafetyAI else None
    security_detector = SignalAnomalyDetector() if SignalAnomalyDetector else None
    maintenance_ai = RoadMaintenanceAI() if RoadMaintenanceAI else None
    nl_parser = NLCommandParser() if NLCommandParser else None
    counterfactual = CounterfactualEngine() if CounterfactualEngine else None
    voice = VoiceBroadcast(language="en") if VoiceBroadcast else None

    if emergency_engine:
        emergency_engine.build_grid_graph(rows=4, cols=4)

# ---------------------------------------------------------------
# Pydantic Models for POST Bodies
# ---------------------------------------------------------------
class SignalOverrideRequest(BaseModel):
    junction_id: str
    phase: str  # "NS_GREEN", "EW_GREEN", "YELLOW", "ALL_RED"
    duration: int = 60
    source: str = "operator"


class EmergencyActivateRequest(BaseModel):
    vehicle_id: str
    vehicle_type: str = "ambulance"
    origin: str  # Junction ID
    destination: str  # Junction ID


class JunctionSelectRequest(BaseModel):
    junction_id: str


class JunctionModeRequest(BaseModel):
    junction_id: str
    mode: str  # ai | manual | emergency
    lane: Optional[str] = None  # north|south|east|west
    duration: int = 60


class SecurityValidateRequest(BaseModel):
    junction_id: str
    new_phase: int
    source: str = "ai"


class SecuritySimulateRequest(BaseModel):
    attack_type: str  # replay, dos, mitm, conflicting
    junction_id: str = "J1_1"


class NLCommandRequest(BaseModel):
    text: str


class VoiceAnnounceRequest(BaseModel):
    message: str
    language: str = "en"
    play: bool = False  # Don't play audio on server by default


class CameraSourceModeRequest(BaseModel):
    mode: str  # live | upload


# ---------------------------------------------------------------
# WebSocket Manager
# ---------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self._active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._active.add(ws)

    def disconnect(self, ws: WebSocket):
        self._active.discard(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self._active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._active.discard(ws)

    @property
    def count(self) -> int:
        return len(self._active)


ws_manager = ConnectionManager()

# ---------------------------------------------------------------
# Junction state cache (updated by background loop / SUMO)
# ---------------------------------------------------------------
_junction_states: Dict[str, Dict] = {}
_signal_overrides: Dict[str, Dict] = {}
_selected_junction_id = "J1_1"
_session_started_at = time.time()
_session_metrics: Dict[str, float] = {
    "samples": 0,
    "ai_wait_sum": 0.0,
    "baseline_wait_sum": 0.0,
    "ai_idle_sum": 0.0,
    "baseline_idle_sum": 0.0,
    "queue_sum": 0.0,
    "saved_vehicle_minutes": 0.0,
    "emissions_saved_kg": 0.0,
}
_ai_decision_feed: collections.deque = collections.deque(maxlen=24)
_completed_emergency_events: collections.deque = collections.deque(maxlen=30)
_active_emergency_ids: Set[str] = set()
_incident_log: collections.deque = collections.deque(maxlen=80)
_audit_log: collections.deque = collections.deque(maxlen=5000)
_state_replay_buffer: collections.deque = collections.deque(maxlen=1800)
_frame_seq = 0
_last_tick_ms = int(time.time() * 1000)
_last_ws_tx_ms = 0.0
_last_traffic_snapshot: Dict[str, Any] = {}

DECISION_ENGINE_MODE = os.getenv("DECISION_ENGINE", "auto").strip().lower()
_rl_coordinator = None
_rl_engine_info: Dict[str, Any] = {
    "enabled": False,
    "source": "heuristic",
    "status": "fallback",
    "message": "Heuristic controller active",
}

SYSTEM_STATE_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "NEXUS SystemState",
    "type": "object",
    "required": [
        "frame_id",
        "tick_timestamp",
        "junctions",
        "session_metrics",
        "ai_decisions",
        "emergency",
        "anomalies",
        "incidents",
        "esg",
        "maintenance",
        "cybersecurity",
        "health",
    ],
    "properties": {
        "frame_id": {"type": "integer", "minimum": 1},
        "tick_timestamp": {"type": "integer", "minimum": 1},
        "selected_junction": {"type": "string"},
        "junctions": {"type": "object"},
        "session_metrics": {"type": "object"},
        "ai_decisions": {"type": "array"},
        "emergency": {"type": "object"},
        "anomalies": {"type": "array"},
        "incidents": {"type": "array"},
        "esg": {"type": "object"},
        "maintenance": {"type": "object"},
        "cybersecurity": {"type": "object"},
        "health": {"type": "object"},
        "map": {"type": "object"},
        "traffic": {"type": "object"},
    },
}


def _next_frame_context() -> Dict[str, int]:
    global _frame_seq, _last_tick_ms
    _frame_seq += 1
    _last_tick_ms = int(time.time() * 1000)
    return {"frame_id": _frame_seq, "tick_timestamp": _last_tick_ms}


def _current_frame_context() -> Dict[str, int]:
    return {"frame_id": max(1, _frame_seq), "tick_timestamp": _last_tick_ms}


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


def _store_replay_state(system_state: Dict[str, Any]) -> None:
    _state_replay_buffer.append(
        {
            "frame_id": system_state.get("frame_id"),
            "tick_timestamp": system_state.get("tick_timestamp"),
            "state": json.loads(json.dumps(system_state, default=str)),
        }
    )


def _validate_system_state_contract(system_state: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    required = SYSTEM_STATE_SCHEMA["required"]
    for key in required:
        if key not in system_state:
            errors.append(f"missing_required:{key}")

    if not isinstance(system_state.get("frame_id"), int):
        errors.append("type_error:frame_id")
    if not isinstance(system_state.get("tick_timestamp"), int):
        errors.append("type_error:tick_timestamp")
    if not isinstance(system_state.get("junctions", {}), dict):
        errors.append("type_error:junctions")
    if not isinstance(system_state.get("session_metrics", {}), dict):
        errors.append("type_error:session_metrics")
    if not isinstance(system_state.get("ai_decisions", []), list):
        errors.append("type_error:ai_decisions")
    if not isinstance(system_state.get("emergency", {}), dict):
        errors.append("type_error:emergency")
    if not isinstance(system_state.get("anomalies", []), list):
        errors.append("type_error:anomalies")
    if not isinstance(system_state.get("incidents", []), list):
        errors.append("type_error:incidents")
    if not isinstance(system_state.get("esg", {}), dict):
        errors.append("type_error:esg")
    if not isinstance(system_state.get("maintenance", {}), dict):
        errors.append("type_error:maintenance")
    if not isinstance(system_state.get("cybersecurity", {}), dict):
        errors.append("type_error:cybersecurity")
    if not isinstance(system_state.get("health", {}), dict):
        errors.append("type_error:health")

    return errors


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


def _push_ai_decision(jid: str, action: str, confidence: float, reason: str) -> None:
    ctx = _current_frame_context()
    _ai_decision_feed.appendleft(
        {
            "ts": round(time.time(), 3),
            "tick_timestamp": ctx["tick_timestamp"],
            "frame_id": ctx["frame_id"],
            "junction_id": jid,
            "action": action,
            "confidence": round(float(confidence), 3),
            "reason": reason,
        }
    )
    _append_audit_event("AI_DECISION", jid, action, {"confidence": round(float(confidence), 3), "reason": reason})


def _push_incident(event_type: str, location: str, status: str, detail: str) -> None:
    ctx = _current_frame_context()
    _incident_log.appendleft(
        {
            "id": f"evt_{int(time.time() * 1000)}",
            "type": event_type,
            "location": location,
            "status": status,
            "time": round(time.time(), 3),
            "tick_timestamp": ctx["tick_timestamp"],
            "frame_id": ctx["frame_id"],
            "detail": detail,
        }
    )
    _append_audit_event("INCIDENT", location, event_type, {"status": status, "detail": detail})


def _session_metrics_payload() -> Dict[str, float]:
    samples = max(1, int(_session_metrics.get("samples", 0)))
    ai_wait = _session_metrics["ai_wait_sum"] / samples
    baseline_wait = _session_metrics["baseline_wait_sum"] / samples
    ai_idle = _session_metrics["ai_idle_sum"] / samples
    baseline_idle = _session_metrics["baseline_idle_sum"] / samples
    queue_len = _session_metrics["queue_sum"] / samples
    improvement = 0.0
    if baseline_wait > 0:
        improvement = ((baseline_wait - ai_wait) / baseline_wait) * 100.0
    return {
        "samples": int(_session_metrics["samples"]),
        "session_minutes": round((time.time() - _session_started_at) / 60.0, 2),
        "avg_wait_ai_s": round(ai_wait, 2),
        "avg_wait_baseline_s": round(baseline_wait, 2),
        "avg_idle_ai_s": round(ai_idle, 2),
        "avg_idle_baseline_s": round(baseline_idle, 2),
        "avg_queue_length": round(queue_len, 2),
        "improvement_pct": round(improvement, 2),
        "saved_vehicle_minutes": round(_session_metrics["saved_vehicle_minutes"], 2),
        "emissions_saved_kg": round(_session_metrics["emissions_saved_kg"], 3),
        "emission_factor_kg_per_idle_second": 0.00062,
    }


def _build_emergency_state() -> Dict:
    state = {
        "active": False,
        "corridor_id": None,
        "route": [],
        "eta_seconds": 0.0,
        "progress_pct": 0.0,
        "current_leg_index": 0,
        "completed_events": list(_completed_emergency_events),
    }
    if not emergency_engine:
        return state

    active_events = list(emergency_engine._active_events.values())
    active_ids = set(e.event_id for e in active_events)
    for stale_id in _active_emergency_ids - active_ids:
        _completed_emergency_events.appendleft(
            {
                "event_id": stale_id,
                "completed_at": round(time.time(), 3),
            }
        )
    _active_emergency_ids.clear()
    _active_emergency_ids.update(active_ids)

    if not active_events:
        return state

    event = active_events[0]
    elapsed = max(0.0, time.time() - float(event.activated_at))
    planned = max(1.0, float(event.estimated_time_s))
    progress = min(1.0, elapsed / planned)
    route = list(event.path or [])
    leg_idx = 0
    if route:
        leg_idx = min(len(route) - 1, int(progress * len(route)))

    state.update(
        {
            "active": True,
            "corridor_id": event.event_id,
            "route": route,
            "eta_seconds": round(max(0.0, planned - elapsed), 1),
            "progress_pct": round(progress * 100.0, 1),
            "current_leg_index": leg_idx,
            "vehicle_type": event.vehicle_type,
            "response_improvement_pct": 34.0,
        }
    )
    return state


def _build_incidents_payload() -> Dict[str, List[Dict]]:
    events: List[Dict] = list(_incident_log)
    anomalies: List[Dict] = []
    ctx = _current_frame_context()
    now = round(time.time(), 3)

    if live_runtime.latest_incidents:
        for idx, inc in enumerate(live_runtime.latest_incidents[:8]):
            events.append(
                {
                    "id": f"cv_inc_{idx}_{int(now)}",
                    "type": str(inc.get("type", "incident")),
                    "location": str(inc.get("junction_id", _selected_junction_id)),
                    "status": str(inc.get("status", "active")),
                    "time": now,
                    "tick_timestamp": ctx["tick_timestamp"],
                    "frame_id": ctx["frame_id"],
                    "detail": str(inc.get("lane", "lane_unknown")),
                }
            )

    anomaly = live_runtime.latest_anomaly or {}
    if anomaly:
        anomalies.append(
            {
                "type": str(anomaly.get("type", "anomaly")),
                "junction": _selected_junction_id,
                "severity": str(anomaly.get("severity", "medium")),
                "status": "active" if anomaly.get("is_anomaly") else "resolved",
                "timestamp": now,
                "tick_timestamp": ctx["tick_timestamp"],
                "frame_id": ctx["frame_id"],
            }
        )

    return {
        "incidents": events[:20],
        "anomalies": anomalies[:10],
    }


def _build_security_payload() -> Dict:
    alerts: List[Dict] = []
    if security_detector:
        raw = security_detector.get_events(limit=8)
        for item in raw:
            alerts.append(
                {
                    "timestamp": item.get("timestamp", round(time.time(), 3)),
                    "severity": item.get("severity", "medium"),
                    "message": item.get("message", item.get("event", "security event")),
                    "junction": item.get("junction_id", "system"),
                }
            )
    integrity = "ok"
    if any(a.get("severity") == "high" for a in alerts):
        integrity = "warning"
    return {
        "integrity": integrity,
        "alerts": alerts,
        "api_misuse_score": round(min(1.0, len(alerts) / 10.0), 2),
    }


def _congestion_from_density(density: float) -> str:
    if density < 0.33:
        return "low"
    if density < 0.66:
        return "medium"
    return "high"


def _phase_from_lane(lane: Optional[str]) -> str:
    if lane in ("north", "south"):
        return "NS_GREEN"
    if lane in ("east", "west"):
        return "EW_GREEN"
    return "ALL_RED"


def _active_lane_from_phase(phase: str) -> str:
    if phase == "NS_GREEN":
        return "north_south"
    if phase == "EW_GREEN":
        return "east_west"
    if phase == "YELLOW":
        return "transition"
    return "all_stop"


def _camera_direction_from_phase(phase: str) -> str:
    if phase == "EW_GREEN":
        return "east"
    if phase == "NS_GREEN":
        return "north"
    if phase == "YELLOW":
        return "north"
    return "north"


def _normalize_phase_name(phase: str) -> str:
    p = str(phase or "").strip().upper().replace("-", "_")
    if p.startswith("NS"):
        return "NS_GREEN" if "GREEN" in p else "YELLOW"
    if p.startswith("EW"):
        return "EW_GREEN" if "GREEN" in p else "YELLOW"
    if p in {"YELLOW", "ALL_RED", "ALLRED"}:
        return "ALL_RED" if p in {"ALL_RED", "ALLRED"} else "YELLOW"
    return "NS_GREEN"


def _lane_distribution_from_snapshot(vehicle_count: int, lane_waiting: Dict[str, Any]) -> Dict[str, int]:
    lane_waiting = lane_waiting or {}
    vals = {
        "north": max(0.0, float(lane_waiting.get("north", 0.0) or 0.0)),
        "south": max(0.0, float(lane_waiting.get("south", 0.0) or 0.0)),
        "east": max(0.0, float(lane_waiting.get("east", 0.0) or 0.0)),
        "west": max(0.0, float(lane_waiting.get("west", 0.0) or 0.0)),
    }
    total = sum(vals.values())
    if total <= 0:
        q = max(0, int(vehicle_count))
        split = q // 4
        rem = q - 4 * split
        return {
            "north": split + (1 if rem > 0 else 0),
            "south": split + (1 if rem > 1 else 0),
            "east": split + (1 if rem > 2 else 0),
            "west": split,
        }
    return {
        "north": int(round(vehicle_count * vals["north"] / total)),
        "south": int(round(vehicle_count * vals["south"] / total)),
        "east": int(round(vehicle_count * vals["east"] / total)),
        "west": int(round(vehicle_count * vals["west"] / total)),
    }


def _apply_traffic_snapshot_to_junctions(traffic: Dict[str, Any]) -> None:
    if not isinstance(traffic, dict):
        return
    junctions = traffic.get("junctions", {})
    if not isinstance(junctions, dict) or not junctions:
        return

    for jid, js in junctions.items():
        if jid not in _junction_states or not isinstance(js, dict):
            continue
        st = _junction_states[jid]
        vehicle_count = int(js.get("vehicle_count", st.get("vehicle_count", 0)) or 0)
        queue_length = float(js.get("queue_length", st.get("queue_length", vehicle_count)) or 0.0)
        waiting_time = float(js.get("waiting_time", js.get("avg_waiting_time", st.get("wait_time", 0.0))) or 0.0)
        density = min(1.0, max(0.0, float(js.get("density", queue_length / 30.0))))
        lane_dist = _lane_distribution_from_snapshot(vehicle_count, js.get("lane_waiting", {}))
        phase = _normalize_phase_name(js.get("phase", st.get("phase", "NS_GREEN")))

        st["vehicle_count"] = max(0, vehicle_count)
        st["queue_length"] = round(max(0.0, queue_length), 2)
        st["wait_time"] = round(max(0.0, waiting_time), 2)
        st["avg_waiting_time"] = st["wait_time"]
        st["density"] = round(density, 3)
        st["congestion_level"] = str(js.get("congestion_level", _congestion_from_density(density)))
        st["lane_distribution"] = lane_dist
        st["queue_n"] = int(lane_dist.get("north", 0))
        st["queue_s"] = int(lane_dist.get("south", 0))
        st["queue_e"] = int(lane_dist.get("east", 0))
        st["queue_w"] = int(lane_dist.get("west", 0))
        st["signal_state"] = phase
        st["phase"] = phase
        st["active_lane"] = _active_lane_from_phase(phase)
        st["camera_direction"] = _camera_direction_from_phase(phase)
        st["ai_reason"] = st.get("ai_reason") or "Telemetry synced from active snapshot"
        hm = st.get("health_metrics") if isinstance(st.get("health_metrics"), dict) else {}
        hm["detection_count"] = max(0, vehicle_count)
        st["health_metrics"] = hm

    _refresh_phase_countdowns()


def _apply_phase_to_junction(jid: str, phase: str, source: str, duration_s: int = 20) -> None:
    if jid not in _junction_states:
        return
    _junction_states[jid]["phase"] = phase
    _junction_states[jid]["signal_state"] = phase
    _junction_states[jid]["active_lane"] = _active_lane_from_phase(phase)
    _junction_states[jid]["camera_direction"] = _camera_direction_from_phase(phase)
    _junction_states[jid]["phase_remaining"] = max(1, int(duration_s))
    _junction_states[jid]["phase_expires_at"] = time.time() + max(1, int(duration_s))
    _junction_states[jid]["last_source"] = source


def _refresh_phase_countdowns() -> None:
    now = time.time()
    for st in _junction_states.values():
        expires = float(st.get("phase_expires_at", now + 1))
        st["phase_remaining"] = max(0, int(expires - now))


def _update_junction_telemetry_from_runtime() -> None:
    global _last_traffic_snapshot
    if not live_runtime.enabled:
        traffic = _last_traffic_snapshot
        if (not traffic) and demo_gen:
            traffic = demo_gen.get_snapshot()
            _last_traffic_snapshot = traffic
        _apply_traffic_snapshot_to_junctions(traffic)
        return

    base_cv = live_runtime.latest_cv_summary or {}
    base_count = int(base_cv.get("vehicle_count", 0))
    base_density = float(base_cv.get("density", 0.0))
    base_cong = str(base_cv.get("congestion_level", _congestion_from_density(base_density)))
    per_lane = dict(base_cv.get("per_lane", {"north": 0, "south": 0, "east": 0, "west": 0}))
    health = live_runtime.health
    runtime = live_runtime.status()

    if _selected_junction_id in _junction_states:
        st = _junction_states[_selected_junction_id]
        st["vehicle_count"] = base_count
        st["congestion_level"] = base_cong
        st["density"] = round(base_density, 3)
        st["lane_distribution"] = per_lane
        st["system_health"] = health
        st["health_metrics"] = {
            "fps": runtime.get("fps", 0.0),
            "latency_ms": runtime.get("latency_ms", {"min": 0.0, "avg": 0.0, "max": 0.0}),
            "frame_drop_rate": runtime.get("frame_drop_rate", 0.0),
            "detection_count": base_count,
            "ws_delay_ms": runtime.get("ws_delay_ms", {"min": 0.0, "avg": 0.0, "max": 0.0}),
        }

    idx = 0
    for jid, st in _junction_states.items():
        if jid == _selected_junction_id:
            continue
        idx += 1
        # Deterministic pseudo-variance across junctions for demo visibility.
        var = ((live_runtime._tick + idx * 7) % 5) - 2
        count = max(1, base_count + var + idx)
        density = min(1.0, max(0.05, base_density + 0.04 * var + 0.03 * idx))
        st["vehicle_count"] = int(count)
        st["density"] = round(float(density), 3)
        st["congestion_level"] = _congestion_from_density(float(density))
        st["lane_distribution"] = {
            "north": max(0, int(count * 0.30)),
            "south": max(0, int(count * 0.22)),
            "east": max(0, int(count * 0.26)),
            "west": max(0, int(count * 0.22)),
        }
        st["system_health"] = health

    _refresh_phase_countdowns()


class LiveRuntime:
    """Connect vision, IoT, prediction, anomaly, and RL into one live tick."""

    def __init__(self) -> None:
        self.enabled = LIVE_MODE and not DEMO_MODE
        self.real_data_only = os.getenv("REAL_DATA_ONLY", "true").lower() == "true"
        self.mode = os.getenv("RUN_MODE", "real").strip().lower()
        if self.mode not in ("real", "demo"):
            self.mode = "real"
        self.intersection_id = os.getenv("PRIMARY_INTERSECTION", "J1_1")
        self.video_source = os.getenv("TRAFFIC_VIDEO_SOURCE", "0")
        self.vision_backend = os.getenv("VISION_BACKEND", "yolo")
        self.vision_device = os.getenv("VISION_DEVICE", "cpu")
        self.vision_conf = max(0.25, min(0.4, float(os.getenv("VISION_CONF", "0.35"))))
        self.resize_width = int(os.getenv("VISION_RESIZE_W", "640"))
        self.resize_height = int(os.getenv("VISION_RESIZE_H", "480"))
        self.debug_cv = os.getenv("DEBUG_CV", "false").lower() == "true"
        fail_fast_env = os.getenv("FAIL_FAST_VIDEO")
        if fail_fast_env is None:
            fail_fast_env = os.getenv("FAIL_ON_MISSING_VIDEO", "false")
        self.fail_fast_video = str(fail_fast_env).lower() not in {"0", "false", "no", "off"}
        self.video_init_retries = max(1, int(os.getenv("VIDEO_INIT_RETRIES", "5")))
        self.black_frame_mean_threshold = float(os.getenv("BLACK_FRAME_MEAN_THRESHOLD", "5.0"))
        self.health = "healthy"
        self._lock = asyncio.Lock()
        self._tick = 0

        self.cap = None
        self.detector = None
        self.tracker = None
        self.counter = None
        self.speed = None
        self.incident = None

        self.sensor_sim = None
        self.sensor_fusion = None
        self.mqtt = None

        self.lstm = None
        self.ml_anomaly = None
        self.rl = None
        self.graph_coordinator = None
        self.graph_runtime_enabled = os.getenv("GRAPH_RUNTIME_ENABLED", "false").lower() == "true"

        self.latest_traffic: Dict = {}
        self.latest_incidents: List[Dict] = []
        self.latest_anomaly: Optional[Dict] = None
        self.latest_prediction: Optional[List[float]] = None
        self.latest_frame_jpeg: Optional[bytes] = None
        self.last_error: str = ""
        self.frame_ok = False
        self._last_open_attempt = 0.0
        self._is_file_source = False
        self.startup_validation_error: str = ""
        self.fallback_triggered = False
        self.fallback_reason = ""
        self.latest_markers: List[Dict] = []
        self.latest_heatmap: List[List[float]] = []
        self.latest_roads: List[Dict] = []
        self.latest_cv_summary: Dict = {}
        self.latest_frame_stats: Dict = {}

        self.frame_count = 0
        self.frame_drop_count = 0
        self.reconnect_attempts = 0
        self.consecutive_zero_frames = 0
        self.max_zero_frames_warn = int(os.getenv("ZERO_FRAMES_WARN", "10"))
        self._density_history = collections.deque(maxlen=12)
        self._lane_history = collections.deque(maxlen=12)
        self._tick_ms = collections.deque(maxlen=300)
        self._ws_delay_ms = collections.deque(maxlen=300)

        # CPU-first mapping config around a real city center.
        center_lat = float(os.getenv("MAP_CENTER_LAT", "28.6139"))
        center_lon = float(os.getenv("MAP_CENTER_LON", "77.2090"))
        self.map_center = {"lat": center_lat, "lon": center_lon}
        self._geo_mapper = None
        if RoadGeoMapper:
            self._geo_mapper = RoadGeoMapper(
                city_center_lat=center_lat,
                city_center_lon=center_lon,
                frame_width=int(os.getenv("MAP_FRAME_WIDTH", str(self.resize_width))),
                frame_height=int(os.getenv("MAP_FRAME_HEIGHT", str(self.resize_height))),
                span_lat=float(os.getenv("MAP_SPAN_LAT", "0.012")),
                span_lon=float(os.getenv("MAP_SPAN_LON", "0.016")),
            )

        if not self.enabled:
            return

        # Vision stack
        if VehicleDetector and VehicleTracker and ZoneCounter and SpeedEstimator and IncidentDetector:
            self.detector = VehicleDetector(
                backend=self.vision_backend,
                conf_threshold=self.vision_conf,
                device=self.vision_device,
            )
            self.tracker = VehicleTracker()
            self.counter = ZoneCounter(frame_shape=(self.resize_height, self.resize_width))
            self.speed = SpeedEstimator(fps=float(os.getenv("VISION_FPS", "25")))
            self.incident = IncidentDetector()

            self._open_video_source()

        # IoT stack
        if SensorFusion:
            self.sensor_fusion = SensorFusion()

        sim_fallback = os.getenv("ENABLE_SIMULATION_FALLBACK", "false").lower() == "true"
        if sim_fallback and not self.real_data_only and SensorSimulator and self.sensor_fusion:
            self.sensor_sim = SensorSimulator(
                intersection_ids=[self.intersection_id],
                real_time=False,
                sim_step_s=float(os.getenv("IOT_STEP_SECONDS", "5")),
            )

        if MQTTClient:
            self.mqtt = MQTTClient(
                broker_host=os.getenv("MQTT_HOST", "localhost"),
                broker_port=int(os.getenv("MQTT_PORT", "1883")),
            )

        # Prediction + anomaly
        if LSTMPredictor:
            try:
                self.lstm = LSTMPredictor(
                    device=os.getenv("LSTM_DEVICE", "cpu"),
                    model_path=os.getenv("LSTM_MODEL_PATH", "models/lstm_live.pt"),
                )
            except Exception as exc:
                logger.warning("[LiveRuntime] LSTM init failed (%s). Using no-predict mode.", exc)
                self.lstm = None
        if MLAnomalyDetector:
            self.ml_anomaly = MLAnomalyDetector(device=os.getenv("ANOMALY_DEVICE", "cpu"))
            try:
                self.ml_anomaly.load(ANOMALY_MODEL_DIR)
            except Exception:
                logger.info("[LiveRuntime] ML anomaly models not loaded yet.")

        # RL controller for live phase recommendation
        if RLController:
            self.rl = RLController(
                intersection_id=self.intersection_id,
                device=os.getenv("RL_DEVICE", "cpu"),
            )

        if self.graph_runtime_enabled and MultiAgentCoordinator:
            try:
                coord_ids = [f"J{r}_{c}" for r in range(4) for c in range(4)]
                self.graph_coordinator = MultiAgentCoordinator(
                    intersection_ids=coord_ids,
                    graph_enabled=True,
                    graph_debug=os.getenv("GRAPH_DEBUG", "false").lower() == "true",
                    safety_shield_enabled=os.getenv("GRAPH_SAFETY_SHIELD", "true").lower() == "true",
                    min_action_hold_steps=int(os.getenv("GRAPH_MIN_HOLD_STEPS", "2")),
                    device=os.getenv("RL_DEVICE", "cpu"),
                )
            except Exception as exc:
                logger.warning("[LiveRuntime] graph coordinator init failed: %s", exc)
                self.graph_coordinator = None

    async def tick(self) -> Dict:
        async with self._lock:
            tick_t0 = time.perf_counter()
            self._tick += 1

            snapshot = None
            if self.sensor_sim and self.sensor_fusion:
                readings = self.sensor_sim.tick()
                if self.mqtt:
                    for rd in readings:
                        self.mqtt.publish_reading(rd)
                fused = self.sensor_fusion.ingest(readings)
                snapshot = fused.get(self.intersection_id)

            # Auto-reconnect video source in case camera/file is temporarily unavailable.
            if (
                self.detector
                and (self.cap is None or not self.cap.isOpened())
                and (time.time() - self._last_open_attempt) > 3.0
            ):
                self._open_video_source()

            # Vision updates (if a real frame is available)
            real_detections = []
            if self.cap and self.detector and self.tracker and self.counter and self.speed and self.incident:
                ok, frame = self.cap.read()
                self.frame_count += 1
                self.frame_ok = bool(ok)
                if not ok or frame is None:
                    self.frame_drop_count += 1
                    self.health = "degraded"
                    self._recover_stream_end()
                if ok and frame is not None:
                    frame = self._resize_frame(frame)
                    det = self.detector.detect(frame)
                    conf_scores = [round(float(d.confidence), 3) for d in det]
                    _log_event(
                        "cv",
                        "frame_detections",
                        frame_index=self._tick,
                        detections=len(det),
                        confidences=conf_scores[:20],
                    )
                    tracked = self.tracker.update(det)
                    zone_stats = self.counter.update(tracked)
                    track_speeds = self.speed.estimate(self.tracker.active_tracks())
                    frame_view = self.detector.draw(frame, tracked if tracked else det) if self.debug_cv else frame
                    self.latest_frame_jpeg = self._encode_jpeg(frame_view)
                    real_detections = tracked if tracked else det

                    vehicle_count = len(real_detections)
                    if vehicle_count == 0:
                        self.consecutive_zero_frames += 1
                        if self.consecutive_zero_frames > self.max_zero_frames_warn:
                            self.health = "degraded"
                            _log_event(
                                "cv",
                                "zero_detection_warning",
                                consecutive_zero_frames=self.consecutive_zero_frames,
                                threshold=self.max_zero_frames_warn,
                            )
                    else:
                        self.consecutive_zero_frames = 0

                    self.latest_frame_stats = {
                        "frame": self._tick,
                        "vehicle_count": vehicle_count,
                        "detections": [
                            {
                                "id": int(getattr(d, "track_id", -1)),
                                "label": str(getattr(d, "label", "vehicle")),
                                "confidence": round(float(getattr(d, "confidence", 0.0)), 3),
                                "bbox": list(getattr(d, "bbox", (0, 0, 0, 0))),
                            }
                            for d in real_detections[:80]
                        ],
                    }

                    incidents = self.incident.update(
                        {k: v["queue"] for k, v in zone_stats.items()},
                        track_speeds,
                    )
                    self.latest_incidents = [
                        {
                            "id": i.incident_id,
                            "type": i.incident_type,
                            "severity": i.severity,
                            "zone": i.zone,
                            "description": i.description,
                        }
                        for i in incidents
                    ]

                    if self.sensor_fusion:
                        avg_speed = float(np.mean(list(track_speeds.values()))) if track_speeds else 0.0
                        for ap in ("north", "south", "east", "west"):
                            q = int(zone_stats.get(ap, {}).get("queue", 0))
                            self.sensor_fusion.ingest_vision(self.intersection_id, ap, q, avg_speed)
                        snapshot = self.sensor_fusion.snapshot(self.intersection_id)

            # Build map telemetry from real detections only.
            self._update_map_telemetry(real_detections)

            # In strict real-data mode, do not retain snapshots when camera has no frame.
            if self.real_data_only and not self.frame_ok:
                snapshot = None

            traffic = self._to_traffic_snapshot(snapshot)
            self.latest_traffic = traffic

            # LSTM online prediction
            if self.lstm and snapshot is not None:
                try:
                    self.lstm.add_observation(snapshot)
                    pred = self.lstm.predict()
                    if pred is not None:
                        self.latest_prediction = pred[0].astype(float).tolist()
                except Exception as exc:
                    self.last_error = f"lstm: {exc}"

            # ML anomaly from fused feature vector
            if self.ml_anomaly and snapshot is not None:
                try:
                    vec = self._to_anomaly_vector(snapshot)
                    self.ml_anomaly.add_observation(vec)
                    if not getattr(self.ml_anomaly, "_fitted", False) and self._tick % 120 == 0:
                        self.ml_anomaly.fit(ae_epochs=6)
                    alert = self.ml_anomaly.detect(vec) if getattr(self.ml_anomaly, "_fitted", False) else None
                    if alert:
                        self.latest_anomaly = {
                            "severity": alert.severity,
                            "score": float(alert.anomaly_score),
                            "detectors": alert.detectors_fired,
                            "message": alert.message,
                        }
                except Exception as exc:
                    self.last_error = f"anomaly: {exc}"

            # RL decision from current observation
            if self.rl and snapshot is not None:
                try:
                    obs = snapshot.to_feature_vector()
                    action = self.rl.predict(obs)
                    phase = self._action_to_phase(action)
                    if self.intersection_id in _junction_states:
                        _junction_states[self.intersection_id]["phase"] = phase
                        _junction_states[self.intersection_id]["ai_confidence"] = 0.92
                except Exception as exc:
                    self.last_error = f"rl: {exc}"

            # Optional graph-coordinated inference over all junctions.
            if self.graph_coordinator and _junction_states:
                try:
                    graph_snapshots: Dict[str, Dict[str, Any]] = {}
                    for jid, st in _junction_states.items():
                        graph_snapshots[jid] = {
                            "queue_length": float(st.get("queue_n", 0) + st.get("queue_s", 0) + st.get("queue_e", 0) + st.get("queue_w", 0)),
                            "waiting_time": float(st.get("wait_time", 0.0)),
                            "current_phase": float(0 if st.get("phase") == "NS_GREEN" else 1),
                            "phase_time": float(st.get("phase_remaining", 0)),
                            "predicted_inflow": float(st.get("vehicle_count", 0.0)),
                            "emergency_flag": bool(st.get("is_corridor", False)),
                            "occupancy": float(st.get("density", 0.0)),
                        }

                    graph_actions = self.graph_coordinator.step(graph_snapshots)
                    for jid, act in graph_actions.items():
                        phase = self._action_to_phase(int(act))
                        _apply_phase_to_junction(jid, phase, source="ai_graph", duration_s=15)
                    _log_event("graph", "coordinator_tick", active=True, junctions=len(graph_actions))
                except Exception as exc:
                    _log_event("graph", "coordinator_fallback", active=False, error=str(exc))

            tick_ms = (time.perf_counter() - tick_t0) * 1000.0
            self._tick_ms.append(tick_ms)

            return traffic

    @staticmethod
    def _encode_jpeg(frame) -> Optional[bytes]:
        cv2 = _optional_cv2()
        if cv2 is None:
            return None
        try:
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok:
                return None
            return buf.tobytes()
        except Exception:
            return None

    def _activate_demo_fallback(self, reason: str) -> None:
        """Disable live runtime and switch to demo mode after repeated camera failures."""
        self.fallback_triggered = True
        self.fallback_reason = reason
        self.enabled = False
        self.health = "degraded"
        self.last_error = reason
        _ensure_demo_mode(reason)

    def _open_video_source(self) -> None:
        self._last_open_attempt = time.time()
        self.reconnect_attempts += 1
        self.startup_validation_error = ""
        try:
            cv2 = _optional_cv2()
            if cv2 is None:
                self.startup_validation_error = "OpenCV unavailable"
                self._activate_demo_fallback(self.startup_validation_error)
                return

            source = int(self.video_source) if str(self.video_source).isdigit() else self.video_source
            self._is_file_source = isinstance(source, str) and os.path.isfile(source)

            last_error = "Video source unavailable"
            for attempt in range(1, self.video_init_retries + 1):
                cap = cv2.VideoCapture(source)
                if not (cap and cap.isOpened()):
                    last_error = "Video source unavailable"
                    logger.warning(
                        "[LiveRuntime] Video source unavailable on attempt %d/%d: %s",
                        attempt,
                        self.video_init_retries,
                        self.video_source,
                    )
                    if cap:
                        cap.release()
                    continue

                ok, first = cap.read()
                if not ok or first is None:
                    last_error = "Video source opened but first frame is invalid"
                    _log_event("video", "first_frame_invalid", source=self.video_source, attempt=attempt)
                    logger.warning(
                        "[LiveRuntime] First frame invalid on attempt %d/%d",
                        attempt,
                        self.video_init_retries,
                    )
                    cap.release()
                    continue

                first = self._resize_frame(first)
                frame_mean = float(np.mean(first))
                _log_event(
                    "video",
                    "first_frame",
                    source=self.video_source,
                    shape=list(first.shape),
                    mean_pixel=round(frame_mean, 2),
                    attempt=attempt,
                )

                if frame_mean <= self.black_frame_mean_threshold:
                    last_error = f"First frame appears black (mean={frame_mean:.2f})"
                    _log_event(
                        "video",
                        "first_frame_black",
                        source=self.video_source,
                        mean=round(frame_mean, 2),
                        attempt=attempt,
                    )
                    logger.warning(
                        "[LiveRuntime] Black first frame on attempt %d/%d (mean=%.2f)",
                        attempt,
                        self.video_init_retries,
                        frame_mean,
                    )
                    if not self._is_file_source:
                        self.cap = cap
                        self.frame_ok = True
                        logger.warning("[LiveRuntime] Accepting dark webcam warm-up frame and staying in live mode")
                        return
                    cap.release()
                    continue

                self.cap = cap
                self.frame_ok = True
                if self._is_file_source:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                logger.info("[LiveRuntime] Video source connected: %s", self.video_source)
                return

            self.cap = None
            self.frame_ok = False
            self.startup_validation_error = last_error
            logger.error("[LiveRuntime] Camera init failed after %d attempts: %s", self.video_init_retries, last_error)

            # Always prefer fallback over startup failure.
            self._activate_demo_fallback(last_error)
            if self.fail_fast_video:
                logger.error("[LiveRuntime] FAIL_FAST_VIDEO=true is set, but fallback is enforced to keep server up.")

        except Exception as exc:
            self.last_error = f"video init: {exc}"
            self.frame_ok = False
            self.startup_validation_error = self.last_error
            logger.exception("[LiveRuntime] Video init exception")
            self._activate_demo_fallback(self.last_error)

    def _recover_stream_end(self) -> None:
        if not self.cap:
            return
        try:
            cv2 = _optional_cv2()
            if cv2 is None:
                self._activate_demo_fallback("OpenCV unavailable")
                return

            if self._is_file_source:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, _ = self.cap.read()
                if ok:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.frame_ok = True
                    _log_event("video", "loop_restart", source=self.video_source)
                    return
            self._open_video_source()
        except Exception as exc:
            self.last_error = f"video recover: {exc}"

    def _resize_frame(self, frame):
        try:
            cv2 = _optional_cv2()
            if cv2 is None:
                return frame

            return cv2.resize(frame, (self.resize_width, self.resize_height))
        except Exception:
            return frame

    def _inject_demo_markers(self) -> List[Dict]:
        # Minimal synthetic traffic when demo mode is enabled and CV is empty.
        n = random.randint(5, 15)
        markers: List[Dict] = []
        heat: List[List[float]] = []
        lane_counts = {"north": 0, "south": 0, "east": 0, "west": 0}
        for i in range(n):
            lat = self.map_center["lat"] + random.uniform(-0.0035, 0.0035)
            lon = self.map_center["lon"] + random.uniform(-0.0045, 0.0045)
            lane = random.choice(list(lane_counts.keys()))
            lane_counts[lane] += 1
            conf = round(random.uniform(0.55, 0.92), 3)
            markers.append(
                {
                    "id": 10000 + i,
                    "lat": lat,
                    "lon": lon,
                    "lane": lane,
                    "label": "demo_vehicle",
                    "confidence": conf,
                    "fallback": True,
                }
            )
            heat.append([lat, lon, min(1.0, 0.45 + conf * 0.55)])

        self.latest_heatmap = heat
        self.latest_roads = self._roads_from_lane_counts(lane_counts)
        self.latest_cv_summary = {
            "vehicle_count": n,
            "density": round(min(1.0, n / 25.0), 3),
            "congestion_level": "medium",
            "per_lane": lane_counts,
            "mode": "synthetic_fallback",
            "degraded": True,
        }
        return markers

    def _update_map_telemetry(self, detections: List) -> None:
        markers: List[Dict] = []
        heatmap: List[List[float]] = []
        lane_counts: Dict[str, int] = {"north": 0, "south": 0, "east": 0, "west": 0}

        if not self._geo_mapper or not detections:
            if self.mode == "demo":
                self.latest_markers = self._inject_demo_markers()
                _log_event("cv", "fallback_traffic_injected", mode=self.mode, markers=len(self.latest_markers))
                return
            self.latest_markers = []
            self.latest_heatmap = []
            self.latest_roads = self._roads_from_lane_counts(lane_counts)
            self.latest_cv_summary = {
                "vehicle_count": 0,
                "density": 0.0,
                "congestion_level": "low",
                "per_lane": lane_counts,
                "mode": "real_cv",
                "degraded": True,
            }
            return

        for d in detections:
            center = getattr(d, "center", None)
            track_id = int(getattr(d, "track_id", -1))
            label = str(getattr(d, "label", "vehicle"))
            conf = float(getattr(d, "confidence", 0.0))

            if not center:
                bbox = getattr(d, "bbox", None)
                if bbox and len(bbox) == 4:
                    center = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
                else:
                    continue

            lat, lon = self._geo_mapper.map_pixel(center[0], center[1])
            lane = self._geo_mapper.lane_name(center[0])
            lane_counts[lane] += 1
            markers.append({
                "id": track_id,
                "lat": lat,
                "lon": lon,
                "lane": lane,
                "label": label,
                "confidence": conf,
            })
            heatmap.append([lat, lon, min(1.0, 0.35 + conf * 0.65)])

        self._lane_history.append(lane_counts.copy())
        smooth_lane = {k: 0 for k in lane_counts}
        if self._lane_history:
            for lane in smooth_lane:
                smooth_lane[lane] = int(round(np.mean([h[lane] for h in self._lane_history])))

        roads = self._roads_from_lane_counts(lane_counts)
        area = float(max(1, self.resize_width * self.resize_height))
        density_raw = min(1.0, (len(markers) / area) * 120000.0)
        self._density_history.append(density_raw)
        density = float(np.mean(self._density_history)) if self._density_history else density_raw
        if density < 0.33:
            cong = "low"
        elif density < 0.66:
            cong = "medium"
        else:
            cong = "high"

        degraded = all(v == 0 for v in smooth_lane.values())
        self.health = "degraded" if degraded or self.consecutive_zero_frames > self.max_zero_frames_warn else "healthy"

        self.latest_markers = markers
        self.latest_heatmap = heatmap
        self.latest_roads = roads
        self.latest_cv_summary = {
            "vehicle_count": len(markers),
            "density": round(density, 3),
            "congestion_level": cong,
            "per_lane": smooth_lane,
            "mode": "real_cv",
            "degraded": degraded,
        }

    def _roads_from_lane_counts(self, lane_counts: Dict[str, int]) -> List[Dict]:
        if self._geo_mapper:
            roads = self._geo_mapper.summarize_roads(lane_counts)
            out = []
            for r in roads:
                out.append({
                    "road_id": r.road_id,
                    "vehicle_count": r.vehicle_count,
                    "density": round(float(r.density), 3),
                    "congestion": r.congestion,
                })
            return out
        return []

    def map_payload(self) -> Dict:
        c = self.map_center
        return {
            "center": c,
            "markers": self.latest_markers,
            "heatmap": self.latest_heatmap,
            "roads": self.latest_roads,
            "cv": self.latest_cv_summary,
        }

    def status(self) -> Dict:
        frame_drop_rate = (self.frame_drop_count / self.frame_count) if self.frame_count else 0.0

        def _stats(values: collections.deque) -> Dict[str, float]:
            if not values:
                return {"min": 0.0, "avg": 0.0, "max": 0.0}
            arr = list(values)
            return {
                "min": round(float(min(arr)), 2),
                "avg": round(float(np.mean(arr)), 2),
                "max": round(float(max(arr)), 2),
            }

        return {
            "enabled": self.enabled,
            "real_data_only": self.real_data_only,
            "mode": self.mode,
            "frame_ok": self.frame_ok,
            "video_source": self.video_source,
            "vision_backend": self.vision_backend,
            "vision_device": self.vision_device,
            "vision_conf": self.vision_conf,
            "resize": {"width": self.resize_width, "height": self.resize_height},
            "intersection_id": self.intersection_id,
            "has_traffic": bool(self.latest_traffic),
            "has_prediction": self.latest_prediction is not None,
            "has_anomaly": self.latest_anomaly is not None,
            "vehicle_markers": len(self.latest_markers),
            "frame_count": self.frame_count,
            "frame_drop_count": self.frame_drop_count,
            "frame_drop_rate": round(frame_drop_rate, 4),
            "reconnect_attempts": self.reconnect_attempts,
            "consecutive_zero_frames": self.consecutive_zero_frames,
            "fps": round(float(getattr(self.detector, "fps", 0.0)), 2) if self.detector else 0.0,
            "latency_ms": _stats(self._tick_ms),
            "ws_delay_ms": _stats(self._ws_delay_ms),
            "system_health": self.health,
            "latest_frame_stats": self.latest_frame_stats,
            "last_error": self.last_error,
        }

    def note_ws_delay(self, delay_ms: float) -> None:
        self._ws_delay_ms.append(float(delay_ms))

    def _to_traffic_snapshot(self, snap) -> Dict:
        if snap is None:
            return {
                "tick": self._tick,
                "hour": time.localtime().tm_hour,
                "mode": "live",
                "queues": {"north": 0.0, "south": 0.0, "east": 0.0, "west": 0.0},
                "waiting_times": {"north": 0.0, "south": 0.0, "east": 0.0, "west": 0.0},
                "total_queue": 0.0,
                "avg_waiting_time": 0.0,
                "throughput": 0.0,
                "phase": _junction_states.get(self.intersection_id, {}).get("phase", "NS_GREEN"),
                "time_factor": 1.0,
            }

        queues = {}
        waits = {}
        throughput = 0.0
        for ap in ("north", "south", "east", "west"):
            st = snap.approaches.get(ap)
            q = float(st.queue_length if st else 0.0)
            queues[ap] = q
            waits[ap] = float(q * 3.0)
            throughput += float(st.flow_veh_h if st else 0.0)

        return {
            "tick": self._tick,
            "hour": time.localtime().tm_hour,
            "mode": "live",
            "queues": queues,
            "waiting_times": waits,
            "total_queue": float(sum(queues.values())),
            "avg_waiting_time": float(sum(waits.values()) / 4.0),
            "throughput": float(throughput),
            "phase": _junction_states.get(self.intersection_id, {}).get("phase", "NS_GREEN"),
            "time_factor": 1.0,
            "rainfall": float(snap.rainfall_mm_h),
            "visibility_m": float(snap.visibility_m),
            "aqi": float(snap.aqi),
        }

    @staticmethod
    def _action_to_phase(action: int) -> str:
        if action in (0, 1):
            return "NS_GREEN" if action == 0 else "EW_GREEN"
        if action == 2:
            return "YELLOW"
        return "ALL_RED"

    @staticmethod
    def _to_anomaly_vector(snap) -> np.ndarray:
        def _apv(ap: str, key: str, default: float = 0.0) -> float:
            st = snap.approaches.get(ap)
            return float(getattr(st, key, default) if st else default)

        hour = time.localtime().tm_hour + time.localtime().tm_min / 60.0
        return np.array([
            _apv("north", "vehicle_count"), _apv("south", "vehicle_count"),
            _apv("east", "vehicle_count"), _apv("west", "vehicle_count"),
            _apv("north", "speed_kmh"), _apv("south", "speed_kmh"),
            _apv("east", "speed_kmh"), _apv("west", "speed_kmh"),
            _apv("north", "queue_length"), _apv("south", "queue_length"),
            _apv("east", "queue_length"), _apv("west", "queue_length"),
            float(np.mean([_apv("north", "occupancy_pct"), _apv("south", "occupancy_pct"), _apv("east", "occupancy_pct"), _apv("west", "occupancy_pct") ])),
            float(np.sin(2 * np.pi * hour / 24.0)),
            float(np.cos(2 * np.pi * hour / 24.0)),
        ], dtype=np.float32)


live_runtime = LiveRuntime()


def _init_junctions():
    """Initialize 4x4 grid junction states."""
    for r in range(4):
        for c in range(4):
            jid = f"J{r}_{c}"
            _junction_states[jid] = {
                "junction_id": jid,
                "phase": "NS_GREEN",
                "signal_state": "NS_GREEN",
                "mode": "ai",
                "vehicle_count": 0,
                "congestion_level": "low",
                "density": 0.0,
                "lane_distribution": {"north": 0, "south": 0, "east": 0, "west": 0},
                "active_lane": "north_south",
                "camera_direction": "north",
                "phase_remaining": 18,
                "phase_expires_at": time.time() + 18,
                "ai_reason": "Awaiting telemetry",
                "rl_action": -1,
                "manual_lane": None,
                "system_health": "healthy",
                "health_metrics": {
                    "fps": 0.0,
                    "latency_ms": {"min": 0.0, "avg": 0.0, "max": 0.0},
                    "frame_drop_rate": 0.0,
                    "detection_count": 0,
                    "ws_delay_ms": {"min": 0.0, "avg": 0.0, "max": 0.0},
                },
                "queue_n": 0, "queue_s": 0, "queue_e": 0, "queue_w": 0,
                "wait_time": 0.0,
                "ai_confidence": 0.95,
                "is_corridor": False,
                "is_overridden": False,
            }


_init_junctions()


def _decision_action_to_phase(action: int) -> str:
    if int(action) == 0:
        return "NS_GREEN"
    if int(action) in (1, 2):
        return "EW_GREEN"
    return "NS_GREEN"


def _init_decision_engine() -> None:
    global _rl_coordinator, _rl_engine_info

    if DECISION_ENGINE_MODE in {"off", "heuristic"}:
        _rl_engine_info = {
            "enabled": False,
            "source": "heuristic",
            "status": "disabled",
            "message": "Configured for heuristic-only decisions",
        }
        return

    if MultiAgentCoordinator is None:
        _rl_engine_info = {
            "enabled": False,
            "source": "heuristic",
            "status": "fallback",
            "message": "RL coordinator unavailable; using heuristic",
        }
        return

    try:
        jids = sorted(_junction_states.keys())
        _rl_coordinator = MultiAgentCoordinator(
            intersection_ids=jids,
            graph_enabled=(os.getenv("GRAPH_RL", "false").lower() == "true"),
            safety_shield_enabled=True,
            min_action_hold_steps=2,
        )
        _rl_engine_info = {
            "enabled": True,
            "source": "rl",
            "status": "active",
            "message": f"RL coordinator active for {len(jids)} junctions",
        }
    except Exception as exc:
        _rl_coordinator = None
        _rl_engine_info = {
            "enabled": False,
            "source": "heuristic",
            "status": "fallback",
            "message": f"RL init failed ({exc}); using heuristic",
        }
        logger.warning("[DecisionEngine] RL coordinator init failed: %s", exc)


def _predict_rl_actions() -> Dict[str, int]:
    if _rl_coordinator is None:
        return {}

    snapshots: Dict[str, Dict[str, Any]] = {}
    for jid, st in _junction_states.items():
        snapshots[jid] = {
            "queue_length": float(st.get("vehicle_count", 0.0)),
            "waiting_time": float(st.get("wait_time", 0.0)),
            "predicted_inflow": float(st.get("density", 0.0)),
            "density": float(st.get("density", 0.0)),
            "current_phase": 0.0 if str(st.get("phase", "NS_GREEN")) == "NS_GREEN" else 1.0,
            "phase_time": float(st.get("phase_remaining", 0.0)),
            "emergency_flag": bool(st.get("mode") == "emergency"),
        }

    try:
        actions = _rl_coordinator.step(snapshots)
        return {str(k): int(v) for k, v in (actions or {}).items()}
    except Exception as exc:
        logger.warning("[DecisionEngine] RL step failed, falling back this tick: %s", exc)
        return {}


# ---------------------------------------------------------------
# REST Endpoints — Core
# ---------------------------------------------------------------
@app.get("/")
def root():
    return {"status": "NEXUS ATMS running"}


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/api/status")
async def status():
    modules_status = {}
    module_map = {
        "emergency": emergency_engine,
        "carbon": carbon_engine,
        "pedestrian_safety": pedestrian_ai,
        "cybersecurity": security_detector,
        "road_maintenance": maintenance_ai,
        "nl_command": nl_parser,
        "counterfactual": counterfactual,
        "voice_broadcast": voice,
    }
    for name, instance in module_map.items():
        modules_status[name] = "active" if instance else f"failed: {_import_errors.get(f'modules.{name}', 'unknown')}"

    runtime_status = live_runtime.status()
    return {
        "status": "running",
        "version": "2.0.0",
        "demo_mode": DEMO_MODE,
        "live_mode": LIVE_MODE,
        "decision_engine": dict(_rl_engine_info),
        "ws_clients": ws_manager.count,
        "junctions": len(_junction_states),
        "modules": modules_status,
        "runtime": runtime_status,
        "runtime_health": runtime_status,
        "camera_source": _camera_source_payload(),
    }


@app.get("/api/schema/system_state")
async def system_state_schema():
    return {
        "name": "system_state",
        "version": "1.0.0",
        "schema": SYSTEM_STATE_SCHEMA,
    }


@app.get("/api/audit/logs")
async def audit_logs(limit: int = Query(200, ge=1, le=5000)):
    items = list(_audit_log)
    return {
        "count": min(limit, len(items)),
        "logs": items[:limit],
    }


@app.get("/api/replay")
async def replay(seconds: int = Query(30, ge=1, le=300)):
    now_ms = int(time.time() * 1000)
    cutoff = now_ms - (seconds * 1000)
    frames = [f for f in list(_state_replay_buffer) if int(f.get("tick_timestamp", 0)) >= cutoff]
    return {
        "seconds": seconds,
        "frames": frames,
        "count": len(frames),
    }


@app.get("/api/live/video")
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


@app.get("/api/map/state")
async def map_state():
    """Real-time map telemetry derived from CV detections."""
    if live_runtime.enabled:
        await live_runtime.tick()
    return {
        "timestamp": time.time(),
        "map": live_runtime.map_payload(),
    }


# ---------------------------------------------------------------
# Multi-camera junction monitoring endpoints
# ---------------------------------------------------------------
_cam_renderers: Dict[str, object] = {}   # key = "{junction_id}_{direction}"
_camera_input_mode: str = "live"
_uploaded_video_path: Optional[str] = None
_camera_source_updated_at: int = int(time.time() * 1000)
_upload_video_dir = Path(PROJECT_ROOT) / "backend" / "uploads"
_upload_video_dir.mkdir(parents=True, exist_ok=True)


def _latest_uploaded_video_path() -> Optional[str]:
    candidates = [p for p in _upload_video_dir.iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}]
    if not candidates:
        return None
    return str(max(candidates, key=lambda p: p.stat().st_mtime))


_uploaded_video_path = _latest_uploaded_video_path()
if _uploaded_video_path:
    _camera_input_mode = "upload"


def _invalidate_cam_renderers() -> None:
    global _cam_renderers
    for renderer in _cam_renderers.values():
        try:
            close_fn = getattr(renderer, "close", None)
            if callable(close_fn):
                close_fn()
        except Exception:
            pass
    _cam_renderers = {}


def _uploaded_video_exists() -> bool:
    return bool(_uploaded_video_path and os.path.isfile(_uploaded_video_path))


def _camera_source_payload() -> Dict[str, Any]:
    return {
        "mode": _camera_input_mode,
        "has_uploaded_video": _uploaded_video_exists(),
        "uploaded_video_name": os.path.basename(_uploaded_video_path) if _uploaded_video_path else None,
        "uploaded_video_path": _uploaded_video_path,
        "updated_at": _camera_source_updated_at,
    }


def _resolve_camera_source(junction_id: str, direction: str) -> Optional[str]:
    """Resolve camera URL with junction-specific override, then direction default."""
    if _camera_input_mode == "upload" and _uploaded_video_exists():
        return _uploaded_video_path

    j = junction_id.upper().replace("-", "_")
    d = direction.upper()
    return (
        os.getenv(f"TRAFFIC_CAM_URL_{j}_{d}")
        or os.getenv(f"TRAFFIC_CAM_URL_{d}")
        or "0"
    )


def _apply_live_runtime_camera_source(blocking_reopen: bool = True) -> None:
    """Sync LiveRuntime capture source with current UI camera mode.

    This avoids opening the same webcam through multiple independent capture
    objects (a common MSMF failure pattern on Windows).
    """
    lr = globals().get("live_runtime")
    if lr is None or not getattr(lr, "enabled", False):
        return

    target_source = _uploaded_video_path if (_camera_input_mode == "upload" and _uploaded_video_exists()) else "0"
    target_source = str(target_source)
    current_source = str(getattr(lr, "video_source", ""))

    # No switch needed when source is already active and capture is open.
    cap = getattr(lr, "cap", None)
    if current_source == target_source and cap is not None and cap.isOpened():
        return

    try:
        if cap is not None:
            cap.release()
    except Exception:
        pass

    lr.cap = None
    lr.video_source = target_source
    lr._is_file_source = os.path.isfile(target_source)
    lr.frame_ok = False
    lr.consecutive_zero_frames = 0
    if blocking_reopen:
        lr._open_video_source()
    else:
        # Let the runtime tick reopen asynchronously to keep mode-switch APIs responsive.
        lr._last_open_attempt = 0.0


@app.get("/api/live/source")
async def live_source_status():
    return _camera_source_payload()


@app.post("/api/live/source/mode")
async def live_source_mode(req: CameraSourceModeRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    global _camera_input_mode, _camera_source_updated_at
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


@app.post("/api/live/upload-video")
async def live_upload_video(video: UploadFile = File(...), x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    global _uploaded_video_path, _camera_input_mode, _camera_source_updated_at

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


@app.post("/api/live/upload-video/clear")
async def live_clear_uploaded_video(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    global _uploaded_video_path, _camera_input_mode, _camera_source_updated_at

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


def _get_cam_renderer(junction_id: str, direction: str):
    """Return a cached RoadCameraRenderer for the given junction + direction."""
    if RoadCameraRenderer is None:
        return None
    source_url = _resolve_camera_source(junction_id, direction)
    source_str = str(source_url).strip() if source_url is not None else ""
    shared_webcam = bool(source_str.isdigit())
    key = f"cam_src_{source_str}" if shared_webcam else f"{junction_id}_{direction.lower()}"
    if key not in _cam_renderers:
        if not source_url:
            logger.warning(
                "[CamRenderer] Missing camera source for %s (%s). Set TRAFFIC_CAM_URL_%s_%s or TRAFFIC_CAM_URL_%s",
                junction_id,
                direction,
                junction_id.upper().replace("-", "_"),
                direction.upper(),
                direction.upper(),
            )
            return None
        try:
            _cam_renderers[key] = RoadCameraRenderer(
                direction=direction,
                junction_id=junction_id,
                fps=10.0,
                source_url=source_url,
                strict_source=True,
            )
            logger.info("[CamRenderer] Created renderer %s", key)
        except Exception as exc:
            logger.warning("[CamRenderer] Could not create renderer %s: %s", key, exc)
            return None
    renderer = _cam_renderers[key]
    # Keep HUD metadata aligned even when renderer instances are shared per source.
    try:
        renderer.junction_id = junction_id
        renderer.direction = str(direction).upper()
    except Exception:
        pass
    return renderer


def _junction_state_payload(junction_id: str) -> Dict:
    st = _junction_states.get(junction_id, {})
    if not st:
        return {}
    payload = dict(st)
    phase = str(payload.get("phase", "NS_GREEN"))
    camera_direction = "north" if phase == "NS_GREEN" else ("east" if phase == "EW_GREEN" else "north")
    payload["selected"] = junction_id == _selected_junction_id
    payload["camera"] = {
        "junction_id": junction_id,
        "source_mode": _camera_input_mode,
        "source": _camera_source_payload(),
        "direction_hint": camera_direction,
        "stream_url": f"/api/live/camera/{junction_id}/{camera_direction}"
    }
    payload["live_source"] = _camera_source_payload()
    return payload


def _encode_jpeg_frame(frame) -> Optional[bytes]:
    cv2 = _optional_cv2()
    if cv2 is None:
        return None
    try:
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        return buf.tobytes() if ok else None
    except Exception:
        return None


def _demo_placeholder_jpeg(text: str = "Demo feed", junction: str = "J0_0") -> Optional[bytes]:
    cv2 = _optional_cv2()
    if cv2 is None:
        return None
    try:
        frame = np.full((480, 800, 3), (245, 248, 250), dtype=np.uint8)
        accent_seed = sum(ord(ch) for ch in junction)
        accent = ((accent_seed * 37) % 170 + 40, (accent_seed * 17) % 140 + 80, (accent_seed * 29) % 160 + 60)
        road_y = 280
        cv2.rectangle(frame, (0, road_y), (800, 480), (55, 62, 70), -1)
        cv2.line(frame, (0, road_y + 60), (800, road_y + 60), (245, 214, 86), 4)
        cv2.line(frame, (0, road_y + 130), (800, road_y + 130), (255, 255, 255), 3)
        for x in range(40, 800, 120):
            cv2.rectangle(frame, (x, road_y + 20), (x + 60, road_y + 60), accent, -1)
        for x in range(20, 800, 80):
            cv2.line(frame, (x, road_y + 90), (x + 30, road_y + 90), (245, 214, 86), 2)
        pulse_x = 80 + int((time.time() * 90) % 620)
        cv2.circle(frame, (pulse_x, road_y + 45), 18, (38, 166, 154), -1)
        cv2.circle(frame, (pulse_x, road_y + 45), 28, (38, 166, 154), 3)
        cv2.putText(frame, "NEXUS Demo Feed", (28, 72), cv2.FONT_HERSHEY_SIMPLEX, 1.15, (20, 34, 48), 3)
        cv2.putText(frame, text, (28, 122), cv2.FONT_HERSHEY_SIMPLEX, 0.9, accent, 2)
        cv2.putText(frame, f"Junction: {junction}", (28, 162), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (32, 48, 64), 2)
        cv2.putText(frame, time.strftime("%Y-%m-%d %H:%M:%S"), (28, 430), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (60, 72, 84), 2)
        return _encode_jpeg_frame(frame)
    except Exception:
        return None


def _read_demo_video_frame(junction: str = "J0_0") -> Optional[bytes]:
    return _demo_placeholder_jpeg("Synthetic demo frame", junction)


@app.get("/api/live/camera/{junction_id}/{direction}")
async def junction_camera_stream(junction_id: str, direction: str):
    """
    MJPEG stream for a specific junction approach camera.
    direction: north | south | east | west
    """
    ALLOWED_DIRS = {"north", "south", "east", "west"}
    dir_clean = direction.lower().strip()
    if dir_clean not in ALLOWED_DIRS:
        from fastapi import HTTPException
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
                    phase = _junction_states.get(junction_id, {}).get("phase", "NS_GREEN")
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


@app.get("/api/live/camera/{junction_id}/{direction}/snapshot")
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
                phase = _junction_states.get(junction_id, {}).get("phase", "NS_GREEN")
                renderer.set_phase(phase)
                jpeg = _encode_jpeg_frame(frame)
            except Exception as exc:
                logger.warning("[CamRenderer] snapshot render failed for %s (%s): %s", junction_id, dir_clean, exc)

    if not jpeg:
        source_kind = "placeholder"
        jpeg = _demo_placeholder_jpeg("Snapshot fallback", junction_id)
    if not jpeg:
        from fastapi import HTTPException
        raise HTTPException(500, "JPEG encode failed")
    from fastapi.responses import Response
    return Response(content=jpeg, media_type="image/jpeg", headers={"X-Camera-Source": source_kind})


@app.get("/api/snapshot")
async def snapshot():
    if live_runtime.enabled:
        snap = await live_runtime.tick()
        if counterfactual:
            queues = {
                "N": int(snap["queues"].get("north", 0)),
                "S": int(snap["queues"].get("south", 0)),
                "E": int(snap["queues"].get("east", 0)),
                "W": int(snap["queues"].get("west", 0)),
            }
            counterfactual.record_comparison(
                ai_avg_wait=snap["avg_waiting_time"],
                ai_total_queue=int(snap["total_queue"]),
                ai_throughput=int(snap["throughput"]),
                queue_lengths=queues,
            )
        if carbon_engine:
            idle_ai = snap["avg_waiting_time"] / 60.0
            idle_baseline = idle_ai * 1.35
            carbon_engine.record_snapshot(idle_ai, idle_baseline, max(1, int(snap["total_queue"])))
        return snap

    if demo_gen:
        snap = demo_gen.get_snapshot()
        # Feed counterfactual engine
        if counterfactual:
            queues = {
                "N": int(snap["queues"].get("north", 0)),
                "S": int(snap["queues"].get("south", 0)),
                "E": int(snap["queues"].get("east", 0)),
                "W": int(snap["queues"].get("west", 0)),
            }
            counterfactual.record_comparison(
                ai_avg_wait=snap["avg_waiting_time"],
                ai_total_queue=int(snap["total_queue"]),
                ai_throughput=int(snap["throughput"]),
                queue_lengths=queues,
            )
        # Feed carbon engine
        if carbon_engine:
            idle_ai = snap["avg_waiting_time"] / 60.0
            idle_baseline = idle_ai * 1.4
            carbon_engine.record_snapshot(idle_ai, idle_baseline, 100)
        return snap
    return {"error": "No data source available. Connect a live webcam or upload a video."}


@app.get("/api/history")
async def history(n: int = Query(100, ge=1, le=1000)):
    if live_runtime.enabled and live_runtime.latest_traffic:
        return [live_runtime.latest_traffic for _ in range(min(n, 10))]
    if demo_gen:
        gen = DemoDataGenerator(mode="rl")
        return gen.get_history(n)
    return []


@app.get("/api/intersections")
async def intersections():
    _update_junction_telemetry_from_runtime()
    return list(_junction_states.values())


@app.get("/api/junction/{junction_id}/state")
async def junction_state(junction_id: str):
    _update_junction_telemetry_from_runtime()
    if junction_id not in _junction_states:
        return JSONResponse({"error": f"Unknown junction {junction_id}"}, status_code=404)
    return {
        "junction_id": junction_id,
        "selected": junction_id == _selected_junction_id,
        "state": _junction_state_payload(junction_id),
    }


@app.post("/api/junction/select")
async def junction_select(req: JunctionSelectRequest):
    global _selected_junction_id
    jid = req.junction_id
    if jid not in _junction_states:
        return JSONResponse({"error": f"Unknown junction {jid}"}, status_code=404)
    _selected_junction_id = jid
    live_runtime.intersection_id = jid
    _log_event("control", "junction_selected", junction_id=jid)
    _append_audit_event("CONTROL", jid, "junction_select", {"input": _model_to_dict(req), "result": "selected"})
    return {"status": "ok", "selected": jid, "junction": _junction_states[jid], "state": _junction_state_payload(jid)}


@app.post("/api/mode/set")
async def mode_set(req: JunctionModeRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    jid = req.junction_id
    mode = req.mode.strip().lower()
    if jid not in _junction_states:
        return JSONResponse({"error": f"Unknown junction {jid}"}, status_code=404)
    if mode not in ("ai", "manual", "emergency"):
        return JSONResponse({"error": "mode must be ai/manual/emergency"}, status_code=400)

    st = _junction_states[jid]
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


# ---------------------------------------------------------------
# REST Endpoints — Signal Override
# ---------------------------------------------------------------
@app.post("/api/signal/override")
async def signal_override(req: SignalOverrideRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    jid = req.junction_id
    if jid not in _junction_states:
        return JSONResponse({"error": f"Unknown junction {jid}"}, status_code=404)

    # Security check
    if security_detector:
        result = security_detector.validate_command(jid, hash(req.phase) % 8, source=req.source)
        if not result.get("allowed"):
            return JSONResponse({"error": "Security blocked", "details": result}, status_code=403)

    _junction_states[jid]["phase"] = req.phase
    _junction_states[jid]["signal_state"] = req.phase
    _junction_states[jid]["mode"] = "manual"
    _junction_states[jid]["is_overridden"] = True
    _signal_overrides[jid] = {"phase": req.phase, "expires": time.time() + req.duration}
    _apply_phase_to_junction(jid, req.phase, source=req.source, duration_s=req.duration)
    _append_audit_event(
        "CONTROL",
        jid,
        "signal_override",
        {"input": _model_to_dict(req), "result_phase": _junction_states[jid].get("phase")},
    )
    _push_incident("signal_override", jid, "active", f"Signal forced to {req.phase} for {req.duration}s")
    _push_ai_decision(jid, f"override_{req.phase}", 0.98, f"Manual override from {req.source}")

    return {"status": "ok", "junction": jid, "phase": req.phase, "duration": req.duration}


# ---------------------------------------------------------------
# REST Endpoints — Emergency
# ---------------------------------------------------------------
@app.post("/api/emergency/activate")
async def emergency_activate(req: EmergencyActivateRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    if not emergency_engine:
        return JSONResponse({"error": "Emergency module not available"}, status_code=503)

    event = emergency_engine.activate_corridor(
        vehicle_id=req.vehicle_id,
        vehicle_type=req.vehicle_type,
        origin=req.origin,
        destination=req.destination,
    )
    if not event:
        return JSONResponse({"error": "Could not compute corridor path"}, status_code=400)

    # Mark junctions as corridor
    for jid in event.path:
        if jid in _junction_states:
            _junction_states[jid]["is_corridor"] = True
            _junction_states[jid]["mode"] = "emergency"
            _apply_phase_to_junction(jid, "NS_GREEN", source="emergency", duration_s=45)
            _push_ai_decision(jid, "corridor_priority", 0.99, "Emergency vehicle corridor override")

    # Voice announcement
    if voice:
        voice.announce_emergency_corridor(req.vehicle_type, req.origin, req.destination)

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
        "signal_overrides": emergency_engine.get_corridor_signal_overrides(),
    }


@app.get("/api/emergency/active")
async def emergency_active():
    if not emergency_engine:
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
        for e in emergency_engine._active_events.values()
    ]


# ---------------------------------------------------------------
# REST Endpoints — Carbon
# ---------------------------------------------------------------
@app.get("/api/carbon/today")
async def carbon_today():
    if not carbon_engine:
        return JSONResponse({"error": "Carbon module not available"}, status_code=503)
    return carbon_engine.get_today_stats()


@app.get("/api/carbon/certificate")
async def carbon_certificate():
    if not carbon_engine:
        return JSONResponse({"error": "Carbon module not available"}, status_code=503)
    cert_dir = os.path.join(PROJECT_ROOT, "reports")
    os.makedirs(cert_dir, exist_ok=True)
    cert_path = os.path.join(cert_dir, "carbon_certificate.pdf")
    carbon_engine.generate_certificate(output_path=cert_path)
    if os.path.exists(cert_path):
        return FileResponse(cert_path, media_type="application/pdf",
                            filename="nexus_carbon_certificate.pdf")
    return JSONResponse({"error": "Certificate generation failed"}, status_code=500)


@app.get("/api/carbon/history")
async def carbon_history():
    if not carbon_engine:
        return []
    return carbon_engine.get_all_daily_stats()


# ---------------------------------------------------------------
# REST Endpoints — Pedestrian Safety
# ---------------------------------------------------------------
@app.get("/api/pedestrian/analyze")
async def pedestrian_analyze(junction_id: str = "J1_1"):
    if not pedestrian_ai:
        return JSONResponse({"error": "Pedestrian module not available"}, status_code=503)
    result = pedestrian_ai.analyze_frame(frame=None, junction_id=junction_id)
    return result


# ---------------------------------------------------------------
# REST Endpoints — Cybersecurity
# ---------------------------------------------------------------
@app.post("/api/security/validate")
async def security_validate(req: SecurityValidateRequest):
    if not security_detector:
        return JSONResponse({"error": "Security module not available"}, status_code=503)
    return security_detector.validate_command(req.junction_id, req.new_phase, source=req.source)


@app.post("/api/security/simulate")
async def security_simulate(req: SecuritySimulateRequest):
    if not security_detector:
        return JSONResponse({"error": "Security module not available"}, status_code=503)
    return security_detector.simulate_attack(req.attack_type, req.junction_id)


@app.get("/api/security/events")
async def security_events():
    if not security_detector:
        return []
    return security_detector.get_events(limit=50)


# ---------------------------------------------------------------
# REST Endpoints — Road Maintenance
# ---------------------------------------------------------------
@app.get("/api/maintenance/orders")
async def maintenance_orders():
    if not maintenance_ai:
        return []
    return maintenance_ai.get_open_orders()


@app.get("/api/maintenance/geojson")
async def maintenance_geojson():
    orders = maintenance_ai.get_open_orders() if maintenance_ai else []
    features = []
    for idx, order in enumerate(orders):
        lat = float(order.get("lat", 28.6139))
        lon = float(order.get("lon", 77.2090))
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "id": order.get("id", f"road_{idx}"),
                    "severity": order.get("priority", "medium"),
                    "issue": order.get("issue", order.get("type", "road_anomaly")),
                    "junction": order.get("junction_id", "unknown"),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------
# REST Endpoints — NL Command
# ---------------------------------------------------------------
@app.post("/api/nl/command")
async def nl_command(req: NLCommandRequest, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_control_access(x_api_key)
    if not nl_parser:
        return JSONResponse({"error": "NL command module not available"}, status_code=503)
    parsed = nl_parser.parse(req.text)
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
        if parsed.intent == "emergency" and emergency_engine:
            origin = parsed.junctions[0] if parsed.junctions else "J0_0"
            destination = parsed.junctions[1] if len(parsed.junctions) > 1 else "J3_3"
            vtype = parsed.vehicle_type or "ambulance"
            event = emergency_engine.activate_corridor("nl_" + str(int(time.time())), vtype, origin, destination)
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
            if jid in _junction_states:
                _junction_states[jid]["phase"] = phase
                _junction_states[jid]["is_overridden"] = True
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


# ---------------------------------------------------------------
# REST Endpoints — Counterfactual
# ---------------------------------------------------------------
@app.get("/api/counterfactual")
async def counterfactual_comparison():
    if not counterfactual:
        return JSONResponse({"error": "Counterfactual module not available"}, status_code=503)
    return counterfactual.get_comparison()


# ---------------------------------------------------------------
# REST Endpoints — Voice Broadcast
# ---------------------------------------------------------------
@app.post("/api/voice/announce")
async def voice_announce(req: VoiceAnnounceRequest):
    if not voice:
        return JSONResponse({"error": "Voice module not available"}, status_code=503)
    path = voice.announce(req.message, language=req.language, play=req.play)
    return {"status": "ok", "audio_file": path}


@app.get("/api/voice/log")
async def voice_log(limit: int = 20):
    if not voice:
        return []
    return voice.get_broadcast_log(limit=limit)


# ---------------------------------------------------------------
# REST Endpoints — Aggregated Metrics
# ---------------------------------------------------------------
@app.get("/api/metrics/overview")
async def metrics_overview():
    if live_runtime.enabled and live_runtime.latest_traffic:
        snapshot_data = live_runtime.latest_traffic
    else:
        snapshot_data = demo_gen.get_snapshot() if demo_gen else {}

    overview = {
        "traffic": {
            "total_queue": snapshot_data.get("total_queue", 0),
            "avg_waiting_time": snapshot_data.get("avg_waiting_time", 0),
            "throughput": snapshot_data.get("throughput", 0),
            "phase": snapshot_data.get("phase", "unknown"),
        },
        "carbon": carbon_engine.get_today_stats() if carbon_engine else {},
        "counterfactual": counterfactual.get_comparison() if counterfactual else {},
        "emergency_active": len(emergency_engine._active_events) if emergency_engine else 0,
        "security_events_24h": len(security_detector.get_events()) if security_detector else 0,
        "maintenance_orders": len(maintenance_ai.get_open_orders()) if maintenance_ai else 0,
        "voice_broadcasts": voice.get_stats() if voice else {},
        "ws_clients": ws_manager.count,
    }
    return overview


# ---------------------------------------------------------------
# REST Endpoints — AI / ML Analytics
# ---------------------------------------------------------------
MLAnomalyDetector = _safe_import("ai.anomaly.ml_anomaly_detector", "MLAnomalyDetector")
TrafficXAI = _safe_import("ai.explainability.explainer", "TrafficXAI")

_ml_anomaly = None
_xai_engine = None

@app.get("/api/ai/status")
async def ai_status():
    """AI/ML model availability and status."""
    models = {
        "dqn_agent": os.path.isfile(AI_STATUS_DQN_MODEL_PATH),
        "lstm_predictor": os.path.isfile(AI_STATUS_LSTM_MODEL_PATH),
        "ml_anomaly_iforest": os.path.isfile(os.path.join(ANOMALY_MODEL_DIR, "iforest.pkl")),
        "ml_anomaly_autoencoder": os.path.isfile(os.path.join(ANOMALY_MODEL_DIR, "autoencoder.pt")),
    }
    return {
        "models": models,
        "trained_count": sum(models.values()),
        "total_count": len(models),
        "gpu_available": _check_gpu(),
    }

@app.get("/api/ai/lstm/results")
async def ai_lstm_results():
    """Get LSTM training results if available."""
    results = _load_json_safe("results/lstm/lstm_training_results.json")
    if not results:
        return {"status": "not_trained", "message": "Run: python scripts/train_lstm.py"}
    return results

@app.get("/api/ai/anomaly/results")
async def ai_anomaly_results():
    """Get ML anomaly detection results."""
    results = _load_json_safe("results/anomaly/anomaly_detection_results.json")
    if not results:
        return {"status": "not_evaluated", "message": "Run: python -m ai.anomaly.ml_anomaly_detector --generate"}
    return results

@app.get("/api/ai/xai/importance")
async def ai_xai_importance():
    """Get feature importance analysis."""
    results = _load_json_safe("results/xai/xai_report.json")
    if not results:
        return {"status": "not_computed", "message": "Run: python -m ai.explainability.explainer --model <path>"}
    return results

@app.get("/api/ai/comparison")
async def ai_agent_comparison():
    """Get agent comparison results (DQN vs PPO vs A2C)."""
    results = _load_json_safe("results/comparison/comparison_results.json")
    if not results:
        return {"status": "not_run", "message": "Run: python scripts/compare_agents.py"}
    return results

@app.get("/api/ai/explain")
async def ai_explain_decision(
    queue_n: float = Query(0.5), queue_s: float = Query(0.3),
    queue_e: float = Query(0.4), queue_w: float = Query(0.2),
    wait_n: float = Query(0.3), wait_s: float = Query(0.2),
    wait_e: float = Query(0.4), wait_w: float = Query(0.1),
):
    """Get AI explanation for a signal decision given current state."""
    global _xai_engine
    if _xai_engine is None and TrafficXAI:
        model_path = AI_EXPLAIN_MODEL_PATH
        _xai_engine = TrafficXAI(model_path=model_path if os.path.isfile(model_path) else None)

    obs = np.array([queue_n, queue_s, queue_e, queue_w,
                     wait_n, wait_s, wait_e, wait_w,
                     1, 0, 0, 0, 0.5], dtype=np.float32)

    if _xai_engine:
        explanation = _xai_engine.explain_decision(obs, action=1)
        return explanation
    return {"error": "XAI engine not available"}

@app.get("/api/ai/training-history")
async def ai_training_history():
    """Return LSTM loss curves for frontend charting."""
    lstm = _load_json_safe("results/lstm/lstm_training_results.json")
    if lstm and "history" in lstm:
        return {"history": lstm["history"], "epochs": lstm.get("epochs_trained", 0)}
    return {"history": {}, "epochs": 0}


def _check_gpu() -> dict:
    try:
        torch = _optional_torch()
        if torch is None:
            return {"available": False}
        if torch.cuda.is_available():
            return {"available": True, "name": torch.cuda.get_device_name(0),
                    "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)}
    except Exception:
        pass
    return {"available": False}


def _load_json_safe(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


# ---------------------------------------------------------------
# WebSocket — Real-Time Stream
# ---------------------------------------------------------------
@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """Stream live data at sub-second cadence to connected clients."""
    global _last_ws_tx_ms
    await ws_manager.connect(ws)
    ws_interval_s = max(0.2, min(0.5, float(os.getenv("WS_UPDATE_INTERVAL", "0.3"))))
    try:
        while True:
            tick_t0 = time.perf_counter()
            global _last_traffic_snapshot
            if live_runtime.enabled:
                traffic = await live_runtime.tick()
            elif demo_gen:
                traffic = demo_gen.get_snapshot()
            else:
                traffic = {}
            if isinstance(traffic, dict) and traffic:
                _last_traffic_snapshot = traffic
            cv_processing_ms = (time.perf_counter() - tick_t0) * 1000.0

            _update_junction_telemetry_from_runtime()

            rl_actions: Dict[str, int] = {}
            if _rl_engine_info.get("enabled", False):
                rl_actions = _predict_rl_actions()

            # Apply per-junction mode logic and AI explainability.
            for jid, st in _junction_states.items():
                lane_dist = st.get("lane_distribution", {"north": 0, "south": 0, "east": 0, "west": 0})
                mode = st.get("mode", "ai")
                if mode == "manual":
                    # Manual mode keeps currently set manual phase.
                    st["ai_reason"] = "Manual override active by authority"
                elif mode == "emergency":
                    _apply_phase_to_junction(jid, "NS_GREEN", source="emergency", duration_s=max(10, st.get("phase_remaining", 20)))
                    st["ai_reason"] = "Emergency corridor active"
                else:
                    n = int(lane_dist.get("north", 0))
                    s = int(lane_dist.get("south", 0))
                    e = int(lane_dist.get("east", 0))
                    w = int(lane_dist.get("west", 0))
                    ns = n + s
                    ew = e + w
                    decision_source = "heuristic"
                    phase = "NS_GREEN" if ns >= ew else "EW_GREEN"
                    action = 0 if phase == "NS_GREEN" else 1
                    if jid in rl_actions:
                        rl_action = int(rl_actions[jid])
                        phase = _decision_action_to_phase(rl_action)
                        action = 0 if phase == "NS_GREEN" else 1
                        decision_source = "rl"
                    _apply_phase_to_junction(jid, phase, source="ai", duration_s=max(8, st.get("phase_remaining", 20)))
                    density = float(st.get("density", 0.0))
                    lane_pick = "north/south" if phase == "NS_GREEN" else "east/west"
                    st["rl_action"] = action
                    st["decision_source"] = decision_source
                    if decision_source == "rl":
                        st["ai_confidence"] = 0.9
                        st["ai_reason"] = (
                            f"RL policy selected {lane_pick} "
                            f"(density={density:.2f}, ns={ns}, ew={ew})"
                        )
                    else:
                        st["ai_confidence"] = round(max(0.5, min(0.99, 0.62 + abs(ns - ew) / max(1, ns + ew))), 2)
                        st["ai_reason"] = (
                            f"Heuristic selected {lane_pick} due to highest congestion "
                            f"(density={density:.2f}, ns={ns}, ew={ew})"
                        )
                    if live_runtime._tick % 4 == 0:
                        _push_ai_decision(
                            jid,
                            f"switch_{phase}",
                            st.get("ai_confidence", 0.9),
                            st["ai_reason"],
                        )

            if traffic:
                ai_wait = float(traffic.get("avg_waiting_time", 0.0))
                queue_len = float(traffic.get("total_queue", 0.0))
                vehicle_count = max(1.0, float((_junction_states.get(_selected_junction_id, {}) or {}).get("vehicle_count", 1)))
                baseline_wait = ai_wait + (0.8 * queue_len) + (0.5 * vehicle_count)
                ai_idle = ai_wait * 0.58
                baseline_idle = baseline_wait * 0.64
                saved_vehicle_minutes = max(0.0, (baseline_wait - ai_wait) * vehicle_count / 60.0)
                emission_factor = 0.00062
                emissions_saved = max(0.0, (baseline_idle - ai_idle) * emission_factor)

                _session_metrics["samples"] += 1
                _session_metrics["ai_wait_sum"] += ai_wait
                _session_metrics["baseline_wait_sum"] += baseline_wait
                _session_metrics["ai_idle_sum"] += ai_idle
                _session_metrics["baseline_idle_sum"] += baseline_idle
                _session_metrics["queue_sum"] += queue_len
                _session_metrics["saved_vehicle_minutes"] += saved_vehicle_minutes
                _session_metrics["emissions_saved_kg"] += emissions_saved

            if counterfactual and traffic:
                queues = {
                    "N": int(traffic.get("queues", {}).get("north", 0)),
                    "S": int(traffic.get("queues", {}).get("south", 0)),
                    "E": int(traffic.get("queues", {}).get("east", 0)),
                    "W": int(traffic.get("queues", {}).get("west", 0)),
                }
                counterfactual.record_comparison(
                    ai_avg_wait=traffic.get("avg_waiting_time", 0.0),
                    ai_total_queue=int(traffic.get("total_queue", 0)),
                    ai_throughput=int(traffic.get("throughput", 0)),
                    queue_lengths=queues,
                )
            if carbon_engine and traffic:
                idle_ai = float(traffic.get("avg_waiting_time", 0.0)) / 60.0
                carbon_engine.record_snapshot(
                    idle_ai,
                    idle_ai * 1.35,
                    max(1, int(traffic.get("total_queue", 1))),
                )

            frame_ctx = _next_frame_context()
            frame_id = frame_ctx["frame_id"]
            tick_timestamp = frame_ctx["tick_timestamp"]
            ts = round(tick_timestamp / 1000.0, 3)
            runtime_status = live_runtime.status()
            emergency_state = _build_emergency_state()
            event_state = _build_incidents_payload()
            maintenance_orders = maintenance_ai.get_open_orders() if maintenance_ai else []
            perf = _session_metrics_payload()
            threat_state = _build_security_payload()

            junction_dict = {}
            for st in _junction_states.values():
                junction_dict[st["junction_id"]] = {
                    "vehicle_count": st.get("vehicle_count", 0),
                    "queue_length": st.get("queue_length", st.get("vehicle_count", 0)),
                    "avg_waiting_time": st.get("avg_waiting_time", st.get("wait_time", 0.0)),
                    "congestion": st.get("congestion_level", "low"),
                    "signal": st.get("signal_state", st.get("phase", "NS_GREEN")),
                    "mode": st.get("mode", "ai"),
                    "lanes": st.get("lane_distribution", {"north": 0, "south": 0, "east": 0, "west": 0}),
                    "density": st.get("density", 0.0),
                    "active_lane": st.get("active_lane", "north_south"),
                    "camera_direction": st.get("camera_direction", "north"),
                    "phase_remaining": st.get("phase_remaining", 0),
                    "ai_reason": st.get("ai_reason", ""),
                    "ai_confidence": st.get("ai_confidence", 0.0),
                    "decision_source": st.get("decision_source", "heuristic"),
                }

            selected_mode = _junction_states.get(_selected_junction_id, {}).get("mode", "ai")
            degraded_reason = ""
            if bool((live_runtime.latest_cv_summary or {}).get("degraded", False)):
                degraded_reason = "CV degraded: low-confidence or missing frames"
            if bool((live_runtime.latest_cv_summary or {}).get("fallback_active", False)):
                degraded_reason = "Fallback traffic injection active"

            selected_junction_state = junction_dict.get(_selected_junction_id, {})
            selected_vehicle_count = int(selected_junction_state.get("vehicle_count", 0))
            fallback_active = bool((live_runtime.latest_cv_summary or {}).get("fallback_active", False))
            camera_source = "live" if live_runtime.enabled else "unavailable"
            pipeline_guard_status = "ok"
            pipeline_guard_message = ""
            if selected_vehicle_count == 0 and not fallback_active:
                pipeline_guard_status = "failure"
                pipeline_guard_message = "DATA PIPELINE FAILURE"

            system_state = {
                "frame_id": frame_id,
                "tick_timestamp": tick_timestamp,
                "junctions": junction_dict,
                "selected_junction": _selected_junction_id,
                "session_metrics": {
                    "avg_wait_ai": perf.get("avg_wait_ai_s", 0.0),
                    "avg_wait_baseline": perf.get("avg_wait_baseline_s", 0.0),
                    "idle_time_saved": round(max(0.0, perf.get("avg_idle_baseline_s", 0.0) - perf.get("avg_idle_ai_s", 0.0)), 2),
                    "queue_length": perf.get("avg_queue_length", 0.0),
                    "vehicle_minutes_saved": perf.get("saved_vehicle_minutes", 0.0),
                    "improvement_pct": perf.get("improvement_pct", 0.0),
                },
                "ai_decisions": list(_ai_decision_feed),
                "emergency": {
                    "active": emergency_state.get("active", False),
                    "corridor": emergency_state.get("route", []),
                    "current_step": emergency_state.get("current_leg_index", 0),
                    "eta": emergency_state.get("eta_seconds", 0.0),
                    "progress": emergency_state.get("progress_pct", 0.0),
                    "corridor_id": emergency_state.get("corridor_id"),
                    "completed_events": emergency_state.get("completed_events", []),
                    "response_improvement_pct": emergency_state.get("response_improvement_pct", 0.0),
                },
                "anomalies": event_state.get("anomalies", []),
                "incidents": event_state.get("incidents", []),
                "esg": {
                    "emissions_saved": perf.get("emissions_saved_kg", 0.0),
                    "idle_time_saved": round(max(0.0, perf.get("avg_idle_baseline_s", 0.0) - perf.get("avg_idle_ai_s", 0.0)), 2),
                    "daily": carbon_engine.get_today_stats() if carbon_engine else {},
                },
                "maintenance": {
                    "potholes": sum(1 for o in maintenance_orders if "pothole" in str(o.get("issue", "")).lower()),
                    "flagged_roads": maintenance_orders,
                },
                "cybersecurity": {
                    "alerts": threat_state.get("alerts", []),
                    "threat_level": threat_state.get("integrity", "ok"),
                    "api_misuse_score": threat_state.get("api_misuse_score", 0.0),
                },
                "health": {
                    "fps": runtime_status.get("fps", 0.0),
                    "latency": runtime_status.get("latency_ms", {}),
                    "latency_breakdown": {
                        "cv_processing_ms": round(cv_processing_ms, 2),
                        "backend_processing_ms": 0.0,
                        "ws_transmission_ms": round(float(_last_ws_tx_ms), 2),
                        "frontend_render_ms": None,
                    },
                    "frame_drop_rate": runtime_status.get("frame_drop_rate", 0.0),
                    "detection_count": (
                        int(selected_junction_state.get("vehicle_count", 0))
                        if not live_runtime.enabled
                        else (live_runtime.latest_cv_summary or {}).get("vehicle_count", 0)
                    ),
                    "system_mode": selected_mode,
                    "degraded_reason": degraded_reason,
                    "fallback_active": fallback_active,
                    "camera_source": camera_source,
                    "decision_engine": dict(_rl_engine_info),
                    "decision_source": selected_junction_state.get("decision_source", "heuristic"),
                    "cv_degraded": bool((live_runtime.latest_cv_summary or {}).get("degraded", False)),
                    "pipeline_guard": {
                        "status": pipeline_guard_status,
                        "message": pipeline_guard_message,
                    },
                },
                "map": live_runtime.map_payload(),
                "traffic": traffic,
            }

            backend_processing_ms = (time.perf_counter() - tick_t0) * 1000.0 - cv_processing_ms
            system_state["health"]["latency_breakdown"]["backend_processing_ms"] = round(max(0.0, backend_processing_ms), 2)

            contract_errors = _validate_system_state_contract(system_state)
            if contract_errors:
                _log_event("contract", "system_state_invalid", frame_id=frame_id, errors=contract_errors)
                _append_audit_event(
                    "CONTROL",
                    "system",
                    "schema_validation_failed",
                    {"frame_id": frame_id, "errors": contract_errors},
                )
                await asyncio.sleep(ws_interval_s)
                continue

            consistency = _consistency_warnings(system_state)
            if consistency:
                _log_event("consistency", "cross_module_warning", frame_id=frame_id, warnings=consistency)
                _append_audit_event(
                    "CONTROL",
                    _selected_junction_id,
                    "consistency_warning",
                    {"frame_id": frame_id, "warnings": consistency},
                )

            _store_replay_state(system_state)

            payload = {
                "timestamp": ts,
                "frame_id": frame_id,
                "tick_timestamp": tick_timestamp,
                "system_state": system_state,
            }
            if counterfactual:
                payload["counterfactual"] = counterfactual.get_comparison()
            if carbon_engine:
                payload["carbon"] = carbon_engine.get_today_stats()
            if live_runtime.latest_prediction:
                payload["prediction"] = live_runtime.latest_prediction

            send_t0 = time.perf_counter()
            await ws.send_json(payload)
            ws_send_ms = (time.perf_counter() - send_t0) * 1000.0
            _last_ws_tx_ms = ws_send_ms
            live_runtime.note_ws_delay(ws_send_ms)
            await asyncio.sleep(ws_interval_s)
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception as exc:
        logger.warning("[WS] live stream closed due to error: %s", exc)
        ws_manager.disconnect(ws)


# Keep old /ws endpoint for backward compatibility
@app.websocket("/ws")
async def websocket_legacy(ws: WebSocket):
    await ws.accept()
    gen = DemoDataGenerator(mode="rl") if DEMO_MODE else None
    try:
        while True:
            if live_runtime.enabled:
                await ws.send_json(await live_runtime.tick())
            elif gen:
                await ws.send_json(gen.get_snapshot())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass


# ---------------------------------------------------------------
# Background: Expire signal overrides
# ---------------------------------------------------------------
async def _override_expiry_loop():
    while True:
        now = time.time()
        expired = [jid for jid, info in _signal_overrides.items() if info["expires"] < now]
        for jid in expired:
            del _signal_overrides[jid]
            if jid in _junction_states:
                _junction_states[jid]["is_overridden"] = False
                if _junction_states[jid].get("mode") == "manual":
                    _junction_states[jid]["mode"] = "ai"
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup():
    try:
        _init_module_singletons()
        _init_decision_engine()

        if (
            live_runtime.enabled
            and LIVE_MODE
            and not DEMO_MODE
            and live_runtime.startup_validation_error
        ):
            logger.error("[Startup] Live validation issue: %s", live_runtime.startup_validation_error)
            live_runtime._activate_demo_fallback(live_runtime.startup_validation_error)

        # Keep startup minimal in demo/cloud deployments.
        if (not _IS_RAILWAY) and (not DEMO_MODE):
            asyncio.create_task(_override_expiry_loop())
        else:
            logger.info("[Startup] Lightweight mode: skipping override expiry background loop")

        mode_label = "DEMO" if DEMO_MODE else "LIVE"
        logger.info("[Startup] Running in %s MODE", mode_label)
        logger.info("[Startup] Modules loaded: %d/8", 8 - len(_import_errors))
        logger.info("[Startup] Fallback triggered: %s", live_runtime.fallback_triggered)
        if live_runtime.fallback_triggered:
            logger.warning("[Startup] Fallback reason: %s", live_runtime.fallback_reason)
        logger.info("[Startup] Live runtime status: %s", live_runtime.status())
        logger.info("[Startup] Server running at http://127.0.0.1:%s", os.getenv("PORT", "8080"))
    except Exception as exc:
        logger.exception("[Startup] Non-fatal startup error: %s", exc)
        try:
            live_runtime._activate_demo_fallback(f"startup exception: {exc}")
        except Exception:
            logger.exception("[Startup] Failed to activate fallback mode")


# ---------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("  NEXUS-ATMS  —  Intelligent Traffic Management Backend")
    print("=" * 60)
    print(f"  Demo Mode : {DEMO_MODE}")
    print(f"  Modules   : {8 - len(_import_errors)}/8 loaded")
    if _import_errors:
        for mod, err in _import_errors.items():
            print(f"    [WARN] {mod}: {err}")
    port = int(os.getenv("PORT", 8080))
    print(f"  Dashboard : http://localhost:{port}")
    print(f"  API Docs  : http://localhost:{port}/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)), log_level="info")
