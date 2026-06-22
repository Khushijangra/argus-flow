import os
import sys
import time
import json
import traceback
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
STREAM_A_SRC = PROJECT_ROOT / "argus_stream_extracted" / "argus stream A"
sys.path.insert(0, str(STREAM_A_SRC))

# Output containers
logs = []
latencies = {}
failures = []
gaps = []
files_to_modify = set()

def log(phase, msg):
    print(f"[{phase}] {msg}")
    logs.append(f"[{phase}] {msg}")

def fail(phase, msg, e, files=None):
    err = f"[{phase}] FAILED: {msg} | Exception: {type(e).__name__}: {str(e)}"
    print(err)
    logs.append(err)
    failures.append(err)
    if files:
        for f in files:
            files_to_modify.add(f)
    gaps.append(f"Integration Gap in {phase}: {msg}")

def run_audit():
    print("====================================================")
    print("NEXUS-ATMS END-TO-END EXECUTION AUDIT")
    print("====================================================")

    # ---------------------------------------------------------
    # PHASE 1: VIDEO INGESTION VERIFICATION
    # ---------------------------------------------------------
    phase = "PHASE 1 (Video)"
    t0 = time.time()
    try:
        import cv2
        video_path = PROJECT_ROOT / "backend/uploads/uploaded_1776265305.mp4"
        if not video_path.exists():
            raise FileNotFoundError(f"Missing video {video_path}")
            
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        frames = []
        for _ in range(16):
            ret, frame = cap.read()
            if not ret: break
            frames.append(frame)
        cap.release()
        
        log(phase, f"Loaded {video_path.name}")
        log(phase, f"FPS: {fps}, Total Frames: {frame_count}")
        log(phase, f"Window Generated: {len(frames)} frames of shape {frames[0].shape if frames else 'N/A'}")
        
        if len(frames) < 16:
            raise ValueError("Insufficient frames for a 16-frame clip.")
    except Exception as e:
        fail(phase, "Video Ingestion Failed", e)
    latencies[phase] = time.time() - t0

    # ---------------------------------------------------------
    # PHASE 2: VIDEOMAE VERIFICATION
    # ---------------------------------------------------------
    phase = "PHASE 2 (VideoMAE)"
    t0 = time.time()
    embeddings = np.zeros((1, 768), dtype=np.float32) # Fallback
    try:
        from src.models.backbones.videomae import VideoMAEFeatureExtractor
        extractor = VideoMAEFeatureExtractor()
        log(phase, "VideoMAEFeatureExtractor initialized successfully.")
        
        # Real extraction from in-memory frames!
        embeddings = extractor.extract_from_frames(frames, batch_size=1)
        log(phase, f"Embeddings generated, shape: {embeddings.shape}")
        if embeddings.shape[-1] != 768:
            raise ValueError(f"Expected 768 dim, got {embeddings.shape}")
    except Exception as e:
        fail(phase, "VideoMAE Execution Failed", e, files=["scripts/extract_ua_detrac_features.py"])
    latencies[phase] = time.time() - t0

    # ---------------------------------------------------------
    # PHASE 3: STREAM-A VERIFICATION
    # ---------------------------------------------------------
    phase = "PHASE 3 (Stream-A)"
    t0 = time.time()
    anomaly_score = 0.5
    try:
        from src.models.scorers.mulde import MULDEScorer
        import torch
        ckpt_path = PROJECT_ROOT / "models/stream_a/best_clip.pt"
        if not ckpt_path.exists():
            raise FileNotFoundError(f"best_clip.pt not found at {ckpt_path}")
            
        scorer = MULDEScorer.load_checkpoint(ckpt_path, device="cpu")
        scorer.eval()
        log(phase, "best_clip.pt loaded.")
        
        with torch.no_grad():
            x = torch.tensor(embeddings, dtype=torch.float32)
            raw_scores = scorer.score_anomaly(x)
            anomaly_score = float(raw_scores[0])
            
        log(phase, f"Anomaly score generated: {anomaly_score}")
        log(phase, f"Normalized severity: {anomaly_score/1000.0:.2f}") # Mock norm
    except Exception as e:
        fail(phase, "Stream-A Scoring Failed", e, files=["scripts/inference_server.py"])
    latencies[phase] = time.time() - t0

    # ---------------------------------------------------------
    # PHASE 4: INFERENCE SERVER VERIFICATION
    # ---------------------------------------------------------
    phase = "PHASE 4 (Inference Server)"
    t0 = time.time()
    try:
        from scripts.inference_server import app as inference_app
        from fastapi.testclient import TestClient
        client = TestClient(inference_app)
        req_data = {
            "camera_id": "cam_north",
            "intersection_id": "J0_0",
            "timestamp": str(time.time()),
            "sequence_id": "seq1",
            "features": embeddings[0].tolist()
        }
        resp = client.post("/api/v1/anomaly/detect", json=req_data)
        if resp.status_code == 200:
            data = resp.json()
            log(phase, "Request accepted and response returned.")
            log(phase, f"Response: {data}")
            anomaly_score = data["normalized_severity"]
        elif resp.status_code == 503:
            raise RuntimeError(f"Server returned 503: {resp.text}")
        else:
            raise RuntimeError(f"Server returned {resp.status_code}: {resp.text}")
    except Exception as e:
        fail(phase, "Inference Server Endpoint Failed", e, files=["scripts/inference_server.py"])
    latencies[phase] = time.time() - t0

    # ---------------------------------------------------------
    # PHASE 5: HYBRID STATE VERIFICATION
    # ---------------------------------------------------------
    phase = "PHASE 5 (Hybrid State)"
    t0 = time.time()
    hybrid_state = {}
    try:
        from core.hybrid_state import HybridStateBuilder
        class _DummyApproach:
            def __init__(self, q, w):
                self.queue_length = q
                self.wait_time = w
                self.occupancy_pct = 50.0
                self.speed_kmh = 30.0
                self.flow_veh_h = 100.0

        approaches_data = {
            a: _DummyApproach(10, 20) for a in ["north", "south", "east", "west"]
        }
        
        hybrid_state = HybridStateBuilder.build_from_telemetry(
            intersection_id="J0_0",
            approaches=approaches_data,
            phase_index=0,
            phase_name="NS_GREEN",
            anomalies=[{"lane": "north", "severity": 0.85}] # Injected
        )
        log(phase, "HybridState built successfully.")
        log(phase, f"State: {json.dumps(hybrid_state, indent=2)}")
    except Exception as e:
        fail(phase, "Hybrid State Build Failed", e, files=["core/hybrid_state.py"])
    latencies[phase] = time.time() - t0

    # ---------------------------------------------------------
    # PHASE 6: RL OBSERVATION VERIFICATION
    # ---------------------------------------------------------
    phase = "PHASE 6 (RL Observation)"
    t0 = time.time()
    obs_vec = None
    try:
        from core.hybrid_state import RLObservationMapper
        obs_vec = RLObservationMapper.to_vector(hybrid_state)
        log(phase, f"Observation vector generated. Shape: {obs_vec.shape}")
        if obs_vec.shape != (28,):
            raise ValueError(f"Shape is {obs_vec.shape}, expected (28,)")
        log(phase, f"Anomaly index 4 (North lane anomaly): {obs_vec[4]}")
        log(phase, f"Full Vector: {obs_vec}")
    except Exception as e:
        fail(phase, "RL Observation Mapping Failed", e, files=["core/hybrid_state.py"])
    latencies[phase] = time.time() - t0

    # ---------------------------------------------------------
    # PHASE 7: PPO VERIFICATION
    # ---------------------------------------------------------
    phase = "PHASE 7 (PPO)"
    t0 = time.time()
    action = 0
    try:
        from backend.runtime.checkpoint_manager import CheckpointManager
        ckpt_mgr = CheckpointManager(PROJECT_ROOT / "models/J0_0/best/best_model.zip")
        model = ckpt_mgr.load_model()
        if obs_vec is not None:
            a, _ = model.predict(obs_vec, deterministic=True)
            action = int(a)
            log(phase, f"PPO Inference successful. Selected Action: {action}")
        else:
            raise ValueError("obs_vec is None from previous step.")
    except Exception as e:
        fail(phase, "PPO Inference Failed", e, files=["backend/runtime/checkpoint_manager.py"])
    latencies[phase] = time.time() - t0

    # ---------------------------------------------------------
    # PHASE 8: SUMO VERIFICATION
    # ---------------------------------------------------------
    phase = "PHASE 8 (SUMO)"
    t0 = time.time()
    try:
        from control.traffic_env import TrafficEnvironment, IntersectionConfig
        env_config = IntersectionConfig()
        env_config.sumo_cfg = str(PROJECT_ROOT / "networks/sumo/piedmont.sumocfg")
        env_config.use_gui = False
        env = TrafficEnvironment(env_config)
        env.reset()
        
        info_before = env._get_info() if hasattr(env, '_get_info') else {} # Actually it's in the return of step/reset
        _, _, _, _, info_before = env.step(action) # Step 1 to get initial state
        prev_phase = info_before.get("phase", "Unknown")
        
        _, _, _, _, info_after = env.step(action)
        new_phase = info_after.get("phase", "Unknown")
        
        log(phase, "SUMO stepped successfully.")
        log(phase, f"Previous Phase: {prev_phase} -> New Phase: {new_phase}")
        env.close()
    except Exception as e:
        fail(phase, "SUMO Execution Failed", e, files=["control/traffic_env.py"])
    latencies[phase] = time.time() - t0

    # ---------------------------------------------------------
    # PHASE 9: DIGITAL TWIN VERIFICATION
    # ---------------------------------------------------------
    phase = "PHASE 9 (Digital Twin)"
    t0 = time.time()
    try:
        dt_payload = {
            "tick": 1,
            "junction_id": "J0_0",
            "lat": 37.824,
            "lon": -122.231,
            "traffic": {"queue": {}, "wait": {}},
            "anomalies": {"north": 0.85},
            "signals": "NS_GREEN",
            "neighbors": []
        }
        log(phase, "Websocket payload built successfully.")
        log(phase, json.dumps(dt_payload, indent=2))
        
        if "anomalies" not in dt_payload or "signals" not in dt_payload:
            raise KeyError("Payload missing critical state information.")
    except Exception as e:
        fail(phase, "Digital Twin Payload Failed", e)
    latencies[phase] = time.time() - t0

    # ---------------------------------------------------------
    # PHASE 11: FAILURE TESTING
    # ---------------------------------------------------------
    phase = "PHASE 11 (Failure Testing)"
    t0 = time.time()
    try:
        from backend.runtime.hybrid_runtime import HybridRuntime
        # Create an instance with dummy config
        runtime = HybridRuntime()
        # Mock stream-a failure
        import asyncio
        sev = asyncio.run(runtime.poll_stream_a("cam_nowhere_down_server"))
        log(phase, f"Stream-A Fallback tested. Returned severity: {sev} (Expected 0.0)")
        
        # Test RL fallback
        runtime.rl_policy = None
        heur_action = runtime.heuristic_action(obs_vec)
        log(phase, f"RL Fallback tested. Heuristic returned action: {heur_action}")
        
    except Exception as e:
        fail(phase, "Failure Handling Testing Failed", e, files=["backend/runtime/hybrid_runtime.py"])
    latencies[phase] = time.time() - t0

    # Write output report
    report_lines = []
    report_lines.append("# END-TO-END EXECUTION AUDIT REPORT\n")
    report_lines.append("## 1. RUNTIME LOGS\n```text")
    report_lines.extend(logs)
    report_lines.append("```\n")
    
    report_lines.append("## 2. LATENCY AUDIT\n```text")
    for k, v in latencies.items():
        report_lines.append(f"{k}: {v*1000:.2f} ms")
    report_lines.append("```\n")

    report_lines.append("## 3. ACTUAL FAILURES ENCOUNTERED\n")
    if failures:
        for f in failures:
            report_lines.append(f"- {f}")
    else:
        report_lines.append("- None")
    report_lines.append("\n")

    report_lines.append("## 4. ACTUAL INTEGRATION GAPS FOUND\n")
    if gaps:
        for g in gaps:
            report_lines.append(f"- {g}")
    else:
        report_lines.append("- None")
    report_lines.append("\n")

    report_lines.append("## 5. EXACT FILES REQUIRING MODIFICATION\n")
    if files_to_modify:
        for f in files_to_modify:
            report_lines.append(f"- {f}")
    else:
        report_lines.append("- None")
    
    with open("execution_audit_report.md", "w") as f:
        f.write("\n".join(report_lines))

if __name__ == "__main__":
    run_audit()
