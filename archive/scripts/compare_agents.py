"""
Agent Comparison Framework
============================
Trains and evaluates multiple RL algorithms on the same environment
to produce a proper academic comparison:

  - DQN  (Deep Q-Network)
  - PPO  (Proximal Policy Optimization)
  - A2C  (Advantage Actor-Critic)
  - Random baseline
  - Fixed-timing baseline

Outputs:
  - Per-algorithm training curves (reward, waiting time, queue length)
  - Evaluation metrics table (mean ± std)
  - Convergence speed comparison
  - Statistical significance tests (Welch's t-test)
  - Saved plots + JSON results for use in reports

Usage:
  python scripts/compare_agents.py --timesteps 200000 --env single
  python scripts/compare_agents.py --timesteps 200000 --env grid
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from stable_baselines3 import DQN, PPO, A2C
from stable_baselines3.common.callbacks import EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.evaluation import evaluate_policy


def _gpu_info() -> str:
    if torch.cuda.is_available():
        return f"cuda ({torch.cuda.get_device_name(0)})"
    return "cpu"


def _create_env(env_type: str, use_gui: bool = False):
    """Create the appropriate environment."""
    if env_type == "grid":
        from ai.envs.multi_agent_env import MultiAgentSumoEnv
        return MultiAgentSumoEnv(
            net_file="networks/grid_4x4/grid_4x4.net.xml",
            route_file="networks/grid_4x4/grid_4x4.rou.xml",
            use_gui=use_gui,
            max_steps=3600,
            delta_time=5,
        )
    else:
        from ai.envs.sumo_env import SumoEnvironment
        return SumoEnvironment(
            net_file="networks/single_intersection.net.xml",
            route_file="networks/single_intersection.rou.xml",
            use_gui=use_gui,
            max_steps=3600,
            delta_time=5,
        )


# ------------------------------------------------------------------
# Baseline agents
# ------------------------------------------------------------------

class RandomAgent:
    """Random action agent — lower-bound baseline."""
    def __init__(self, action_space):
        self.action_space = action_space

    def predict(self, obs, deterministic=True):
        return self.action_space.sample(), None


class FixedTimingAgent:
    """Fixed-timing agent — cycles through phases at regular intervals."""
    def __init__(self, action_space, switch_every: int = 6):
        self.action_space = action_space
        self.switch_every = switch_every
        self._counter = 0

    def predict(self, obs, deterministic=True):
        self._counter += 1
        if self._counter % self.switch_every == 0:
            # Switch signal
            if hasattr(self.action_space, 'nvec'):
                return np.ones(len(self.action_space.nvec), dtype=int), None
            return 1, None
        # Keep current
        if hasattr(self.action_space, 'nvec'):
            return np.zeros(len(self.action_space.nvec), dtype=int), None
        return 0, None


# ------------------------------------------------------------------
# Agent Training
# ------------------------------------------------------------------

AGENT_CONFIG = {
    "DQN": {
        "class": DQN,
        "policy": "MlpPolicy",
        "kwargs": {
            "learning_rate": 3e-4,
            "buffer_size": 100000,
            "batch_size": 128,
            "gamma": 0.99,
            "exploration_fraction": 0.15,
            "exploration_final_eps": 0.05,
            "target_update_interval": 1000,
        },
    },
    "PPO": {
        "class": PPO,
        "policy": "MlpPolicy",
        "kwargs": {
            "learning_rate": 3e-4,
            "n_steps": 2048,
            "batch_size": 128,
            "n_epochs": 10,
            "gamma": 0.99,
            "clip_range": 0.2,
            "ent_coef": 0.01,
        },
    },
    "A2C": {
        "class": A2C,
        "policy": "MlpPolicy",
        "kwargs": {
            "learning_rate": 7e-4,
            "n_steps": 5,
            "gamma": 0.99,
            "ent_coef": 0.01,
        },
    },
}


def train_agent(algo_name: str, env, total_timesteps: int,
                log_dir: str, model_dir: str, device: str) -> object:
    """Train a single SB3 agent and return the model."""
    cfg = AGENT_CONFIG[algo_name]
    print(f"\n{'='*60}")
    print(f"  Training {algo_name} for {total_timesteps:,} timesteps")
    print(f"  Device: {device}")
    print(f"{'='*60}\n")

    model = cfg["class"](
        policy=cfg["policy"],
        env=env,
        verbose=1,
        tensorboard_log=log_dir,
        device=device,
        **cfg["kwargs"],
    )

    eval_callback = EvalCallback(
        Monitor(env),
        best_model_save_path=os.path.join(model_dir, algo_name, "best"),
        log_path=os.path.join(log_dir, algo_name),
        eval_freq=max(total_timesteps // 20, 1000),
        n_eval_episodes=3,
        deterministic=True,
    )

    start_time = time.time()
    model.learn(
        total_timesteps=total_timesteps,
        callback=eval_callback,
        progress_bar=True,
    )
    train_time = time.time() - start_time

    model.save(os.path.join(model_dir, algo_name, f"{algo_name}_final.zip"))
    print(f"  {algo_name} training completed in {train_time:.0f}s")

    return model, train_time


def evaluate_agent(agent, env, n_episodes: int = 10,
                   agent_name: str = "Agent") -> Dict:
    """Evaluate an agent over multiple episodes and return metrics."""
    episode_rewards = []
    episode_waits = []
    episode_queues = []
    episode_throughputs = []

    for ep in range(n_episodes):
        obs, info = env.reset()
        total_reward = 0.0
        done = False

        while not done:
            if hasattr(agent, 'predict'):
                action, _ = agent.predict(obs, deterministic=True)
            else:
                action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            done = terminated or truncated

        episode_rewards.append(total_reward)
        metrics = info.get("metrics", {})
        episode_waits.append(metrics.get("avg_waiting_time", 0))
        episode_queues.append(metrics.get("avg_queue_length", 0))
        episode_throughputs.append(metrics.get("throughput", 0))
        print(f"    {agent_name} Episode {ep+1}/{n_episodes}: "
              f"R={total_reward:.1f}, Wait={episode_waits[-1]:.1f}s")

    return {
        "agent": agent_name,
        "reward_mean": float(np.mean(episode_rewards)),
        "reward_std": float(np.std(episode_rewards)),
        "waiting_time_mean": float(np.mean(episode_waits)),
        "waiting_time_std": float(np.std(episode_waits)),
        "queue_length_mean": float(np.mean(episode_queues)),
        "queue_length_std": float(np.std(episode_queues)),
        "throughput_mean": float(np.mean(episode_throughputs)),
        "throughput_std": float(np.std(episode_throughputs)),
        "n_episodes": n_episodes,
    }


# ------------------------------------------------------------------
# Statistical testing
# ------------------------------------------------------------------

def welch_t_test(mean1, std1, n1, mean2, std2, n2) -> Dict:
    """Welch's t-test for comparing two agent distributions."""
    from scipy import stats
    se1 = std1 ** 2 / max(n1, 1)
    se2 = std2 ** 2 / max(n2, 1)
    se_diff = np.sqrt(se1 + se2)
    if se_diff < 1e-10:
        return {"t_statistic": 0.0, "p_value": 1.0, "significant": False}

    t_stat = (mean1 - mean2) / se_diff
    # Welch-Satterthwaite degrees of freedom
    df_num = (se1 + se2) ** 2
    df_den = (se1 ** 2 / max(n1 - 1, 1)) + (se2 ** 2 / max(n2 - 1, 1))
    df = df_num / max(df_den, 1e-10)
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))
    return {
        "t_statistic": float(t_stat),
        "p_value": float(p_value),
        "significant": p_value < 0.05,
        "degrees_of_freedom": float(df),
    }


