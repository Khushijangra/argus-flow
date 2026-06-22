"""
Training Script for Smart Traffic Management System
Train DQN or PPO agent on SUMO traffic environment.
"""

import argparse
import json
import os
import random
import sys
import yaml
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ai.envs.sumo_env import SumoEnvironment
from ai.rl.dqn import DQNAgent
from ai.rl.d3qn import D3QNAgent
from ai.rl.ppo import PPOAgent
from ai.utils.logger import setup_logger
from ai.utils.metrics import MetricsTracker
from ai.utils.visualization import plot_reward, plot_epsilon, plot_loss


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file with optional `extends` support."""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    base_path = cfg.get("extends")
    if not base_path:
        return cfg

    parent = Path(config_path).parent / str(base_path)
    with open(parent, "r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f) or {}

    cfg.pop("extends", None)
    return deep_update(base_cfg, cfg)


def deep_update(base: dict, override: dict) -> dict:
    """Recursively update dictionary values from override into base."""
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base


def set_global_seed(seed: int, deterministic: bool = True) -> None:
    """Set reproducible global seeds for python, numpy, and torch."""
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


def resolved_device_for_agent(agent_name: str, config: dict) -> str:
    """Resolve runtime device policy for agent type."""
    policy = config.get("device_policy", {})
    if agent_name in ("dqn", "ppo"):
        return policy.get("sb3", "cpu")
    return policy.get("d3qn", "cuda")


def main():
    parser = argparse.ArgumentParser(
        description="Train RL agent for traffic signal control"
    )
    parser.add_argument(
        "--agent",
        type=str,
        default="ppo",
        choices=["dqn", "d3qn", "ppo"],
        help="Agent type: dqn, d3qn, or ppo (default: ppo)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/default.yaml",
        help="Path to config file",
    )
    parser.add_argument(
        "--timesteps",
        type=int,
        default=None,
        help="Total training timesteps (overrides config)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        choices=["rush_hour", "normal", "night"],
        help="Traffic scenario to use",
    )
    parser.add_argument("--gui", action="store_true", help="Use SUMO GUI")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Quick demo mode (50K timesteps)",
    )
    parser.add_argument(
        "--graph-enabled",
        action="store_true",
        help="Enable graph coordination mode for compatible agents/envs",
    )
    parser.add_argument(
        "--graph-disabled",
        action="store_true",
        help="Force-disable graph coordination mode",
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume D3QN training from a checkpoint.pt file",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Override the generated run name (e.g. anomaly_v1)",
    )

    args = parser.parse_args()
    log = setup_logger("train")

    # Load config
    config = load_config(args.config)

    # Reproducibility configuration
    deterministic = bool(config.get("training", {}).get("deterministic", True))
    set_global_seed(args.seed, deterministic=deterministic)

    # Apply scenario config if specified
    if args.scenario:
        scenario_path = f"configs/scenarios/{args.scenario}.yaml"
        if os.path.exists(scenario_path):
            scenario_cfg = load_config(scenario_path)
            config = deep_update(config, scenario_cfg)
            log.info(f"Loaded scenario: {args.scenario}")
        else:
            log.warning(f"Scenario file not found: {scenario_path}")

    # Override config from CLI
    if args.demo:
        config["training"]["total_timesteps"] = 50000
        log.info("Demo mode: 50K timesteps")
    if args.timesteps:
        config["training"]["total_timesteps"] = args.timesteps
    config["training"]["seed"] = args.seed
    config["training"]["deterministic"] = deterministic

    config.setdefault("coordination", {})
    if args.graph_enabled and args.graph_disabled:
        log.warning("Both --graph-enabled and --graph-disabled were provided; keeping config value.")
    elif args.graph_enabled:
        config["coordination"]["graph_enabled"] = True
    elif args.graph_disabled:
        config["coordination"]["graph_enabled"] = False

    # Apply resolved device policy to agent section consumed by agents.
    config.setdefault("agent", {})
    config["agent"]["device"] = resolved_device_for_agent(args.agent, config)

    # Directories
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.run_name:
        run_name = args.run_name
    else:
        run_name = f"{args.agent}_{timestamp}"
    log_dir = os.path.join("logs", run_name)
    model_dir = os.path.join("models", run_name)
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(model_dir, exist_ok=True)

    log.info("=" * 60)
    log.info("Smart Traffic Management System — Training")
    log.info("=" * 60)
    log.info(f"Agent      : {args.agent.upper()}")
    log.info(f"Timesteps  : {config['training']['total_timesteps']:,}")
    log.info(f"Seed       : {args.seed}")
    log.info(f"Determinism: {deterministic}")
    log.info(f"Device pol.: {config['agent']['device']} (agent={args.agent})")
    log.info(f"Graph mode : {bool(config.get('coordination', {}).get('graph_enabled', False))}")
    if args.resume:
        log.info(f"Resume    : {args.resume}")
    log.info(f"Log Dir    : {log_dir}")
    log.info(f"Model Dir  : {model_dir}")
    log.info("=" * 60)

    # Persist run metadata for reproducibility.
    run_metadata = {
        "timestamp": timestamp,
        "agent": args.agent,
        "seed": args.seed,
        "deterministic": deterministic,
        "device_policy": config.get("device_policy", {}),
        "resolved_agent_device": config["agent"]["device"],
        "graph_enabled": bool(config.get("coordination", {}).get("graph_enabled", False)),
        "graph_context_dim": int(config.get("coordination", {}).get("graph_context_dim", 0)),
        "timesteps": int(config["training"]["total_timesteps"]),
        "eval_freq": int(config["training"]["eval_freq"]),
        "n_eval_episodes": int(config["training"]["n_eval_episodes"]),
        "save_freq": int(config["training"]["save_freq"]),
        "scenario": args.scenario,
        "gui": bool(args.gui),
    }
    with open(os.path.join(log_dir, "run_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(run_metadata, f, indent=2)

    # Network files
    net_file = config["environment"]["network_file"]
    route_file = config["environment"]["route_file"]

    if not os.path.exists(net_file):
        log.error(f"Network file not found: {net_file}")
        sys.exit(1)
    if not os.path.exists(route_file):
        log.error(f"Route file not found: {route_file}")
        sys.exit(1)

    # Create environment
    log.info("Initialising SUMO environment...")
    env = SumoEnvironment(
        net_file=net_file,
        route_file=route_file,
        use_gui=args.gui,
        max_steps=config["sumo"]["max_steps"],
        delta_time=config["sumo"]["delta_time"],
        yellow_time=config["sumo"]["yellow_time"],
        min_green=config["sumo"]["min_green"],
        max_green=config["sumo"]["max_green"],
        reward_type=config["environment"]["reward"]["type"],
    )

    # Create agent
    log.info(f"Creating {args.agent.upper()} agent...")
    if args.agent == "dqn":
        AgentClass = DQNAgent
    elif args.agent == "d3qn":
        AgentClass = D3QNAgent
    else:
        AgentClass = PPOAgent
    agent = AgentClass(
        env=env, config=config, log_dir=log_dir, model_dir=model_dir
    )
    resume_step = 0
    if args.resume:
        if args.agent != "d3qn":
            log.warning("--resume is only supported for D3QN; ignoring for SB3 agents.")
        elif not os.path.exists(args.resume):
            log.error(f"Resume checkpoint not found: {args.resume}")
            env.close()
            sys.exit(1)
        else:
            checkpoint = agent.load_checkpoint(args.resume)
            resume_step = int(checkpoint.get("step", 0)) + 1
            config["training"]["seed"] = int(checkpoint.get("seed", config["training"]["seed"]))
            config["training"]["deterministic"] = bool(
                checkpoint.get("deterministic", config["training"]["deterministic"])
            )
            log.info(f"Resuming from step {resume_step:,}")

    # Train
    log.info("Starting training... (Ctrl+C to stop early)")
    train_history = None
    try:
        train_kwargs = {
            "total_timesteps": config["training"]["total_timesteps"],
            "eval_freq": config["training"]["eval_freq"],
            "n_eval_episodes": config["training"]["n_eval_episodes"],
            "save_freq": config["training"]["save_freq"],
        }
        if args.agent == "d3qn":
            train_kwargs["start_step"] = int(resume_step)
        train_history = agent.train(**train_kwargs)
        if isinstance(train_history, dict):
            plot_reward(train_history, save_dir="results/plots")
            print("Saved: reward_vs_steps.png")
            plot_epsilon(train_history, save_dir="results/plots")
            print("Saved: epsilon_decay.png")
            plot_loss(train_history, save_dir="results/plots")
            print("Saved: loss_curve.png")
    except KeyboardInterrupt:
        log.warning("Training interrupted by user.")
        if args.agent == "d3qn":
            checkpoint_path = os.path.join(model_dir, "checkpoint.pt")
            runtime_state = dict(getattr(agent, "_last_runtime_state", {}) or {})
            if not runtime_state:
                runtime_state = {
                    "step": int(getattr(agent, "global_step", 0)),
                    "episode_reward": 0.0,
                    "episode_idx": 0,
                    "best_eval_reward": float("-inf"),
                    "env_internal": {},
                }
            agent.save_checkpoint(
                checkpoint_path,
                step=int(getattr(agent, "global_step", 0)),
                runtime_state=runtime_state,
            )
        else:
            interrupted_ext = ".zip"
            agent.save(os.path.join(model_dir, f"{args.agent}_interrupted{interrupted_ext}"))
    finally:
        env.close()

    # Persist rich D3QN history for benchmarking and diagnostics.
    if args.agent == "d3qn" and isinstance(train_history, dict):
        with open(os.path.join(log_dir, "d3qn_history.json"), "w", encoding="utf-8") as f:
            json.dump(train_history, f, indent=2)

    log.info("=" * 60)
    log.info("Training Complete!")
    log.info(f"Models → {model_dir}")
    log.info(f"Logs   → {log_dir}")
    best_model_name = "best_model.pt" if args.agent == "d3qn" else "best_model.zip"
    log.info("Next: python evaluate.py --model " + model_dir + f"/best/{best_model_name}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
