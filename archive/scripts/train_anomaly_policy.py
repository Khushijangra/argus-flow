import sys
import os
import argparse
from datetime import datetime

# Add project root to path
PROJECT_ROOT = "c:/Users/Asus/OneDrive/Desktop/projects/urban congestion"
sys.path.insert(0, PROJECT_ROOT)

from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import BaseCallback

from control.traffic_env import TrafficEnvironment, IntersectionConfig

class AnomalyMetricsCallback(BaseCallback):
    """
    Custom callback for plotting additional values in tensorboard.
    """
    def __init__(self, verbose=0):
        super().__init__(verbose)

    def _on_step(self) -> bool:
        # We can extract anomaly events from the environment if needed
        # For now, just logging standard reward metrics natively handled by SB3
        return True

def train_stage(model_path, save_path, timesteps, stage_name):
    print(f"\n--- Starting {stage_name} ({timesteps} steps) ---")
    
    env_config = IntersectionConfig()
    # Create vectorized environment
    env = make_vec_env(lambda: TrafficEnvironment(env_config), n_envs=1)
    
    if os.path.exists(model_path):
        print(f"Loading existing model from {model_path}...")
        model = PPO.load(model_path, env=env, device="cpu", custom_objects={"clip_range": 0.2, "learning_rate": 5e-5})
    else:
        print(f"Starting fresh model...")
        model = PPO("MlpPolicy", env, verbose=1, device="cpu", learning_rate=3e-4, tensorboard_log=os.path.join(PROJECT_ROOT, "logs", "anomaly_training"))

    # Train
    model.learn(total_timesteps=timesteps, callback=AnomalyMetricsCallback(), tb_log_name=stage_name, reset_num_timesteps=False)
    
    # Save
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    model.save(save_path)
    print(f"Saved {stage_name} model to {save_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, default=1, help="Stage 1 (50k), Stage 2 (200k), Stage 3 (500k)")
    args = parser.parse_args()
    
    # Base model from Phase 1 is in models/baseline/best_model.zip
    base_model = os.path.join(PROJECT_ROOT, "models", "baseline", "best_model.zip")
    
    if args.stage == 1:
        # Load baseline, train 50k, save to anomaly_v1
        save_model = os.path.join(PROJECT_ROOT, "models", "anomaly_v1", "best", "best_model.zip")
        train_stage(base_model, save_model, 50000, "Stage1_50k")
        
    elif args.stage == 2:
        # Load baseline directly for Stage 2 since Stage 1 collapsed
        train_stage(base_model, os.path.join(PROJECT_ROOT, "models", "anomaly_v2", "best", "best_model.zip"), 200000, "Stage2_200k")
        
    elif args.stage == 3:
        # Load Stage 2, train 500k
        load_model = os.path.join(PROJECT_ROOT, "models", "anomaly_v2", "best", "best_model.zip")
        train_stage(load_model, load_model, 500000, "Stage3_500k")
        
    elif args.stage == 4:
        # Final unclipped reward training (anomaly_v3)
        train_stage(base_model, os.path.join(PROJECT_ROOT, "models", "anomaly_v3", "best", "best_model.zip"), 100000, "Stage4_anomaly_v3")
        
    elif args.stage == 5:
        # Rebalanced reward logic training (anomaly_v4)
        train_stage(base_model, os.path.join(PROJECT_ROOT, "models", "anomaly_v4", "best", "best_model.zip"), 50000, "Stage5_anomaly_v4")
