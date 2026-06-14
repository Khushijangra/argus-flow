import pytest
import numpy as np
import gymnasium as gym

class MockTrafficEnv(gym.Env):
    def __init__(self):
        super().__init__()
        self.observation_space = gym.spaces.Box(low=0, high=1, shape=(26,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(4)
        
    def reset(self, seed=None):
        return self.observation_space.sample(), {}

    def step(self, action):
        obs = self.observation_space.sample()
        reward = np.random.randn()
        done = False
        return obs, reward, done, False, {}

@pytest.fixture
def mock_env():
    return MockTrafficEnv()

@pytest.fixture
def d3qn_config():
    return {
        "agent": {
            "device": "cpu",
            "d3qn": {
                "hidden_dim": 64,
                "batch_size": 16,
                "buffer_size": 1000
            }
        },
        "training": {
            "seed": 42
        }
    }
