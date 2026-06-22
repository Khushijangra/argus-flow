"""
D3QN Agent for Traffic Signal Control
Dueling Double DQN implemented in native PyTorch (no SB3 dependency).
"""

from __future__ import annotations

import os
import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkstemp
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import gymnasium as gym
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

import traci


def _setup_gpu(preferred_device: str = "cuda") -> str:
    """Configure preferred device with CUDA fallback handling."""
    preferred_device = (preferred_device or "cuda").lower()
    if preferred_device == "cpu":
        print("[GPU] Forced CPU mode")
        return "cpu"
    if not torch.cuda.is_available():
        print("[GPU] CUDA not available — using CPU")
        return "cpu"
    torch.cuda.empty_cache()
    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"[GPU] {gpu_name} | {vram_gb:.1f} GB VRAM | CUDA {torch.version.cuda}")
    return "cuda"


def _set_global_seed(seed: int, deterministic: bool = True) -> None:
    """Set deterministic random seeds for reproducible training runs."""
    if deterministic and torch.cuda.is_available():
        # Required by PyTorch for deterministic cuBLAS kernels on CUDA >= 10.2.
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        try:
            torch.use_deterministic_algorithms(True, warn_only=True)
        except Exception:
            pass
        try:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        except Exception:
            pass


class DuelingQNetwork(nn.Module):
    """Dueling architecture: shared trunk + value stream + advantage stream."""

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )
        self.adv_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, action_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.trunk(x)
        value = self.value_head(h)
        adv = self.adv_head(h)
        return value + (adv - adv.mean(dim=1, keepdim=True))


@dataclass
class Transition:
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: float


