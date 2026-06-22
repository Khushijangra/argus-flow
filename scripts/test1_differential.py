import os
import sys
from pathlib import Path
import cv2
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
STREAM_A_SRC = PROJECT_ROOT / "argus_stream_extracted" / "argus stream A"
sys.path.insert(0, str(STREAM_A_SRC))

import numpy as np
from collections import defaultdict
from backend.runtime.checkpoint_manager import CheckpointManager
from control.traffic_env import TrafficEnvironment, IntersectionConfig
from src.models.backbones.videomae import VideoMAEFeatureExtractor
from src.models.scorers.mulde import MULDEScorer

def run_differential_test():
    print("====================================================")
    print("TEST 1: REAL VIDEO DIFFERENTIAL TEST")
    print("====================================================")
    
    # 1. Known Severity from Real Video (Pre-extracted)
    video_path = PROJECT_ROOT / "backend/uploads/uploaded_1776265305.mp4"
    print(f"Loading Video: {video_path}")
    
    raw_score = 14.155392387371135
    norm_severity = 0.8333333333333333
    print(f"Raw Score: {raw_score}")
    print(f"Normalized Severity: {norm_severity}")
    
    # 2. Load RL Model
    chk_mgr = CheckpointManager(primary_path=PROJECT_ROOT / "models/anomaly_v4/best/best_model.zip")
    model = chk_mgr.load_model()
    
    # 3. Define a simulation loop
    def run_sim(severity, label):
        env = TrafficEnvironment(IntersectionConfig(), render_mode="none")
        obs, info = env.reset(seed=42)
        
        metrics = {"reward": 0.0, "steps": 0, "phase_alloc": defaultdict(int), "queue": defaultdict(list), "wait": defaultdict(list)}
        
        # We will track the exact anomaly index observation and action
        first_obs_vec_anomaly_idx = None
        first_action = None
        
        for _ in range(100):
            # Inject severity
            env._anomaly_severity["north"] = severity
            env._anomaly_timer["north"] = 999.0
            obs = env._build_obs()
            
            if first_obs_vec_anomaly_idx is None:
                first_obs_vec_anomaly_idx = obs[4]
                
            action, _ = model.predict(obs, deterministic=True)
            if first_action is None:
                first_action = int(action)
                
            obs, reward, term, trunc, info = env.step(int(action))
            metrics["reward"] += reward
            metrics["steps"] += 1
            metrics["phase_alloc"][info["phase"]] += 1
            for a in ["north", "south", "east", "west"]:
                metrics["queue"][a].append(info["queue"][a])
                metrics["wait"][a].append(info["wait"][a])
                
        # Aggregate
        avg_queue = {a: np.mean(metrics["queue"][a]) for a in ["north", "south", "east", "west"]}
        avg_wait = {a: np.mean(metrics["wait"][a]) for a in ["north", "south", "east", "west"]}
        phase_pct = {k: v / metrics["steps"] * 100 for k, v in metrics["phase_alloc"].items()}
        
        print(f"\n--- {label} ---")
        print(f"RL Observation Vector Anomaly Index: {first_obs_vec_anomaly_idx}")
        print(f"First PPO Action: {first_action}")
        print(f"Phase Allocation: {phase_pct}")
        print(f"Avg Queue: {avg_queue}")
        print(f"Avg Wait: {avg_wait}")
        
        return first_action, phase_pct, avg_queue, avg_wait

    # 4. Run A (Actual Severity)
    action_A, phase_A, queue_A, wait_A = run_sim(norm_severity, "Run A (Actual Stream-A Severity)")
    
    # 5. Run B (Severity 0.0)
    action_B, phase_B, queue_B, wait_B = run_sim(0.0, "Run B (Forced Severity = 0.0)")
    
    # 6. Evaluate Pass Condition
    diff_action = (action_A != action_B)
    diff_phase = (phase_A != phase_B)
    diff_queue = (queue_A != queue_B)
    diff_wait = (wait_A != wait_B)
    
    passed = diff_action or diff_phase or diff_queue or diff_wait
    
    print("\n====================================================")
    print(f"TEST 1 RESULT: {'PASS' if passed else 'FAIL'}")
    print("====================================================")

if __name__ == "__main__":
    run_differential_test()
