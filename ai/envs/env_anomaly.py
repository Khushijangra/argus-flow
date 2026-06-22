import gymnasium as gym
from gymnasium import spaces
import numpy as np
import traci
import random
import logging
import os
import sys

# Ensure vision_bridge is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai.envs.sumo_env import SumoEnvironment
from ai.vision.vision_bridge import VisionBridge

class AnomalySumoEnvironment(SumoEnvironment):
    def __init__(self, incident_prob=0.01, **kwargs):
        # Initialise base SUMO environment
        super().__init__(**kwargs)
        
        # Expand state_dim by 2 (anomaly_score, anomaly_flag)
        self.original_state_dim = self.state_dim
        self.state_dim = self.original_state_dim + 2
        
        # Update observation space
        self.observation_space = spaces.Box(
            low=0.0, high=np.inf, shape=(self.state_dim,), dtype=np.float32
        )
        
        # Initialise ZeroMQ bridge to ARGUS inference server
        self.vision_bridge = VisionBridge(port=5555, timeout_ms=50)
        self.incident_prob = incident_prob
        self.current_incident = "none"
        self.incident_duration = 0
        
    def reset(self, seed=None, options=None):
        """Reset environment and clear VisionBridge buffers."""
        self.vision_bridge.reset()
        self.current_incident = "none"
        self.incident_duration = 0
        return super().reset(seed=seed, options=options)
        
    def _inject_incident(self):
        """Inject synthetic incidents into the SUMO simulation periodically."""
        # Only inject if no active incident
        if self.current_incident != "none":
            self.incident_duration -= 1
            if self.incident_duration <= 0:
                self.current_incident = "none"
                # SUMO vehicles generally recover their speeds dynamically if setSpeed is lifted
            return
            
        if random.random() < self.incident_prob:
            incident_types = ["stopped_vehicle", "lane_blockage", "intersection_obstruction"]
            self.current_incident = random.choice(incident_types)
            self.incident_duration = random.randint(10, 30) # simulation steps
            
            try:
                vehicles = traci.vehicle.getIDList()
                if not vehicles:
                    self.current_incident = "none"
                    return
                
                target_vehicle = random.choice(vehicles)
                
                if self.current_incident == "stopped_vehicle":
                    traci.vehicle.setSpeed(target_vehicle, 0.0)
                    traci.vehicle.setColor(target_vehicle, (255, 0, 0, 255))
                elif self.current_incident == "lane_blockage":
                    traci.vehicle.setSpeedMode(target_vehicle, 0)
                    traci.vehicle.setSpeed(target_vehicle, 0.0)
                elif self.current_incident == "intersection_obstruction":
                    traci.vehicle.setSpeed(target_vehicle, 0.0)
            except Exception as e:
                logging.warning(f"Failed to inject incident: {e}")
                self.current_incident = "none"

    def _get_state(self) -> np.ndarray:
        """Fetch SUMO traffic state and append ARGUS anomaly state."""
        base_state = super()._get_state()
        
        # Query vision bridge for anomaly context via ZeroMQ
        score, flag, inc = self.vision_bridge.get_anomaly_context(
            frame_id=self._step_count,
            context="synthetic",
            incident_type=self.current_incident
        )
        
        anomaly_features = np.array([score, float(flag)], dtype=np.float32)
        multimodal_state = np.concatenate([base_state, anomaly_features])
        
        # Validation Assertion as requested
        assert multimodal_state.shape[-1] == self.state_dim, f"Shape mismatch: {multimodal_state.shape[-1]} != {self.state_dim}"
        
        return multimodal_state

    def step(self, action: int):
        """Advance simulation and generate multimodal state."""
        self._inject_incident()
        
        # Calls base step which implicitly calls _get_state()
        obs, reward, terminated, truncated, info = super().step(action)
        
        # Log anomaly metrics for debugging
        score, flag = obs[-2], obs[-1]
        info["anomaly_score"] = float(score)
        info["anomaly_flag"] = int(flag)
        info["incident_type"] = self.current_incident
        
        return obs, reward, terminated, truncated, info

# Register environment with Gymnasium
gym.register(
    id="SumoAnomaly-v0",
    entry_point="ai.envs.env_anomaly:AnomalySumoEnvironment",
)
