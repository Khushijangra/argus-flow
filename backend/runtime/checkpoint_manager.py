import os
from stable_baselines3 import PPO

class CheckpointManager:
    def __init__(self, primary_path: str, fallback_path: str = None):
        self.primary_path = primary_path
        self.fallback_path = fallback_path
        self.model = None

    def load_model(self) -> PPO:
        """Loads RL Checkpoint with automatic rollback and compatibility validation."""
        try:
            print(f"Loading primary RL checkpoint: {self.primary_path}")
            if not os.path.exists(self.primary_path):
                raise FileNotFoundError(f"Primary checkpoint not found: {self.primary_path}")
            self.model = PPO.load(self.primary_path, device="cpu")
            self._validate_model(self.model)
            return self.model
        except Exception as e:
            print(f"Failed to load primary checkpoint: {e}")
            if self.fallback_path:
                print(f"Attempting rollback to fallback checkpoint: {self.fallback_path}")
                try:
                    if not os.path.exists(self.fallback_path):
                        raise FileNotFoundError(f"Fallback checkpoint not found: {self.fallback_path}")
                    self.model = PPO.load(self.fallback_path, device="cpu")
                    self._validate_model(self.model)
                    print("Rollback successful.")
                    return self.model
                except Exception as rollback_e:
                    print(f"Fallback load failed: {rollback_e}")
                    raise RuntimeError("All checkpoints failed to load.") from rollback_e
            else:
                raise RuntimeError("Primary checkpoint failed and no fallback provided.") from e

    def _validate_model(self, model: PPO):
        # Validate observation space (needs to be 28 for our Hybrid State)
        obs_shape = model.observation_space.shape
        if obs_shape != (28,):
            raise ValueError(f"Incompatible observation shape: {obs_shape}. Expected (28,).")
        print("Model compatibility validated (28-D observation space).")
