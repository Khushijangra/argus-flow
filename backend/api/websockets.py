from typing import Optional, List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect, Header, Query, APIRouter, Request, HTTPException
import backend.dependencies as deps
from backend.services.traffic_service import live_runtime
from backend.core.config import *
from backend.core.utils import *
router = APIRouter(tags=['Websockets'])

# ---------------------------------------------------------------
# WebSocket — Real-Time Stream
# ---------------------------------------------------------------
@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """Stream live data at sub-second cadence to connected clients."""
    await deps.ws_manager.connect(ws)
    ws_interval_s = max(0.2, min(0.5, float(os.getenv("WS_UPDATE_INTERVAL", "0.3"))))
    try:
        while True:
            tick_t0 = time.perf_counter()
            if live_runtime.enabled:
                traffic = await live_runtime.tick()
            elif deps.demo_gen:
                traffic = deps.demo_gen.get_snapshot()
            else:
                traffic = {}
            if isinstance(traffic, dict) and traffic:
                deps._last_traffic_snapshot = traffic
            cv_processing_ms = (time.perf_counter() - tick_t0) * 1000.0

            _update_junction_telemetry_from_runtime()

            rl_actions: Dict[str, int] = {}
            if _rl_engine_info.get("enabled", False):
                rl_actions = _predict_rl_actions()

            # Apply per-junction mode logic and AI explainability.
            for jid, st in deps._junction_states.items():
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
                vehicle_count = max(1.0, float((deps._junction_states.get(deps._selected_junction_id, {}) or {}).get("vehicle_count", 1)))
                baseline_wait = ai_wait + (0.8 * queue_len) + (0.5 * vehicle_count)
                ai_idle = ai_wait * 0.58
                baseline_idle = baseline_wait * 0.64
                saved_vehicle_minutes = max(0.0, (baseline_wait - ai_wait) * vehicle_count / 60.0)
                emission_factor = 0.00062
                emissions_saved = max(0.0, (baseline_idle - ai_idle) * emission_factor)

                deps._session_metrics["samples"] += 1
                deps._session_metrics["ai_wait_sum"] += ai_wait
                deps._session_metrics["baseline_wait_sum"] += baseline_wait
                deps._session_metrics["ai_idle_sum"] += ai_idle
                deps._session_metrics["baseline_idle_sum"] += baseline_idle
                deps._session_metrics["queue_sum"] += queue_len
                deps._session_metrics["saved_vehicle_minutes"] += saved_vehicle_minutes
                deps._session_metrics["emissions_saved_kg"] += emissions_saved

            if deps.counterfactual and traffic:
                queues = {
                    "N": int(traffic.get("queues", {}).get("north", 0)),
                    "S": int(traffic.get("queues", {}).get("south", 0)),
                    "E": int(traffic.get("queues", {}).get("east", 0)),
                    "W": int(traffic.get("queues", {}).get("west", 0)),
                }
                deps.counterfactual.record_comparison(
                    ai_avg_wait=traffic.get("avg_waiting_time", 0.0),
                    ai_total_queue=int(traffic.get("total_queue", 0)),
                    ai_throughput=int(traffic.get("throughput", 0)),
                    queue_lengths=queues,
                )
            if deps.carbon_engine and traffic:
                idle_ai = float(traffic.get("avg_waiting_time", 0.0)) / 60.0
                deps.carbon_engine.record_snapshot(
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
            maintenance_orders = deps.maintenance_ai.get_open_orders() if deps.maintenance_ai else []
            perf = _session_metrics_payload()
            threat_state = _build_security_payload()

            junction_dict = {}
            for st in deps._junction_states.values():
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

            selected_mode = deps._junction_states.get(deps._selected_junction_id, {}).get("mode", "ai")
            degraded_reason = ""
            if bool((live_runtime.latest_cv_summary or {}).get("degraded", False)):
                degraded_reason = "CV degraded: low-confidence or missing frames"
            if bool((live_runtime.latest_cv_summary or {}).get("fallback_active", False)):
                degraded_reason = "Fallback traffic injection active"

            selected_junction_state = junction_dict.get(deps._selected_junction_id, {})
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
                "selected_junction": deps._selected_junction_id,
                "session_metrics": {
                    "avg_wait_ai": perf.get("avg_wait_ai_s", 0.0),
                    "avg_wait_baseline": perf.get("avg_wait_baseline_s", 0.0),
                    "idle_time_saved": round(max(0.0, perf.get("avg_idle_baseline_s", 0.0) - perf.get("avg_idle_ai_s", 0.0)), 2),
                    "queue_length": perf.get("avg_queue_length", 0.0),
                    "vehicle_minutes_saved": perf.get("saved_vehicle_minutes", 0.0),
                    "improvement_pct": perf.get("improvement_pct", 0.0),
                },
                "ai_decisions": list(deps._ai_decision_feed),
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
                    "daily": deps.carbon_engine.get_today_stats() if deps.carbon_engine else {},
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
                        "ws_transmission_ms": round(float(deps._last_ws_tx_ms), 2),
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
                    deps._selected_junction_id,
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
            if deps.counterfactual:
                payload["deps.counterfactual"] = deps.counterfactual.get_comparison()
            if deps.carbon_engine:
                payload["carbon"] = deps.carbon_engine.get_today_stats()
            if live_runtime.latest_prediction:
                payload["prediction"] = live_runtime.latest_prediction

            send_t0 = time.perf_counter()
            await ws.send_json(payload)
            ws_send_ms = (time.perf_counter() - send_t0) * 1000.0
            deps._last_ws_tx_ms = ws_send_ms
            live_runtime.note_ws_delay(ws_send_ms)
            await asyncio.sleep(ws_interval_s)
    except WebSocketDisconnect:
        deps.ws_manager.disconnect(ws)
    except Exception as exc:
        logger.warning("[WS] live stream closed due to error: %s", exc)
        deps.ws_manager.disconnect(ws)



# Keep old /ws endpoint for backward compatibility
@router.websocket("/ws")
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



