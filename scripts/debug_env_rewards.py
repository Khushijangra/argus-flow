import sys
import os
import numpy as np
from collections import defaultdict

PROJECT_ROOT = "c:/Users/Asus/OneDrive/Desktop/projects/urban congestion"
sys.path.insert(0, PROJECT_ROOT)

from control.traffic_env import TrafficEnvironment, IntersectionConfig

def run_debug():
    print("=========================================")
    print("TASK 1 & 3: ENVIRONMENT DEEP-DIVE")
    print("=========================================")
    
    cfg = IntersectionConfig()
    env = TrafficEnvironment(cfg)
    
    env.reset()
    
    rewards_log = defaultdict(list)
    anomaly_stats = defaultdict(list)
    
    steps = 1000
    anomaly_active_steps = 0
    
    for i in range(steps):
        action = env.action_space.sample()
        obs, reward, term, trunc, info = env.step(action)
        
        # We need to extract the sub-rewards. To do this precisely, we'll reach into the env
        # Actually, let's just copy the logic from _compute_reward to see the terms
        throughput = env._total_throughput  # This is cumulative though, we need step throughput
        # The env doesn't store step throughput, but we can recalculate or just modify env temporarily
        # For now, let's just patch traffic_env.py to return the terms in info!
        
        anoms = info["anomalies"]
        has_anomaly = any(v > 0.0 for v in anoms.values())
        if has_anomaly:
            anomaly_active_steps += 1
            for ap, v in anoms.items():
                if v > 0.0:
                    anomaly_stats[ap].append(v)
                    
        # Log reward terms
        if "reward_terms" in info:
            for k, v in info["reward_terms"].items():
                rewards_log[k].append(v)
            rewards_log["total_reward"].append(reward)
            
        if term or trunc:
            env.reset()
            
    print(f"\n--- ANOMALY STATS ({steps} steps) ---")
    print(f"Anomaly active steps: {anomaly_active_steps} ({anomaly_active_steps/steps*100:.1f}%)")
    for ap, vals in anomaly_stats.items():
        print(f"  {ap}: mean={np.mean(vals):.2f}, max={np.max(vals):.2f}, events_logged={len(vals)}")
        
    print("\n--- REWARD TERM STATS ---")
    for k, vals in rewards_log.items():
        print(f"{k:>15}: min={np.min(vals):7.2f}, max={np.max(vals):7.2f}, mean={np.mean(vals):7.2f}")
        
    print("\nDebug complete.")

if __name__ == "__main__":
    run_debug()