class ReplayBuffer:
    """Simple FIFO replay buffer."""

    def __init__(self, capacity: int):
        self.capacity = int(capacity)
        self.buffer: Deque[Transition] = deque(maxlen=self.capacity)

    def push(self, state, action, reward, next_state, done) -> None:
        self.buffer.append(
            Transition(
                state=np.asarray(state, dtype=np.float32),
                action=int(action),
                reward=float(reward),
                next_state=np.asarray(next_state, dtype=np.float32),
                done=float(done),
            )
        )

    def sample(self, batch_size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        batch = random.sample(self.buffer, batch_size)
        states = np.stack([t.state for t in batch], axis=0)
        actions = np.array([t.action for t in batch], dtype=np.int64)
        rewards = np.array([t.reward for t in batch], dtype=np.float32)
        next_states = np.stack([t.next_state for t in batch], axis=0)
        dones = np.array([t.done for t in batch], dtype=np.float32)
        return states, actions, rewards, next_states, dones

    def __len__(self) -> int:
        return len(self.buffer)

    def state_dict(self) -> Dict[str, Any]:
        return {
            "capacity": int(self.capacity),
            "transitions": [
                {
                    "state": t.state,
                    "action": int(t.action),
                    "reward": float(t.reward),
                    "next_state": t.next_state,
                    "done": float(t.done),
                }
                for t in self.buffer
            ],
        }

    def load_state_dict(self, state: Dict[str, Any]) -> None:
        capacity = int(state.get("capacity", self.capacity))
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        for item in state.get("transitions", []):
            if isinstance(item, Transition):
                transition = item
            else:
                transition = Transition(
                    state=np.asarray(item["state"], dtype=np.float32),
                    action=int(item["action"]),
                    reward=float(item["reward"]),
                    next_state=np.asarray(item["next_state"], dtype=np.float32),
                    done=float(item["done"]),
                )
            self.buffer.append(transition)


class D3QNAgent:
    """Dueling Double DQN agent with soft target updates."""

    def __init__(
        self,
        env: gym.Env,
        config: Dict,
        log_dir: str = "logs",
        model_dir: str = "models",
    ):
        self.env = env
        self.config = config
        self.log_dir = log_dir
        self.model_dir = model_dir

        os.makedirs(log_dir, exist_ok=True)
        os.makedirs(model_dir, exist_ok=True)

        d3qn_cfg = config.get("agent", {}).get("d3qn", {})
        agent_cfg = config.get("agent", {})
        training_cfg = config.get("training", {})
        coordination_cfg = config.get("coordination", {})

        seed = int(training_cfg.get("seed", 42))
        deterministic = bool(training_cfg.get("deterministic", True))
        _set_global_seed(seed, deterministic=deterministic)
        self.seed = seed
        self.deterministic = deterministic

        preferred_device = agent_cfg.get("device", "cuda")
        self.device = torch.device(_setup_gpu(preferred_device))

        self.graph_enabled = bool(coordination_cfg.get("graph_enabled", False))
        self.graph_context_dim = int(coordination_cfg.get("graph_context_dim", 0)) if self.graph_enabled else 0
        self.graph_debug = bool(coordination_cfg.get("debug", False))
        self._graph_context: Optional[np.ndarray] = None
        self._resume_checkpoint: Optional[Dict[str, Any]] = None
        self._resume_env_state_path: Optional[str] = None
        self._resume_runtime_state: Dict[str, Any] = {}
        self._resume_step: int = 0
        self.global_step: int = 0
        self._last_runtime_state: Dict[str, Any] = {}

        if not isinstance(env.action_space, gym.spaces.Discrete):
            raise ValueError("D3QNAgent currently supports only Discrete action spaces.")
        if not isinstance(env.observation_space, gym.spaces.Box):
            raise ValueError("D3QNAgent currently supports only Box observation spaces.")

        self.state_dim = int(np.prod(env.observation_space.shape)) + int(self.graph_context_dim)
        self.action_dim = int(env.action_space.n)

        hidden_dim = d3qn_cfg.get("hidden_dim", 256)
        self.online_net = DuelingQNetwork(self.state_dim, self.action_dim, hidden_dim).to(self.device)
        self.target_net = DuelingQNetwork(self.state_dim, self.action_dim, hidden_dim).to(self.device)
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()

        self.learning_rate = d3qn_cfg.get("learning_rate", agent_cfg.get("learning_rate", 3e-4))
        self.gamma = d3qn_cfg.get("gamma", agent_cfg.get("gamma", 0.99))
        self.batch_size = d3qn_cfg.get("batch_size", 128)
        self.train_freq = d3qn_cfg.get("train_freq", 4)
        self.gradient_steps = d3qn_cfg.get("gradient_steps", 1)
        self.learning_starts = d3qn_cfg.get("learning_starts", 1000)
        self.max_grad_norm = d3qn_cfg.get("max_grad_norm", 10.0)
        self.tau = d3qn_cfg.get("tau", 0.005)
        self.fail_on_nan = bool(training_cfg.get("fail_on_nan", False))

        self.epsilon_start = d3qn_cfg.get("epsilon_start", 1.0)
        self.epsilon_end = d3qn_cfg.get("epsilon_end", 0.05)
        self.exploration_fraction = d3qn_cfg.get("exploration_fraction", 0.2)
        self.epsilon = self.epsilon_start

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=self.learning_rate)
        self.replay_buffer = ReplayBuffer(d3qn_cfg.get("buffer_size", 100000))

    def _capture_seed_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "numpy_random": np.random.get_state(),
            "torch_random": torch.get_rng_state(),
        }
        if torch.cuda.is_available():
            state["torch_cuda_random_all"] = torch.cuda.get_rng_state_all()
        return state

    def _restore_seed_state(self, seed_state: Optional[Dict[str, Any]]) -> None:
        if not seed_state:
            return
        try:
            np.random.set_state(seed_state["numpy_random"])
        except Exception:
            pass
        try:
            torch.set_rng_state(seed_state["torch_random"])
        except Exception:
            pass
        if torch.cuda.is_available() and seed_state.get("torch_cuda_random_all") is not None:
            try:
                torch.cuda.set_rng_state_all(seed_state["torch_cuda_random_all"])
            except Exception:
                pass

    def _capture_runtime_state(
        self,
        obs: np.ndarray,
        step: int,
        episode_reward: float,
        episode_idx: int,
        best_eval_reward: float,
    ) -> Dict[str, Any]:
        runtime_state: Dict[str, Any] = {
            "current_observation": np.asarray(obs, dtype=np.float32),
            "episode_reward": float(episode_reward),
            "episode_idx": int(episode_idx),
            "best_eval_reward": float(best_eval_reward),
            "step": int(step),
            "graph_context": None if self._graph_context is None else np.asarray(self._graph_context, dtype=np.float32),
        }
        env_attrs = [
            "_step_count",
            "_current_phase_idx",
            "_time_since_change",
            "_is_yellow",
            "_episode_waiting_time",
            "_episode_queue_length",
            "_episode_throughput",
            "_episode_rewards",
            "_prev_waiting_time",
            "_phase_changes",
        ]
        runtime_state["env_internal"] = {}
        for attr in env_attrs:
            if hasattr(self.env, attr):
                value = getattr(self.env, attr)
                if isinstance(value, np.generic):
                    value = value.item()
                runtime_state["env_internal"][attr] = value
        return runtime_state

    def _apply_runtime_state(self, runtime_state: Optional[Dict[str, Any]]) -> None:
        if not runtime_state:
            return
        graph_context = runtime_state.get("graph_context")
        self.set_graph_context(graph_context if graph_context is not None else None)
        env_internal = runtime_state.get("env_internal", {})
        for attr, value in env_internal.items():
            if hasattr(self.env, attr):
                try:
                    setattr(self.env, attr, value)
                except Exception:
                    pass

    def _snapshot_sumo_state(self, target_path: Optional[str] = None) -> Optional[str]:
        if not getattr(self.env, "_sumo_running", False):
            return None
        if target_path is None:
            fd, tmp_path = mkstemp(prefix="d3qn_state_", suffix=".xml")
            os.close(fd)
            target_path = tmp_path
        try:
            traci.simulation.saveState(str(target_path))
            return str(target_path)
        except Exception as exc:
            print(f"[D3QN] Failed to save SUMO state: {exc}")
            return None

    def _restore_sumo_state(self, state_path: Optional[str]) -> None:
        if not state_path:
            return
        try:
            traci.simulation.loadState(str(state_path))
        except Exception as exc:
            print(f"[D3QN] Failed to restore SUMO state: {exc}")

    def _capture_training_snapshot(
        self,
        obs: np.ndarray,
        step: int,
        episode_reward: float,
        episode_idx: int,
        best_eval_reward: float,
    ) -> Dict[str, Any]:
        runtime_state = self._capture_runtime_state(obs, step, episode_reward, episode_idx, best_eval_reward)
        state_path = self._snapshot_sumo_state()
        if state_path is not None:
            runtime_state["env_state_path"] = state_path
        return runtime_state

    def _restore_training_snapshot(self, snapshot: Dict[str, Any]) -> np.ndarray:
        env_state_path = snapshot.get("env_state_path")
        if env_state_path and not getattr(self.env, "_sumo_running", False):
            try:
                self.env.reset(seed=self.seed)
            except Exception:
                pass
        self._restore_sumo_state(env_state_path)
        self._apply_runtime_state(snapshot)
        if env_state_path and env_state_path != self._resume_env_state_path:
            try:
                os.remove(env_state_path)
            except OSError:
                pass
        current_obs = snapshot.get("current_observation")
        if current_obs is None:
            current_obs = self.env._get_state()
        return np.asarray(current_obs, dtype=np.float32)

    def _checkpoint_payload(self, step: int, runtime_state: Dict[str, Any]) -> Dict[str, Any]:
        seed_state = self._capture_seed_state()
        return {
            "model": self.online_net.state_dict(),
            "target_model": self.target_net.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "replay_buffer": self.replay_buffer.state_dict(),
            "epsilon": float(self.epsilon),
            "step": int(step),
            "seed_state": seed_state,
            "runtime_state": runtime_state,
            "state_dim": int(self.state_dim),
            "action_dim": int(self.action_dim),
            "seed": int(self.seed),
            "deterministic": bool(self.deterministic),
        }

    def save_checkpoint(
        self,
        path: str,
        *,
        step: int,
        runtime_state: Dict[str, Any],
    ) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        checkpoint = self._checkpoint_payload(step=step, runtime_state=runtime_state)
        checkpoint["env_state_path"] = self._snapshot_sumo_state(str(Path(path).with_suffix(".sumo-state.xml")))
        torch.save(checkpoint, path)
        print(f"[D3QN] Checkpoint saved to {path}")

    def load_checkpoint(self, path: str) -> Dict[str, Any]:
        ckpt = torch.load(path, map_location=self.device, weights_only=False)
        seed_state = ckpt.get("seed_state")
        model_state = ckpt.get("model", ckpt.get("online_state_dict"))
        target_state = ckpt.get("target_model", ckpt.get("target_state_dict", model_state))
        optimizer_state = ckpt.get("optimizer", ckpt.get("optimizer_state_dict"))
        replay_state = ckpt.get("replay_buffer")

        if model_state is None:
            raise ValueError(f"[D3QN] Invalid checkpoint: missing model state in {path}")

        checkpoint_state_dim = int(ckpt.get("state_dim", self.state_dim))
        checkpoint_action_dim = int(ckpt.get("action_dim", self.action_dim))
        if checkpoint_state_dim != self.state_dim or checkpoint_action_dim != self.action_dim:
            raise ValueError(
                f"[D3QN] Checkpoint shape mismatch for {path}: "
                f"expected state_dim={self.state_dim}, action_dim={self.action_dim}, "
                f"got state_dim={checkpoint_state_dim}, action_dim={checkpoint_action_dim}"
            )

        self.online_net.load_state_dict(model_state)
        self.target_net.load_state_dict(target_state)
        if optimizer_state is not None:
            self.optimizer.load_state_dict(optimizer_state)
        if not isinstance(replay_state, dict):
            raise ValueError(f"[D3QN] Invalid checkpoint: replay_buffer must be a state_dict in {path}")
        self.replay_buffer.load_state_dict(replay_state)
        self._restore_seed_state(seed_state)
        assert len(self.replay_buffer) > 0, "Replay buffer lost during resume"

        self.epsilon = float(ckpt.get("epsilon", self.epsilon_end))
        self.seed = int(ckpt.get("seed", self.seed))
        self.deterministic = bool(ckpt.get("deterministic", self.deterministic))
        self._resume_checkpoint = ckpt
        self._resume_env_state_path = ckpt.get("env_state_path") or ckpt.get("runtime_state", {}).get("env_state_path")
        self._resume_runtime_state = ckpt.get("runtime_state", {}) or {}
        self._resume_step = int(ckpt.get("step", 0))
        self.global_step = self._resume_step
        self.online_net.train()
        self.target_net.eval()

        print(f"[D3QN] Checkpoint loaded from {path} (step={self._resume_step}, epsilon={self.epsilon:.4f})")
        return ckpt

    def _flatten_obs(self, obs: np.ndarray) -> np.ndarray:
        base = np.asarray(obs, dtype=np.float32).reshape(-1)
        if not self.graph_enabled or self.graph_context_dim <= 0:
            flat = base
        else:
            if self._graph_context is None:
                graph_ctx = np.zeros((self.graph_context_dim,), dtype=np.float32)
            else:
                graph_ctx = np.asarray(self._graph_context, dtype=np.float32).reshape(-1)
                if graph_ctx.size < self.graph_context_dim:
                    pad = np.zeros((self.graph_context_dim - graph_ctx.size,), dtype=np.float32)
                    graph_ctx = np.concatenate([graph_ctx, pad], axis=0)
                elif graph_ctx.size > self.graph_context_dim:
                    graph_ctx = graph_ctx[: self.graph_context_dim]

            flat = np.concatenate([base, graph_ctx], axis=0)
            
        assert flat.shape[-1] == self.state_dim, f"State shape mismatch! Expected {self.state_dim}, got {flat.shape[-1]}"
        if self.graph_debug:
            print(f"[D3QN][graph] base={base.shape} flat={flat.shape}")
        return flat

    def set_graph_context(self, context: Optional[np.ndarray]) -> None:
        """Set per-decision graph context appended to the local observation."""
        if context is None:
            self._graph_context = None
            return
        self._graph_context = np.asarray(context, dtype=np.float32).reshape(-1)

    def _select_action(self, obs: np.ndarray, deterministic: bool = False) -> int:
        if (not deterministic) and random.random() < self.epsilon:
            return int(self.env.action_space.sample())

        obs_t = torch.as_tensor(self._flatten_obs(obs), dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            q_values = self.online_net(obs_t)
        return int(torch.argmax(q_values, dim=1).item())

    def _update_epsilon(self, step: int, total_timesteps: int) -> None:
        decay_steps = max(1, int(total_timesteps * self.exploration_fraction))
        if step >= decay_steps:
            self.epsilon = self.epsilon_end
            return
        frac = step / decay_steps
        self.epsilon = self.epsilon_start + frac * (self.epsilon_end - self.epsilon_start)

    def _soft_update_target(self) -> None:
        for target_param, online_param in zip(self.target_net.parameters(), self.online_net.parameters()):
            target_param.data.mul_(1.0 - self.tau)
            target_param.data.add_(self.tau * online_param.data)

    def _optimize_step(self) -> Optional[Dict[str, float]]:
        if len(self.replay_buffer) < self.batch_size:
            return None

        states, actions, rewards, next_states, dones = self.replay_buffer.sample(self.batch_size)

        states_t = torch.as_tensor(states, dtype=torch.float32, device=self.device)
        actions_t = torch.as_tensor(actions, dtype=torch.int64, device=self.device).unsqueeze(1)
        rewards_t = torch.as_tensor(rewards, dtype=torch.float32, device=self.device)
        next_states_t = torch.as_tensor(next_states, dtype=torch.float32, device=self.device)
        dones_t = torch.as_tensor(dones, dtype=torch.float32, device=self.device)

        q_values = self.online_net(states_t).gather(1, actions_t).squeeze(1)

        with torch.no_grad():
            # Double DQN: online net selects action, target net evaluates it.
            next_actions = self.online_net(next_states_t).argmax(dim=1, keepdim=True)
            next_q = self.target_net(next_states_t).gather(1, next_actions).squeeze(1)
            targets = rewards_t + self.gamma * (1.0 - dones_t) * next_q

        if not torch.isfinite(q_values).all() or not torch.isfinite(targets).all():
            msg = "[D3QN] Non-finite Q-values or targets detected during optimization"
            if self.fail_on_nan:
                raise RuntimeError(msg)
            print(msg)
            return None

        loss = F.smooth_l1_loss(q_values, targets)
        if not torch.isfinite(loss):
            msg = "[D3QN] Non-finite loss detected during optimization"
            if self.fail_on_nan:
                raise RuntimeError(msg)
            print(msg)
            return None

        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online_net.parameters(), self.max_grad_norm)
        self.optimizer.step()

        self._soft_update_target()

        return {
            "loss": float(loss.item()),
            "q_mean": float(q_values.mean().item()),
            "target_mean": float(targets.mean().item()),
        }

    def train(
        self,
        total_timesteps: int = 500000,
        eval_freq: int = 10000,
        n_eval_episodes: int = 5,
        save_freq: int = 50000,
        callback: Optional[Callable] = None,
        start_step: int = 0,
    ) -> Dict:
        history = {
            "episodes": [],
            "eval": [],
            "loss": [],
            "epsilon": [],
            "incomplete_run": False,
            "start_step": int(start_step),
        }

        print(f"[D3QN] Starting training for {total_timesteps:,} timesteps...")
        print(f"[D3QN] Device: {self.device}")
        print(f"[D3QN] Seed={self.seed} | Deterministic={self.deterministic}")

        if start_step > 0 and self._resume_checkpoint is not None:
            snapshot = dict(self._resume_runtime_state)
            if self._resume_env_state_path:
                snapshot["env_state_path"] = self._resume_env_state_path
            obs = self._restore_training_snapshot(snapshot)
            episode_reward = float(snapshot.get("episode_reward", 0.0))
            episode_idx = int(snapshot.get("episode_idx", 0))
            best_eval_reward = float(snapshot.get("best_eval_reward", -float("inf")))
        else:
            obs, _ = self.env.reset(seed=self.seed)
            episode_reward = 0.0
            episode_idx = 0
            best_eval_reward = -float("inf")
        losses: List[float] = []

        checkpoint_dir = os.path.join(self.model_dir, "checkpoints")
        best_dir = os.path.join(self.model_dir, "best")
        os.makedirs(checkpoint_dir, exist_ok=True)
        os.makedirs(best_dir, exist_ok=True)
        checkpoint_path = os.path.join(self.model_dir, "checkpoint.pt")
        self.global_step = int(max(0, start_step - 1))

        try:
            for step in range(max(1, start_step), total_timesteps + 1):
                self.global_step = int(step)
                step_num = int(step)
                action = self._select_action(obs, deterministic=False)
                next_obs, reward, terminated, truncated, info = self.env.step(action)
                done = terminated or truncated

                self.replay_buffer.push(
                    self._flatten_obs(obs),
                    action,
                    reward,
                    self._flatten_obs(next_obs),
                    float(done),
                )

                obs = next_obs
                episode_reward += float(reward)

                if step_num >= self.learning_starts and step_num % self.train_freq == 0:
                    for _ in range(self.gradient_steps):
                        stats = self._optimize_step()
                        if stats:
                            losses.append(stats["loss"])
                            history["loss"].append(
                                {
                                    "step": step_num,
                                    "loss": float(stats["loss"]),
                                    "q_mean": float(stats["q_mean"]),
                                    "target_mean": float(stats["target_mean"]),
                                }
                            )

                self._update_epsilon(step_num, total_timesteps)
                history["epsilon"].append({"step": step_num, "epsilon": float(self.epsilon)})

                if done:
                    episode_idx += 1
                    history["episodes"].append(
                        {
                            "episode": episode_idx,
                            "step": step_num,
                            "reward": float(episode_reward),
                        }
                    )
                    print(
                        f"[D3QN] Episode {episode_idx:04d} | "
                        f"Reward={episode_reward:8.2f} | "
                        f"Buffer={len(self.replay_buffer):6d} | "
                        f"Epsilon={self.epsilon:.3f}"
                    )
                    obs, _ = self.env.reset(seed=self.seed)
                    episode_reward = 0.0

                if step_num % eval_freq == 0:
                    eval_snapshot = self._capture_training_snapshot(obs, step_num, episode_reward, episode_idx, best_eval_reward)
                    try:
                        eval_results = self.evaluate(n_episodes=n_eval_episodes)
                    finally:
                        obs = self._restore_training_snapshot(eval_snapshot)
                        episode_reward = float(eval_snapshot.get("episode_reward", 0.0))
                        episode_idx = int(eval_snapshot.get("episode_idx", 0))
                        best_eval_reward = float(eval_snapshot.get("best_eval_reward", best_eval_reward))

                    mean_reward = eval_results["mean_reward"]
                    history["eval"].append(
                        {
                            "step": step_num,
                            "mean_reward": float(eval_results.get("mean_reward", 0.0)),
                            "std_reward": float(eval_results.get("std_reward", 0.0)),
                            "mean_length": float(eval_results.get("mean_length", 0.0)),
                            "avg_waiting_time": float(eval_results.get("avg_waiting_time", 0.0)),
                            "avg_queue_length": float(eval_results.get("avg_queue_length", 0.0)),
                            "avg_throughput": float(eval_results.get("avg_throughput", 0.0)),
                            "epsilon": float(self.epsilon),
                        }
                    )
                    print(
                        f"[D3QN] Eval @ {step_num:>7d} | "
                        f"MeanReward={mean_reward:8.2f} | "
                        f"MeanLen={eval_results['mean_length']:.1f}"
                    )
                    if mean_reward > best_eval_reward:
                        best_eval_reward = mean_reward
                        self.save(os.path.join(best_dir, "best_model.pt"))
                        print(f"[D3QN] New best model saved (reward={best_eval_reward:.2f})")

                self._last_runtime_state = self._capture_runtime_state(
                    obs,
                    step_num,
                    episode_reward,
                    episode_idx,
                    best_eval_reward,
                )

                if step_num % save_freq == 0:
                    self.save_checkpoint(checkpoint_path, step=step_num, runtime_state=self._last_runtime_state)

        except KeyboardInterrupt:
            history["incomplete_run"] = True
            interrupted_step = int(self.global_step)
            history["interrupted_step"] = interrupted_step
            runtime_state = self._capture_runtime_state(obs, interrupted_step, episode_reward, episode_idx, best_eval_reward)
            self._last_runtime_state = runtime_state
            self.save_checkpoint(checkpoint_path, step=interrupted_step, runtime_state=runtime_state)
            print("Checkpoint saved. Exiting safely.")
            return history

        final_path = os.path.join(self.model_dir, "d3qn_final.pt")
        self.save(final_path)
        final_runtime_state = self._capture_runtime_state(obs, total_timesteps, episode_reward, episode_idx, best_eval_reward)
        self.save_checkpoint(checkpoint_path, step=total_timesteps, runtime_state=final_runtime_state)
        if losses:
            print(f"[D3QN] Training complete. Avg recent loss: {np.mean(losses[-200:]):.6f}")
        print(f"[D3QN] Final model saved to {final_path}")
        return history

    def predict(self, observation: np.ndarray, deterministic: bool = True) -> int:
        return self._select_action(observation, deterministic=deterministic)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        ckpt = {
            "online_state_dict": self.online_net.state_dict(),
            "target_state_dict": self.target_net.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "state_dim": self.state_dim,
            "action_dim": self.action_dim,
            "epsilon": self.epsilon,
            "gamma": self.gamma,
            "tau": self.tau,
            "seed": self.seed,
            "deterministic": self.deterministic,
            "graph_enabled": self.graph_enabled,
            "graph_context_dim": self.graph_context_dim,
        }
        torch.save(ckpt, path)
        print(f"[D3QN] Model saved to {path}")

    def load(self, path: str) -> None:
        ckpt = torch.load(path, map_location=self.device, weights_only=False)
        model_state = ckpt.get("model", ckpt.get("online_state_dict"))
        target_state = ckpt.get("target_model", ckpt.get("target_state_dict", model_state))
        optimizer_state = ckpt.get("optimizer", ckpt.get("optimizer_state_dict"))
        if model_state is None:
            raise ValueError(f"[D3QN] Invalid checkpoint format: {path}")
        self.online_net.load_state_dict(model_state)
        self.target_net.load_state_dict(target_state)
        if optimizer_state is not None:
            self.optimizer.load_state_dict(optimizer_state)
        self.epsilon = float(ckpt.get("epsilon", self.epsilon_end))
        self.online_net.eval()
        self.target_net.eval()
        print(f"[D3QN] Model loaded from {path}")

    def evaluate(self, n_episodes: int = 10, render: bool = False) -> Dict:
        episode_rewards = []
        episode_lengths = []
        episode_metrics = []

        prev_epsilon = self.epsilon
        self.epsilon = 0.0

        for ep in range(n_episodes):
            obs, info = self.env.reset()
            done = False
            total_reward = 0.0
            steps = 0

            while not done:
                action = self.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = self.env.step(action)
                done = terminated or truncated
                total_reward += float(reward)
                steps += 1
                if render:
                    self.env.render()

            episode_rewards.append(total_reward)
            episode_lengths.append(steps)
            if "metrics" in info:
                episode_metrics.append(info["metrics"])

            print(f"  Episode {ep + 1}/{n_episodes}: Reward = {total_reward:.2f}")

        self.epsilon = prev_epsilon

        results = {
            "mean_reward": float(np.mean(episode_rewards)),
            "std_reward": float(np.std(episode_rewards)),
            "mean_length": float(np.mean(episode_lengths)),
            "episodes": n_episodes,
        }

        if episode_metrics:
            results["avg_waiting_time"] = float(
                np.mean([m.get("avg_waiting_time", 0) for m in episode_metrics])
            )
            results["avg_queue_length"] = float(
                np.mean([m.get("avg_queue_length", 0) for m in episode_metrics])
            )
            results["avg_throughput"] = float(
                np.mean([m.get("throughput", 0) for m in episode_metrics])
            )

        return results
