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
from backend.core.schemas import *

# Add project root to path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from backend.demo_data import DemoDataGenerator
from backend.core.utils import _safe_import, _optional_cv2, _optional_torch, _check_gpu, _load_json_safe
from backend.core.logging import _log_event, _append_audit_event, _consistency_warnings

from backend.core.config import _IS_RAILWAY, _demo_mode_env, _BOOT_DEMO_MODE, _import_errors


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

from backend.core.config import ANOMALY_MODEL_DIR, AI_STATUS_DQN_MODEL_PATH, AI_STATUS_LSTM_MODEL_PATH, AI_EXPLAIN_MODEL_PATH

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )


def _model_to_dict(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


# ---------------------------------------------------------------
# App Initialisation
# ---------------------------------------------------------------
app = FastAPI(title="NEXUS-ATMS Dashboard", version="2.0.0")
from backend.core.config import HARDENED_MODE, CONTROL_API_KEY
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
# ---------------------------------------------------------------
# WebSocket Manager
# ---------------------------------------------------------------
import backend.dependencies as deps
from backend.services.video_service import *
from backend.services.traffic_service import _congestion_from_density, _phase_from_lane, _active_lane_from_phase, _camera_direction_from_phase, _normalize_phase_name, _lane_distribution_from_snapshot, _apply_traffic_snapshot_to_junctions, _apply_phase_to_junction, _refresh_phase_countdowns, LiveRuntime

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
    deps._frame_seq += 1
    deps._last_tick_ms = int(time.time() * 1000)
    return {"frame_id": deps._frame_seq, "tick_timestamp": deps._last_tick_ms}


def _current_frame_context() -> Dict[str, int]:
    return {"frame_id": max(1, deps._frame_seq), "tick_timestamp": deps._last_tick_ms}


def _store_replay_state(system_state: Dict[str, Any]) -> None:
    deps._state_replay_buffer.append(
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


def _push_ai_decision(jid: str, action: str, confidence: float, reason: str) -> None:
    ctx = _current_frame_context()
    deps._ai_decision_feed.appendleft(
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
    deps._incident_log.appendleft(
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
    samples = max(1, int(deps._session_metrics.get("samples", 0)))
    ai_wait = deps._session_metrics["ai_wait_sum"] / samples
    baseline_wait = deps._session_metrics["baseline_wait_sum"] / samples
    ai_idle = deps._session_metrics["ai_idle_sum"] / samples
    baseline_idle = deps._session_metrics["baseline_idle_sum"] / samples
    queue_len = deps._session_metrics["queue_sum"] / samples
    improvement = 0.0
    if baseline_wait > 0:
        improvement = ((baseline_wait - ai_wait) / baseline_wait) * 100.0
    return {
        "samples": int(deps._session_metrics["samples"]),
        "session_minutes": round((time.time() - deps._session_started_at) / 60.0, 2),
        "avg_wait_ai_s": round(ai_wait, 2),
        "avg_wait_baseline_s": round(baseline_wait, 2),
        "avg_idle_ai_s": round(ai_idle, 2),
        "avg_idle_baseline_s": round(baseline_idle, 2),
        "avg_queue_length": round(queue_len, 2),
        "improvement_pct": round(improvement, 2),
        "saved_vehicle_minutes": round(deps._session_metrics["saved_vehicle_minutes"], 2),
        "emissions_saved_kg": round(deps._session_metrics["emissions_saved_kg"], 3),
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
        "completed_events": list(deps._completed_emergency_events),
    }
    if not emergency_engine:
        return state

    active_events = list(emergency_engine._active_events.values())
    active_ids = set(e.event_id for e in active_events)
    for stale_id in deps._active_emergency_ids - active_ids:
        deps._completed_emergency_events.appendleft(
            {
                "event_id": stale_id,
                "completed_at": round(time.time(), 3),
            }
        )
    deps._active_emergency_ids.clear()
    deps._active_emergency_ids.update(active_ids)

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
    events: List[Dict] = list(deps._incident_log)
    anomalies: List[Dict] = []
    ctx = _current_frame_context()
    now = round(time.time(), 3)

    if live_runtime.latest_incidents:
        for idx, inc in enumerate(live_runtime.latest_incidents[:8]):
            events.append(
                {
                    "id": f"cv_inc_{idx}_{int(now)}",
                    "type": str(inc.get("type", "incident")),
                    "location": str(inc.get("junction_id", deps._selected_junction_id)),
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
                "junction": deps._selected_junction_id,
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


def _update_junction_telemetry_from_runtime() -> None:
    if not live_runtime.enabled:
        traffic = deps._last_traffic_snapshot
        if (not traffic) and demo_gen:
            traffic = demo_gen.get_snapshot()
            deps._last_traffic_snapshot = traffic
        _apply_traffic_snapshot_to_junctions(traffic)
        return

    base_cv = live_runtime.latest_cv_summary or {}
    base_count = int(base_cv.get("vehicle_count", 0))
    base_density = float(base_cv.get("density", 0.0))
    base_cong = str(base_cv.get("congestion_level", _congestion_from_density(base_density)))
    per_lane = dict(base_cv.get("per_lane", {"north": 0, "south": 0, "east": 0, "west": 0}))
    health = live_runtime.health
    runtime = live_runtime.status()

    if deps._selected_junction_id in deps._junction_states:
        st = deps._junction_states[deps._selected_junction_id]
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
    for jid, st in deps._junction_states.items():
        if jid == deps._selected_junction_id:
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


def _init_junctions():
    """Initialize 4x4 grid junction states."""
    for r in range(4):
        for c in range(4):
            jid = f"J{r}_{c}"
            deps._junction_states[jid] = {
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
        jids = sorted(deps._junction_states.keys())
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
    for jid, st in deps._junction_states.items():
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
from backend.api.health import router as health_router
app.include_router(health_router)
from backend.api.traffic import router as traffic_router
app.include_router(traffic_router)
from backend.api.signals import router as signals_router
app.include_router(signals_router)
from backend.api.emergency import router as emergency_router
app.include_router(emergency_router)
from backend.api.analytics import router as analytics_router
app.include_router(analytics_router)
from backend.api.maintenance import router as maintenance_router
app.include_router(maintenance_router)
from backend.api.websockets import router as websockets_router
app.include_router(websockets_router)


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


# ---------------------------------------------------------------
# REST Endpoints — AI / ML Analytics
# ---------------------------------------------------------------
MLAnomalyDetector = _safe_import("ai.anomaly.ml_anomaly_detector", "MLAnomalyDetector")
TrafficXAI = _safe_import("ai.explainability.explainer", "TrafficXAI")

_ml_anomaly = None
_xai_engine = None

# ---------------------------------------------------------------
# Background: Expire signal overrides
# ---------------------------------------------------------------
async def _override_expiry_loop():
    while True:
        now = time.time()
        expired = [jid for jid, info in deps._signal_overrides.items() if info["expires"] < now]
        for jid in expired:
            del deps._signal_overrides[jid]
            if jid in deps._junction_states:
                deps._junction_states[jid]["is_overridden"] = False
                if deps._junction_states[jid].get("mode") == "manual":
                    deps._junction_states[jid]["mode"] = "ai"
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
