import os
import sys
from pathlib import Path
import time
import numpy as np
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.runtime.checkpoint_manager import CheckpointManager
from control.traffic_env import TrafficEnvironment, IntersectionConfig

def run_multi_intersection_validation():
    print("====================================================")
    print("TASK 2: MULTI-INTERSECTION VALIDATION (4x4 GRID)")
    print("====================================================")
    
    chk_mgr = CheckpointManager(primary_path=PROJECT_ROOT / "models/J0_0/releases/production_v1.zip")
    model = chk_mgr.load_model()
    
    # Instantiate 16 intersections for a 4x4 grid
    grid_size = 4
    intersections = {}
    for i in range(grid_size):
        for j in range(grid_size):
            iid = f"J_{i}_{j}"
            env = TrafficEnvironment(IntersectionConfig(intersection_id=iid), render_mode="none")
            obs, _ = env.reset()
            intersections[iid] = {"env": env, "obs": obs}
            
    cycles = 500
    metrics = {
        "queue": [],
        "wait": [],
        "throughput": 0,
        "crashes": 0,
        "fallbacks": 0
    }
    
    for cycle in range(cycles):
        for iid, data in intersections.items():
            try:
                env = data["env"]
                obs = data["obs"]
                
                # Check shape
                if obs.shape != (28,):
                    metrics["crashes"] += 1
                    continue
                    
                # Action
                action, _ = model.predict(obs, deterministic=True)
                
                # Step
                next_obs, reward, terminated, truncated, info = env.step(int(action))
                data["obs"] = next_obs
                
                # Metrics
                q = sum(info["queue"].values())
                w = sum(info["wait"].values())
                metrics["queue"].append(q)
                metrics["wait"].append(w)
                metrics["throughput"] += info.get("throughput", sum(info["queue"].values()) * 0.1)  # Proxy for throughput
                
            except Exception as e:
                metrics["crashes"] += 1
                
    avg_queue = np.mean(metrics["queue"])
    avg_wait = np.mean(metrics["wait"])
    
    print("Metrics Collected:")
    print(f"- Average Queue: {avg_queue:.2f}")
    print(f"- Average Wait: {avg_wait:.2f}")
    print(f"- Intersection Throughput (proxy): {metrics['throughput']:.2f}")
    print(f"- Crashes: {metrics['crashes']}")
    print(f"- Fallback Activations: {metrics['fallbacks']}")
    print("====================================================")

if __name__ == "__main__":
    run_multi_intersection_validation()
