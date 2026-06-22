import os
import sys
import numpy as np
import torch
import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from control.traffic_env import TrafficEnvironment, IntersectionConfig

class AnomalyInjectionWrapper(gym.Wrapper):
    def __init__(self, env):
        super().__init__(env)
        # Increase anomaly probability and reward multiplier to FORCE the policy to learn it
        self.env.unwrapped._anomaly_prob = 0.05
        self.env.unwrapped._anomaly_multiplier = 10.0
        
        # Tracking variables
        self.anomaly_steps = 0
        self.total_steps = 0
        self.anomaly_severities = []
        
    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self.total_steps += 1
        
        # North approach is index 0-4. Anomaly is at index 4
        sev = obs[4]
        if sev > 0.0:
            self.anomaly_steps += 1
            self.anomaly_severities.append(sev)
            
        return obs, reward, terminated, truncated, info

class TrainingLoggerCallback(BaseCallback):
    def __init__(self, verbose=0):
        super().__init__(verbose)
        
    def _on_step(self) -> bool:
        return True
        
    def _on_rollout_end(self) -> None:
        env_wrapper = self.training_env.envs[0]
        if hasattr(env_wrapper, 'env') and hasattr(env_wrapper.env, 'anomaly_steps'):
            wrapper = env_wrapper.env
            total = max(1, wrapper.total_steps)
            pct = wrapper.anomaly_steps / total * 100.0
            avg_sev = np.mean(wrapper.anomaly_severities) if len(wrapper.anomaly_severities) > 0 else 0.0
            print(f"Rollout | Anomaly frequency: {pct:.2f}% of steps | Avg Severity when active: {avg_sev:.2f}", flush=True)

def run_sensitivity_sweep(model, env):
    print("\n--- RUNNING SENSITIVITY SWEEP ---")
    
    # Get a baseline clean observation
    obs, _ = env.reset()
    
    # Zero out all anomalies to create a pristine base
    obs[4] = 0.0
    obs[9] = 0.0
    obs[14] = 0.0
    obs[19] = 0.0
    
    severities = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    results = []
    
    actions_selected = set()
    prob_variances = []
    
    for sev in severities:
        test_obs = obs.copy()
        test_obs[4] = sev  # Inject severity only to the North approach
        
        action, _ = model.predict(test_obs, deterministic=True)
        actions_selected.add(int(action))
        
        obs_tensor = torch.tensor(test_obs).unsqueeze(0).to(model.device)
        with torch.no_grad():
            dist = model.policy.get_distribution(obs_tensor)
            probs = dist.distribution.probs.cpu().numpy()[0]
            val = model.policy.predict_values(obs_tensor).cpu().numpy()[0][0]
            
        results.append((sev, int(action), probs, float(val)))
        prob_variances.append(probs)
        
    print(f"{'Severity':<10} | {'Action':<8} | {'Value':<10} | {'Probabilities'}")
    print("-" * 70)
    for sev, act, probs, val in results:
        prob_str = ", ".join([f"{p:.3f}" for p in probs])
        print(f"{sev:<10.2f} | {act:<8} | {val:<10.3f} | [{prob_str}]")
        
    # Check if probabilities changed
    prob_variances = np.array(prob_variances)
    std_devs = np.std(prob_variances, axis=0)
    max_std = np.max(std_devs)
    
    success = max_std > 0.01  # At least 1% standard deviation in probability distribution
    
    if success:
        print("\nSUCCESS: Policy distribution changes materially as severity increases!")
    else:
        print("\nFAILED: Policy is still insensitive to anomaly index 4.")
        
    return success

def train_and_verify():
    config = IntersectionConfig()
    base_env = TrafficEnvironment(config=config)
    
    # Verify Delta-Wait is loaded
    if not hasattr(base_env, '_prev_wait'):
        raise RuntimeError("Environment does not contain delta-wait tracking (_prev_wait missing).")
    print("Verified: Delta-wait environment loaded successfully.", flush=True)
    
    env = AnomalyInjectionWrapper(base_env)
    
    # Check if a model exists to fine-tune, or train from scratch. 
    # The user says "train a new checkpoint"
    model = PPO("MlpPolicy", env, verbose=0, learning_rate=3e-4, ent_coef=0.01)
    
    max_attempts = 3
    success = False
    
    checkpoint_dir = PROJECT_ROOT / "models" / "anomaly_sensitive"
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = checkpoint_dir / "best_model.zip"
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n--- TRAINING ATTEMPT {attempt}/{max_attempts} ---", flush=True)
        model.learn(total_timesteps=50000, callback=TrainingLoggerCallback())
        
        success = run_sensitivity_sweep(model, base_env)
        if success:
            model.save(str(checkpoint_path))
            print(f"\nSaved sensitive model to: {checkpoint_path}")
            break
            
    if not success:
        print("\nFailed to learn sensitivity after max attempts.")
        # Inspect weights connected to feature index 4
        policy_net = model.policy.mlp_extractor.policy_net
        first_layer = policy_net[0]
        weights = first_layer.weight.data
        idx_4_weights = weights[:, 4]
        avg_weight_mag = torch.mean(torch.abs(idx_4_weights)).item()
        print(f"Average absolute weight magnitude for Index 4 entering first hidden layer: {avg_weight_mag:.6f}")

if __name__ == "__main__":
    train_and_verify()