# ------------------------------------------------------------------
# Plotting
# ------------------------------------------------------------------

def generate_comparison_plots(results: List[Dict], output_dir: str):
    """Generate comparison charts from evaluation results."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[WARN] matplotlib not installed. Skipping plots.")
        return

    agents = [r["agent"] for r in results]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("NEXUS-ATMS — RL Agent Comparison", fontsize=16, fontweight="bold")

    # 1. Reward comparison
    ax = axes[0, 0]
    means = [r["reward_mean"] for r in results]
    stds = [r["reward_std"] for r in results]
    bars = ax.bar(agents, means, yerr=stds, color=colors[:len(agents)],
                  capsize=5, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Mean Episodic Reward")
    ax.set_title("Cumulative Reward (higher = better)")
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)

    # 2. Waiting time comparison
    ax = axes[0, 1]
    means = [r["waiting_time_mean"] for r in results]
    stds = [r["waiting_time_std"] for r in results]
    ax.bar(agents, means, yerr=stds, color=colors[:len(agents)],
           capsize=5, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Avg Waiting Time (s)")
    ax.set_title("Average Waiting Time (lower = better)")

    # 3. Queue length comparison
    ax = axes[1, 0]
    means = [r["queue_length_mean"] for r in results]
    stds = [r["queue_length_std"] for r in results]
    ax.bar(agents, means, yerr=stds, color=colors[:len(agents)],
           capsize=5, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Avg Queue Length")
    ax.set_title("Average Queue Length (lower = better)")

    # 4. Throughput comparison
    ax = axes[1, 1]
    means = [r["throughput_mean"] for r in results]
    stds = [r["throughput_std"] for r in results]
    ax.bar(agents, means, yerr=stds, color=colors[:len(agents)],
           capsize=5, edgecolor="black", linewidth=0.5)
    ax.set_ylabel("Throughput (vehicles)")
    ax.set_title("Total Throughput (higher = better)")

    plt.tight_layout()
    plot_path = os.path.join(output_dir, "agent_comparison.png")
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Comparison plots saved to {plot_path}")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compare RL agents for traffic control")
    parser.add_argument("--env", choices=["single", "grid"], default="single",
                        help="Environment type")
    parser.add_argument("--timesteps", type=int, default=200000,
                        help="Training timesteps per agent")
    parser.add_argument("--eval-episodes", type=int, default=5,
                        help="Evaluation episodes per agent")
    parser.add_argument("--agents", nargs="+", default=["DQN", "PPO", "A2C"],
                        choices=["DQN", "PPO", "A2C"],
                        help="RL agents to train and compare")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--skip-baselines", action="store_true",
                        help="Skip random/fixed-timing baselines")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("results", f"comparison_{timestamp}")
    log_dir = os.path.join(output_dir, "logs")
    model_dir = os.path.join(output_dir, "models")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  NEXUS-ATMS — Agent Comparison Framework")
    print("=" * 60)
    print(f"  Environment : {args.env}")
    print(f"  Device      : {_gpu_info()}")
    print(f"  Timesteps   : {args.timesteps:,}")
    print(f"  Agents      : {', '.join(args.agents)}")
    print(f"  Output      : {output_dir}")
    print("=" * 60)

    all_results = []
    train_times = {}

    # --- Baselines ---
    if not args.skip_baselines:
        for baseline_name, BaselineClass in [
            ("Random", RandomAgent),
            ("FixedTiming", FixedTimingAgent),
        ]:
            print(f"\n  Evaluating {baseline_name} baseline...")
            env = _create_env(args.env, use_gui=args.gui)
            agent = BaselineClass(env.action_space)
            result = evaluate_agent(agent, env, n_episodes=args.eval_episodes,
                                    agent_name=baseline_name)
            result["train_time_s"] = 0
            all_results.append(result)
            train_times[baseline_name] = 0
            env.close()

    # --- RL Agents ---
    for algo_name in args.agents:
        env = _create_env(args.env, use_gui=args.gui)
        try:
            model, t_time = train_agent(
                algo_name, env, args.timesteps, log_dir, model_dir, device,
            )
            train_times[algo_name] = t_time

            print(f"\n  Evaluating {algo_name}...")
            result = evaluate_agent(model, env, n_episodes=args.eval_episodes,
                                    agent_name=algo_name)
            result["train_time_s"] = t_time
            all_results.append(result)
        except KeyboardInterrupt:
            print(f"\n  {algo_name} interrupted. Skipping.")
        finally:
            env.close()

    # --- Statistical tests ---
    print(f"\n{'='*60}")
    print("  Statistical Significance (Welch's t-test on waiting time)")
    print(f"{'='*60}")

    stat_tests = {}
    best_rl = None
    best_rl_wait = float("inf")
    for r in all_results:
        if r["agent"] in args.agents and r["waiting_time_mean"] < best_rl_wait:
            best_rl = r
            best_rl_wait = r["waiting_time_mean"]

    if best_rl:
        for r in all_results:
            if r["agent"] != best_rl["agent"]:
                try:
                    test = welch_t_test(
                        best_rl["waiting_time_mean"], best_rl["waiting_time_std"],
                        best_rl["n_episodes"],
                        r["waiting_time_mean"], r["waiting_time_std"],
                        r["n_episodes"],
                    )
                    key = f"{best_rl['agent']}_vs_{r['agent']}"
                    stat_tests[key] = test
                    sig = "YES (p<0.05)" if test["significant"] else "NO"
                    print(f"  {best_rl['agent']} vs {r['agent']}: "
                          f"t={test['t_statistic']:.3f}, p={test['p_value']:.4f}, "
                          f"significant={sig}")
                except ImportError:
                    print("  (scipy not installed — skipping significance tests)")
                    break

    # --- Summary table ---
    print(f"\n{'='*60}")
    print("  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Agent':<15} {'Reward':>10} {'Wait(s)':>10} {'Queue':>10} "
          f"{'Throughput':>10} {'TrainTime':>10}")
    print(f"  {'-'*65}")
    for r in all_results:
        print(f"  {r['agent']:<15} {r['reward_mean']:>10.1f} "
              f"{r['waiting_time_mean']:>10.1f} {r['queue_length_mean']:>10.1f} "
              f"{r['throughput_mean']:>10.0f} {r.get('train_time_s', 0):>9.0f}s")

    # --- Save results ---
    output = {
        "timestamp": timestamp,
        "environment": args.env,
        "timesteps_per_agent": args.timesteps,
        "device": _gpu_info(),
        "results": all_results,
        "statistical_tests": stat_tests,
        "train_times": train_times,
    }
    results_path = os.path.join(output_dir, "comparison_results.json")
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to {results_path}")

    # --- Plots ---
    generate_comparison_plots(all_results, output_dir)

    print(f"\n{'='*60}")
    print("  Comparison complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
