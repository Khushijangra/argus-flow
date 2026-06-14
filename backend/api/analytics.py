from fastapi import APIRouter, Request, HTTPException
import backend.dependencies as deps
from backend.core.config import *
from backend.core.utils import *
router = APIRouter(tags=['Analytics'])

# ---------------------------------------------------------------
# REST Endpoints — Carbon
# ---------------------------------------------------------------
@router.get("/api/carbon/today")
async def carbon_today():
    if not carbon_engine:
        return JSONResponse({"error": "Carbon module not available"}, status_code=503)
    return carbon_engine.get_today_stats()



@router.get("/api/carbon/certificate")
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



@router.get("/api/carbon/history")
async def carbon_history():
    if not carbon_engine:
        return []
    return carbon_engine.get_all_daily_stats()



# ---------------------------------------------------------------
# REST Endpoints — Pedestrian Safety
# ---------------------------------------------------------------
@router.get("/api/pedestrian/analyze")
async def pedestrian_analyze(junction_id: str = "J1_1"):
    if not pedestrian_ai:
        return JSONResponse({"error": "Pedestrian module not available"}, status_code=503)
    result = pedestrian_ai.analyze_frame(frame=None, junction_id=junction_id)
    return result



# ---------------------------------------------------------------
# REST Endpoints — Counterfactual
# ---------------------------------------------------------------
@router.get("/api/counterfactual")
async def counterfactual_comparison():
    if not counterfactual:
        return JSONResponse({"error": "Counterfactual module not available"}, status_code=503)
    return counterfactual.get_comparison()



# ---------------------------------------------------------------
# REST Endpoints — Voice Broadcast
# ---------------------------------------------------------------
@router.post("/api/voice/announce")
async def voice_announce(req: VoiceAnnounceRequest):
    if not voice:
        return JSONResponse({"error": "Voice module not available"}, status_code=503)
    path = voice.announce(req.message, language=req.language, play=req.play)
    return {"status": "ok", "audio_file": path}



@router.get("/api/voice/log")
async def voice_log(limit: int = 20):
    if not voice:
        return []
    return voice.get_broadcast_log(limit=limit)



# ---------------------------------------------------------------
# REST Endpoints — Aggregated Metrics
# ---------------------------------------------------------------
@router.get("/api/metrics/overview")
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
        "ws_clients": deps.ws_manager.count,
    }
    return overview



@router.get("/api/ai/status")
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


@router.get("/api/ai/lstm/results")
async def ai_lstm_results():
    """Get LSTM training results if available."""
    results = _load_json_safe("results/lstm/lstm_training_results.json")
    if not results:
        return {"status": "not_trained", "message": "Run: python scripts/train_lstm.py"}
    return results


@router.get("/api/ai/anomaly/results")
async def ai_anomaly_results():
    """Get ML anomaly detection results."""
    results = _load_json_safe("results/anomaly/anomaly_detection_results.json")
    if not results:
        return {"status": "not_evaluated", "message": "Run: python -m ai.anomaly.ml_anomaly_detector --generate"}
    return results


@router.get("/api/ai/xai/importance")
async def ai_xai_importance():
    """Get feature importance analysis."""
    results = _load_json_safe("results/xai/xai_report.json")
    if not results:
        return {"status": "not_computed", "message": "Run: python -m ai.explainability.explainer --model <path>"}
    return results


@router.get("/api/ai/comparison")
async def ai_agent_comparison():
    """Get agent comparison results (DQN vs PPO vs A2C)."""
    results = _load_json_safe("results/comparison/comparison_results.json")
    if not results:
        return {"status": "not_run", "message": "Run: python scripts/compare_agents.py"}
    return results


@router.get("/api/ai/explain")
async def ai_explain_decision(
    queue_n: float = Query(0.5), queue_s: float = Query(0.3),
    queue_e: float = Query(0.4), queue_w: float = Query(0.2),
    wait_n: float = Query(0.3), wait_s: float = Query(0.2),
    wait_e: float = Query(0.4), wait_w: float = Query(0.1),
):
    """Get AI explanation for a signal decision given current state."""
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


@router.get("/api/ai/training-history")
async def ai_training_history():
    """Return LSTM loss curves for frontend charting."""
    lstm = _load_json_safe("results/lstm/lstm_training_results.json")
    if lstm and "history" in lstm:
        return {"history": lstm["history"], "epochs": lstm.get("epochs_trained", 0)}
    return {"history": {}, "epochs": 0}



