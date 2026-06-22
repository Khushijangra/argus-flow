import sys
import os
import argparse
import numpy as np
from collections import defaultdict
import torch

# Add project root to path
PROJECT_ROOT = "c:/Users/Asus/OneDrive/Desktop/projects/urban congestion"
sys.path.insert(0, PROJECT_ROOT)

from control.traffic_env import TrafficEnvironment, IntersectionConfig, APPROACHES
from stable_baselines3 import PPO

def evaluate_scenario(model, env_config, anomaly_lane=None, anomaly_severity=1.0, episodes=3):
    """Evaluates the policy under a specific anomaly scenario and records behavior."""
    env = TrafficEnvironment(env_config)
    
    metrics = {
        "queue": defaultdict(list),
        "wait": defaultdict(list),
        "cumulative_reward": 0.0,
        "phase_alloc": defaultdict(int),
        "steps": 0
    }
    
    for ep in range(episodes):
        obs, _ = env.reset(seed=42+ep)
        
        # Override the stochastic anomaly logic
        if anomaly_lane:
            env._anomaly_severity[anomaly_lane] = anomaly_severity
            env._anomaly_timer[anomaly_lane] = 99999.0
            obs = env._build_obs()
            
        done = False
        while not done:
            # Force anomaly every step
            if anomaly_lane:
                env._anomaly_severity[anomaly_lane] = anomaly_severity
                env._anomaly_timer[anomaly_lane] = 99999.0
                obs = env._build_obs()
                
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(int(action))
            done = terminated or truncated
            
            metrics["cumulative_reward"] += reward
            metrics["steps"] += 1
            metrics["phase_alloc"][info["phase"]] += 1
            
            for a in APPROACHES:
                metrics["queue"][a].append(info["queue"][a])
                metrics["wait"][a].append(info["wait"][a])
                
    # Aggregate
    res = {
        "avg_reward": metrics["cumulative_reward"] / episodes,
        "phase_alloc_pct": {k: v / metrics["steps"] * 100 for k, v in metrics["phase_alloc"].items()},
        "avg_queue": {a: np.mean(metrics["queue"][a]) for a in APPROACHES},
        "avg_wait": {a: np.mean(metrics["wait"][a]) for a in APPROACHES}
    }
    return res

def run_evaluation(model_dir):
    model_path = os.path.join(PROJECT_ROOT, "models", model_dir, "best", "best_model.zip")
    if not os.path.exists(model_path):
        # Try without 'best' if it doesn't exist
        model_path = os.path.join(PROJECT_ROOT, "models", model_dir, "best_model.zip")
        if not os.path.exists(model_path):
            print(f"Error: Model not found at {model_path}")
            return
        
    print(f"Loading model from {model_path}...")
    model = PPO.load(model_path, device="cpu")
    config = IntersectionConfig()
    
    print("\n--- Scenario A: Baseline (No Anomaly) ---")
    res_base = evaluate_scenario(model, config, anomaly_lane=None)
    print(f"Avg Reward: {res_base['avg_reward']:.2f}")
    print(f"Phase Allocation: {res_base['phase_alloc_pct']}")
    print(f"Avg Queue: {res_base['avg_queue']}")
    
    print("\n--- Scenario B: North Anomaly (Severity 1.0) ---")
    res_north = evaluate_scenario(model, config, anomaly_lane="north")
    print(f"Avg Reward: {res_north['avg_reward']:.2f}")
    print(f"Phase Allocation: {res_north['phase_alloc_pct']}")
    print(f"Avg Queue: {res_north['avg_queue']}")
    
    print("\n--- Scenario C: West Anomaly (Severity 1.0) ---")
    res_west = evaluate_scenario(model, config, anomaly_lane="west")
    print(f"Avg Reward: {res_west['avg_reward']:.2f}")
    print(f"Phase Allocation: {res_west['phase_alloc_pct']}")
    print(f"Avg Queue: {res_west['avg_queue']}")

    print("\n--- Scenario D: South Anomaly (Severity 1.0) ---")
    res_south = evaluate_scenario(model, config, anomaly_lane="south")
    print(f"Avg Reward: {res_south['avg_reward']:.2f}")
    print(f"Phase Allocation: {res_south['phase_alloc_pct']}")
    print(f"Avg Queue: {res_south['avg_queue']}")
    
    # Analysis
    print("\n--- BEHAVIOR SHIFT ANALYSIS ---")
    n_alloc_base = res_base['phase_alloc_pct'].get('NS_through', 0) + res_base['phase_alloc_pct'].get('NS_left', 0)
    n_alloc_anom = res_north['phase_alloc_pct'].get('NS_through', 0) + res_north['phase_alloc_pct'].get('NS_left', 0)
    print(f"North-South Green Allocation (Base -> North Anomaly): {n_alloc_base:.1f}% -> {n_alloc_anom:.1f}%")
    
    w_alloc_base = res_base['phase_alloc_pct'].get('EW_through', 0) + res_base['phase_alloc_pct'].get('EW_left', 0)
    w_alloc_anom = res_west['phase_alloc_pct'].get('EW_through', 0) + res_west['phase_alloc_pct'].get('EW_left', 0)
    print(f"East-West Green Allocation (Base -> West Anomaly): {w_alloc_base:.1f}% -> {w_alloc_anom:.1f}%")
    print("\nEvidence generation complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="baseline", help="Directory name in models/ (e.g. anomaly_v1 or baseline)")
    args = parser.parse_args()
    run_evaluation(args.model)
