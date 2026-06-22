import pytest
import numpy as np
import torch
from ai.rl.d3qn import D3QNAgent, ReplayBuffer

def test_agent_init(mock_env, d3qn_config, tmp_path):
    agent = D3QNAgent(
        env=mock_env, 
        config=d3qn_config,
        log_dir=str(tmp_path / "logs"),
        model_dir=str(tmp_path / "models")
    )
    assert agent.state_dim == 26
    assert agent.action_dim == 4
    assert agent.device.type == "cpu"

def test_action_selection(mock_env, d3qn_config, tmp_path):
    agent = D3QNAgent(
        env=mock_env, 
        config=d3qn_config,
        log_dir=str(tmp_path / "logs"),
        model_dir=str(tmp_path / "models")
    )
    obs = mock_env.observation_space.sample()
    action = agent.predict(obs, deterministic=True)
    assert isinstance(action, int)
    assert 0 <= action < agent.action_dim

def test_buffer_push_sample():
    buffer = ReplayBuffer(capacity=100)
    for i in range(20):
        buffer.push(np.zeros(26), 1, 1.0, np.ones(26), 0.0)
    
    assert len(buffer) == 20
    states, actions, rewards, next_states, dones = buffer.sample(5)
    assert states.shape == (5, 26)
    assert actions.shape == (5,)
    assert rewards.shape == (5,)
    assert next_states.shape == (5, 26)
    assert dones.shape == (5,)

def test_optimize_step_no_crash(mock_env, d3qn_config, tmp_path):
    agent = D3QNAgent(
        env=mock_env, 
        config=d3qn_config,
        log_dir=str(tmp_path / "logs"),
        model_dir=str(tmp_path / "models")
    )
    # Fill buffer to enable optimization
    for _ in range(agent.batch_size + 5):
        obs = mock_env.observation_space.sample()
        next_obs = mock_env.observation_space.sample()
        agent.replay_buffer.push(obs, 0, 1.0, next_obs, 0)
        
    stats = agent._optimize_step()
    assert stats is not None
    assert "loss" in stats
    assert "q_mean" in stats
