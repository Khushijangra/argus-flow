"""
Comprehensive benchmark suite for DQN vs PPO vs D3QN.

Outputs:
- results/benchmark_d3qn.json
- results/benchmark_summary.csv
- results/benchmark_reward_vs_timesteps.png
- results/benchmark_waiting_vs_timesteps.png
- results/benchmark_queue_vs_timesteps.png
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from ai.rl.d3qn import D3QNAgent
from ai.rl.dqn import DQNAgent
from ai.rl.ppo import PPOAgent
from ai.envs.multi_agent_env import MultiAgentSumoEnv
from ai.envs.sumo_env import SumoEnvironment


@dataclass
class DeviceInfo:
    device: str
    gpu_name: str
    gpu_memory_gb: float


def set_global_seed(seed: int, deterministic: bool = True) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        try:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        except Exception:
            pass


def detect_device() -> DeviceInfo:
    if torch.cuda.is_available():
        idx = torch.cuda.current_device()
        name = torch.cuda.get_device_name(idx)
        mem_gb = torch.cuda.get_device_properties(idx).total_memory / (1024**3)
        device = "cuda"
    else:
        name = ""
        mem_gb = 0.0
        device = "cpu"
    return DeviceInfo(device=device, gpu_name=name, gpu_memory_gb=mem_gb)


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_single_env(config: Dict[str, Any], route_file: Optional[str] = None):
    env_cfg = config["environment"]
    sumo_cfg = config["sumo"]
    return SumoEnvironment(
        net_file=env_cfg["network_file"],
        route_file=route_file or env_cfg["route_file"],
        use_gui=False,
        max_steps=sumo_cfg["max_steps"],
        delta_time=sumo_cfg["delta_time"],
        yellow_time=sumo_cfg["yellow_time"],
        min_green=sumo_cfg["min_green"],
        max_green=sumo_cfg["max_green"],
        reward_type=env_cfg["reward"]["type"],
    )


def make_multi_env(
    config: Dict[str, Any],
    graph_enabled: bool = False,
    shared_policy_mode: bool = False,
):
    env_cfg = config["environment"]
    sumo_cfg = config["sumo"]

    net_candidates = [
        env_cfg.get("grid_network_file", ""),
        "networks/grid_2x2.net.xml",
    ]
    route_candidates = [
        env_cfg.get("grid_route_file", ""),
        "networks/grid_2x2.rou.xml",
    ]

    net_file = next((p for p in net_candidates if p and Path(p).exists()), None)
    route_file = next((p for p in route_candidates if p and Path(p).exists()), None)
    if not net_file or not route_file:
        raise FileNotFoundError("Grid network/route files not found for multi-agent benchmark")

    return MultiAgentSumoEnv(
        net_file=net_file,
        route_file=route_file,
        use_gui=False,
        max_steps=sumo_cfg["max_steps"],
        delta_time=sumo_cfg["delta_time"],
        yellow_time=sumo_cfg["yellow_time"],
        min_green=sumo_cfg["min_green"],
        max_green=sumo_cfg["max_green"],
        reward_type="cooperative",
        graph_enabled=bool(graph_enabled),
        graph_debug=bool(config.get("coordination", {}).get("debug", False)),
        shared_policy_mode=bool(shared_policy_mode),
    )


def compute_convergence_step(eval_curve: List[Dict[str, Any]]) -> Optional[int]:
    if len(eval_curve) < 4:
        return None
    rewards = [float(p["mean_reward"]) for p in eval_curve]
    tail_mean = float(np.mean(rewards[-3:]))
    tol = max(1.0, abs(tail_mean) * 0.05)
    for i in range(len(rewards) - 2):
        window = rewards[i : i + 3]
        if max(abs(w - tail_mean) for w in window) <= tol:
            return int(eval_curve[i]["step"])
    return None


def evaluate_agent(agent_name: str, model_path: str, config: Dict[str, Any], route_file: str, n_episodes: int) -> Dict[str, Any]:
    env = make_single_env(config, route_file=route_file)
    seed = int(config.get("training", {}).get("seed", 42))
    env.reset(seed=seed)

    run_cfg = copy.deepcopy(config)
    run_cfg["training"]["seed"] = seed

    if agent_name == "dqn":
        agent = DQNAgent(env=env, config=run_cfg, log_dir="logs/benchmark_eval_tmp", model_dir="models/benchmark_eval_tmp")
        agent.load(model_path)
    elif agent_name == "ppo":
        agent = PPOAgent(env=env, config=run_cfg, log_dir="logs/benchmark_eval_tmp", model_dir="models/benchmark_eval_tmp")
        agent.load(model_path)
    else:
        agent = D3QNAgent(env=env, config=run_cfg, log_dir="logs/benchmark_eval_tmp", model_dir="models/benchmark_eval_tmp")
        agent.load(model_path)

    result = agent.evaluate(n_episodes=n_episodes, render=False)
    env.close()
    return result


def run_sb3_training(
    agent_name: str,
    agent,
    total_timesteps: int,
    eval_freq: int,
    n_eval_episodes: int,
) -> Dict[str, Any]:
    eval_curve: List[Dict[str, Any]] = []
    eps_curve: List[Dict[str, Any]] = []
    loss_curve: List[Dict[str, Any]] = []

    trained_steps = 0
    t0 = time.perf_counter()

    while trained_steps < total_timesteps:
        chunk = min(eval_freq, total_timesteps - trained_steps)
        agent.model.learn(total_timesteps=chunk, reset_num_timesteps=False, progress_bar=False)
        trained_steps += chunk

        eval_res = agent.evaluate(n_episodes=n_eval_episodes)
        point = {
            "step": trained_steps,
            "mean_reward": float(eval_res.get("mean_reward", 0.0)),
            "std_reward": float(eval_res.get("std_reward", 0.0)),
            "mean_length": float(eval_res.get("mean_length", 0.0)),
            "avg_waiting_time": float(eval_res.get("avg_waiting_time", 0.0)),
            "avg_queue_length": float(eval_res.get("avg_queue_length", 0.0)),
            "avg_throughput": float(eval_res.get("avg_throughput", 0.0)),
        }
        eval_curve.append(point)

        epsilon = getattr(agent.model, "exploration_rate", None)
        if epsilon is not None:
            eps_curve.append({"step": trained_steps, "epsilon": float(epsilon)})

        if hasattr(agent.model, "logger") and hasattr(agent.model.logger, "name_to_value"):
            maybe_loss = agent.model.logger.name_to_value.get("train/loss")
            if maybe_loss is not None:
                loss_curve.append({"step": trained_steps, "loss": float(maybe_loss)})

    total_time = time.perf_counter() - t0
    return {
        "eval_curve": eval_curve,
        "epsilon_curve": eps_curve,
        "loss_curve": loss_curve,
        "total_time_s": float(total_time),
        "time_per_step_s": float(total_time / max(1, total_timesteps)),
    }


def run_d3qn_training(
    agent: D3QNAgent,
    total_timesteps: int,
    eval_freq: int,
    n_eval_episodes: int,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    history = agent.train(
        total_timesteps=total_timesteps,
        eval_freq=eval_freq,
        n_eval_episodes=n_eval_episodes,
        save_freq=max(eval_freq, 10000),
    )
    total_time = time.perf_counter() - t0

    return {
        "eval_curve": history.get("eval", []),
        "epsilon_curve": history.get("epsilon", []),
        "loss_curve": history.get("loss", []),
        "episode_curve": history.get("episodes", []),
        "total_time_s": float(total_time),
        "time_per_step_s": float(total_time / max(1, total_timesteps)),
    }


def plot_metric(curves: Dict[str, List[Dict[str, Any]]], key: str, ylabel: str, out_path: Path) -> None:
    plt.figure(figsize=(10, 6))
    for agent_name, pts in curves.items():
        if not pts:
            continue
        xs = [p["step"] for p in pts if key in p]
        ys = [p[key] for p in pts if key in p]
        if xs and ys:
            plt.plot(xs, ys, marker="o", linewidth=2, label=agent_name.upper())
    plt.xlabel("Timesteps")
    plt.ylabel(ylabel)
    plt.title(f"{ylabel} vs Timesteps")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=160)
    plt.close()


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp_path.replace(path)


def write_partial_results(path: Path, payload: Dict[str, Any], timestamp: str) -> Path:
    partial_path = path.with_name(f"{path.stem}_partial_{timestamp}{path.suffix}")
    write_json_atomic(partial_path, payload)
    return partial_path


def load_resume_results(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Resume benchmark file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Resume benchmark file must contain a JSON object: {path}")
    payload.setdefault("meta", {})
    payload["meta"]["incomplete_run"] = True
    return payload


def short_cpu_benchmark(agent_name: str, config: Dict[str, Any], timesteps: int, seed: int) -> Optional[Dict[str, float]]:
    if timesteps <= 0:
        return None

    cpu_cfg = copy.deepcopy(config)
    cpu_cfg["agent"]["device"] = "cpu"
    cpu_cfg["training"]["seed"] = seed

    env = make_single_env(cpu_cfg)
    env.reset(seed=seed)

    log_dir = ROOT / "logs" / "benchmark_cpu_tmp"
    model_dir = ROOT / "models" / "benchmark_cpu_tmp"

    if agent_name == "dqn":
        agent = DQNAgent(env=env, config=cpu_cfg, log_dir=str(log_dir), model_dir=str(model_dir))
    elif agent_name == "ppo":
        agent = PPOAgent(env=env, config=cpu_cfg, log_dir=str(log_dir), model_dir=str(model_dir))
    else:
        agent = D3QNAgent(env=env, config=cpu_cfg, log_dir=str(log_dir), model_dir=str(model_dir))

    t0 = time.perf_counter()
    if agent_name in ("dqn", "ppo"):
        agent.model.learn(total_timesteps=timesteps, reset_num_timesteps=False, progress_bar=False)
    else:
        agent.train(total_timesteps=timesteps, eval_freq=max(1000, timesteps // 2), n_eval_episodes=2, save_freq=timesteps + 1)
    elapsed = time.perf_counter() - t0
    env.close()

    return {
        "cpu_total_time_s": float(elapsed),
        "cpu_time_per_step_s": float(elapsed / max(1, timesteps)),
        "cpu_steps_per_sec": float(timesteps / max(elapsed, 1e-9)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark DQN/PPO/D3QN on SUMO traffic control")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--timesteps", type=int, default=50000)
    parser.add_argument("--eval-freq", type=int, default=10000)
    parser.add_argument("--eval-episodes", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cpu-compare-steps", type=int, default=2000)
    parser.add_argument("--skip-multi", action="store_true")
    parser.add_argument(
        "--include-graph-variant",
        action="store_true",
        help="Include Graph-D3QN variant in multi-agent benchmark",
    )
    parser.add_argument(
        "--agents",
        nargs="+",
        choices=["dqn", "ppo", "d3qn", "graph_d3qn"],
        default=None,
        help="Optional subset of agents to run",
    )
    parser.add_argument(
        "--resume-results",
        type=str,
        default=None,
        help="Resume from a partial benchmark JSON and continue missing combinations",
    )
    args = parser.parse_args()

    set_global_seed(args.seed, deterministic=True)
    config = load_yaml(ROOT / args.config)
    config["training"]["seed"] = int(args.seed)

    include_graph_variant = bool(
        args.include_graph_variant
        or config.get("benchmark", {}).get("multiseed", {}).get("include_graph_variant", False)
    )

    device_info = detect_device()
    print(f"[device] using={device_info.device}")
    if device_info.device == "cuda":
        print(f"[device] gpu={device_info.gpu_name} mem_gb={device_info.gpu_memory_gb:.2f}")

    resume_payload = None
    if args.resume_results:
        resume_payload = load_resume_results((ROOT / args.resume_results).resolve())

    timestamp = (
        str(resume_payload.get("meta", {}).get("timestamp"))
        if resume_payload
        else datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    out_json = ROOT / "results" / "benchmark_d3qn.json"
    out_csv = ROOT / "results" / "benchmark_summary.csv"

    environments: Dict[str, Callable[[], Any]] = {
        "single_intersection": lambda: make_single_env(config),
    }

    if not args.skip_multi:
        environments["multi_agent"] = lambda: make_multi_env(config)

    if resume_payload is not None:
        all_results = resume_payload
        all_results.setdefault("environments", {})
        all_results.setdefault("stress_tests", {})
        all_results.setdefault("gpu_impact", {})
        all_results.setdefault("decision", {})
        all_results["meta"]["resumed_from"] = str((ROOT / args.resume_results).resolve())
        all_results["meta"]["incomplete_run"] = True
        if all_results["meta"].get("seed") != args.seed:
            print(f"[warn] Resume file seed={all_results['meta'].get('seed')} differs from CLI seed={args.seed}; using resume file seed metadata.")
        if all_results["meta"].get("timesteps") != args.timesteps:
            print(f"[warn] Resume file timesteps={all_results['meta'].get('timesteps')} differs from CLI timesteps={args.timesteps}; using CLI timesteps for any missing runs.")
        if all_results["meta"].get("eval_freq") != args.eval_freq:
            print(f"[warn] Resume file eval_freq={all_results['meta'].get('eval_freq')} differs from CLI eval_freq={args.eval_freq}; using CLI value for missing runs.")
        if all_results["meta"].get("eval_episodes") != args.eval_episodes:
            print(f"[warn] Resume file eval_episodes={all_results['meta'].get('eval_episodes')} differs from CLI eval_episodes={args.eval_episodes}; using CLI value for missing runs.")
    else:
        all_results = {
            "meta": {
                "timestamp": timestamp,
                "seed": args.seed,
                "timesteps": args.timesteps,
                "eval_freq": args.eval_freq,
                "eval_episodes": args.eval_episodes,
                "device": device_info.device,
                "gpu_name": device_info.gpu_name,
                "gpu_memory_gb": device_info.gpu_memory_gb,
                "deterministic": True,
            },
            "environments": {},
            "stress_tests": {},
            "gpu_impact": {},
            "decision": {},
        }

    summary_rows: List[Dict[str, Any]] = []
    if resume_payload is not None:
        for env_name, agents in (all_results.get("environments", {}) or {}).items():
            if not isinstance(agents, dict):
                continue
            for agent_name, agent_result in agents.items():
                metrics = (agent_result or {}).get("metrics") if isinstance(agent_result, dict) else None
                if metrics:
                    summary_rows.append(
                        {
                            "environment": env_name,
                            "agent": agent_name,
                            "mean_reward": metrics.get("mean_reward"),
                            "avg_waiting_time": metrics.get("avg_waiting_time"),
                            "avg_queue_length": metrics.get("avg_queue_length"),
                            "reward_variance": metrics.get("reward_variance"),
                            "reward_std": metrics.get("reward_std"),
                            "stability": metrics.get("stability"),
                            "td_loss_variance": metrics.get("td_loss_variance"),
                            "spillback_rate": metrics.get("spillback_rate"),
                            "time_per_step_s": metrics.get("time_per_step_s"),
                            "total_training_time_s": metrics.get("total_training_time_s"),
                            "convergence_step": metrics.get("convergence_step"),
                            "graph_enabled": metrics.get("graph_enabled"),
                        }
                    )
    incomplete_run = False

    try:
        for env_name, env_factory in environments.items():
            print(f"\n=== Environment: {env_name} ===")
            all_results["environments"][env_name] = {}

            agent_variants = ["dqn", "ppo", "d3qn"]
            if env_name == "multi_agent" and include_graph_variant:
                agent_variants.append("graph_d3qn")

            if args.agents:
                allowed = set(args.agents)
                agent_variants = [a for a in agent_variants if a in allowed]

            for agent_name in agent_variants:
                existing = all_results.get("environments", {}).get(env_name, {}).get(agent_name)
                if isinstance(existing, dict) and existing.get("metrics") and resume_payload is not None:
                    print(f"[skip] {agent_name} on {env_name} already present in resume file")
                    continue

                print(f"\n--- Training {agent_name.upper()} on {env_name} ---")
                set_global_seed(args.seed, deterministic=True)
                env = None
                try:
                    run_cfg = copy.deepcopy(config)
                    run_cfg["training"]["seed"] = args.seed

                    graph_mode = agent_name == "graph_d3qn"
                    if graph_mode:
                        run_cfg.setdefault("coordination", {})
                        run_cfg["coordination"]["graph_enabled"] = True

                    if env_name == "multi_agent":
                        use_shared_policy = agent_name in ("dqn", "d3qn", "graph_d3qn")
                        env = make_multi_env(
                            run_cfg,
                            graph_enabled=graph_mode,
                            shared_policy_mode=use_shared_policy,
                        )
                    else:
                        env = env_factory()
                    env.reset(seed=args.seed)

                    log_dir = ROOT / "logs" / f"benchmark_{timestamp}" / env_name / agent_name
                    model_dir = ROOT / "models" / f"benchmark_{timestamp}" / env_name / agent_name
                    log_dir.mkdir(parents=True, exist_ok=True)
                    model_dir.mkdir(parents=True, exist_ok=True)

                    if agent_name == "dqn":
                        agent = DQNAgent(env=env, config=run_cfg, log_dir=str(log_dir), model_dir=str(model_dir))
                        run = run_sb3_training(agent_name, agent, args.timesteps, args.eval_freq, args.eval_episodes)
                        model_path = str(model_dir / "benchmark_final.zip")
                        agent.model.save(model_path)
                    elif agent_name == "ppo":
                        agent = PPOAgent(env=env, config=run_cfg, log_dir=str(log_dir), model_dir=str(model_dir))
                        run = run_sb3_training(agent_name, agent, args.timesteps, args.eval_freq, args.eval_episodes)
                        model_path = str(model_dir / "benchmark_final.zip")
                        agent.model.save(model_path)
                    else:
                        agent = D3QNAgent(env=env, config=run_cfg, log_dir=str(log_dir), model_dir=str(model_dir))
                        run = run_d3qn_training(agent, args.timesteps, args.eval_freq, args.eval_episodes)
                        model_path = str(model_dir / "benchmark_final.pt")
                        agent.save(model_path)

                    eval_curve = run.get("eval_curve", [])
                    rewards = [float(p.get("mean_reward", 0.0)) for p in eval_curve]
                    waits = [float(p.get("avg_waiting_time", 0.0)) for p in eval_curve]
                    queues = [float(p.get("avg_queue_length", 0.0)) for p in eval_curve]

                    reward_var = float(np.var(rewards)) if rewards else 0.0
                    reward_std = float(np.std(rewards)) if rewards else 0.0

                    loss_vals = [float(x["loss"]) for x in run.get("loss_curve", []) if "loss" in x]
                    loss_var = float(np.var(loss_vals)) if loss_vals else None
                    spillback_rate = float(np.mean([1.0 if q > 10.0 else 0.0 for q in queues])) if queues else 0.0

                    convergence_step = compute_convergence_step(eval_curve)

                    agent_result = {
                        "model_path": model_path,
                        "training": run,
                        "metrics": {
                            "mean_reward": float(np.mean(rewards)) if rewards else 0.0,
                            "avg_waiting_time": float(np.mean(waits)) if waits else 0.0,
                            "avg_queue_length": float(np.mean(queues)) if queues else 0.0,
                            "reward_variance": reward_var,
                            "reward_std": reward_std,
                            "stability": float(1.0 / (1.0 + reward_std)),
                            "td_loss_variance": loss_var,
                            "spillback_rate": spillback_rate,
                            "time_per_step_s": run["time_per_step_s"],
                            "total_training_time_s": run["total_time_s"],
                            "convergence_step": convergence_step,
                            "graph_enabled": bool(graph_mode),
                        },
                    }
                    all_results["environments"][env_name][agent_name] = agent_result

                    summary_rows.append(
                        {
                            "environment": env_name,
                            "agent": agent_name,
                            "mean_reward": agent_result["metrics"]["mean_reward"],
                            "avg_waiting_time": agent_result["metrics"]["avg_waiting_time"],
                            "avg_queue_length": agent_result["metrics"]["avg_queue_length"],
                            "reward_variance": agent_result["metrics"]["reward_variance"],
                            "reward_std": agent_result["metrics"]["reward_std"],
                            "stability": agent_result["metrics"]["stability"],
                            "td_loss_variance": agent_result["metrics"]["td_loss_variance"],
                            "spillback_rate": agent_result["metrics"]["spillback_rate"],
                            "time_per_step_s": agent_result["metrics"]["time_per_step_s"],
                            "total_training_time_s": agent_result["metrics"]["total_training_time_s"],
                            "convergence_step": agent_result["metrics"]["convergence_step"],
                            "graph_enabled": agent_result["metrics"]["graph_enabled"],
                        }
                    )

                    if isinstance(run, dict) and run.get("incomplete_run"):
                        incomplete_run = True
                        all_results["meta"]["incomplete_run"] = True
                        all_results["meta"]["interrupted_agent"] = agent_name
                        all_results["meta"]["interrupted_environment"] = env_name
                        break

                except KeyboardInterrupt:
                    incomplete_run = True
                    all_results["meta"]["incomplete_run"] = True
                    all_results["meta"]["interrupted_agent"] = agent_name
                    all_results["meta"]["interrupted_environment"] = env_name
                    print("[warn] Benchmark interrupted by user.")
                    break
                except Exception as exc:
                    all_results["environments"][env_name][agent_name] = {"error": str(exc)}
                    print(f"[warn] {agent_name} on {env_name} failed: {exc}")
                finally:
                    if env is not None:
                        try:
                            env.close()
                        except Exception:
                            pass

            if incomplete_run:
                break

    except KeyboardInterrupt:
        incomplete_run = True
        all_results["meta"]["incomplete_run"] = True
        print("[warn] Benchmark interrupted before completion.")

    if incomplete_run:
        all_results["meta"]["incomplete_run"] = True
        partial_path = write_partial_results(out_json, all_results, timestamp)
        print(f"[partial] {partial_path}")
        return 130

    # Stress testing on single-intersection with scenario routes.
    scenario_routes = {
        "peak_traffic": "networks/scenarios/rush_hour.rou.xml",
        "low_traffic": "networks/scenarios/night.rou.xml",
        "incident": "networks/scenarios/asymmetric.rou.xml",
    }

    trained_single = all_results["environments"].get("single_intersection", {})
    all_results["stress_tests"] = {}

    for scenario_name, route in scenario_routes.items():
        if not (ROOT / route).exists():
            all_results["stress_tests"][scenario_name] = {"skipped": f"missing route file: {route}"}
            continue

        all_results["stress_tests"][scenario_name] = {}
        for agent_name in ["dqn", "ppo", "d3qn"]:
            entry = trained_single.get(agent_name, {})
            model_path = entry.get("model_path") if isinstance(entry, dict) else None
            if not model_path:
                all_results["stress_tests"][scenario_name][agent_name] = {"skipped": "model unavailable"}
                continue

            try:
                res = evaluate_agent(agent_name, model_path, config, str(ROOT / route), args.eval_episodes)
                all_results["stress_tests"][scenario_name][agent_name] = res
            except Exception as exc:
                all_results["stress_tests"][scenario_name][agent_name] = {"error": str(exc)}

    # GPU impact with short CPU compare (single env only).
    if device_info.device == "cuda":
        for agent_name in ["dqn", "ppo", "d3qn"]:
            gpu_entry = all_results["environments"].get("single_intersection", {}).get(agent_name, {})
            gpu_tps = None
            if isinstance(gpu_entry, dict):
                tps = gpu_entry.get("metrics", {}).get("time_per_step_s")
                if tps:
                    gpu_tps = 1.0 / max(float(tps), 1e-9)

            cpu_bench = short_cpu_benchmark(agent_name, config, args.cpu_compare_steps, args.seed)
            if cpu_bench and gpu_tps is not None:
                speedup = gpu_tps / max(cpu_bench["cpu_steps_per_sec"], 1e-9)
                all_results["gpu_impact"][agent_name] = {
                    "gpu_steps_per_sec": gpu_tps,
                    **cpu_bench,
                    "speedup_gpu_vs_cpu": float(speedup),
                }

    # Decision output (single env preferred)
    single_env_results = all_results["environments"].get("single_intersection", {})

    def metric(agent: str, key: str, default: float) -> float:
        return float(single_env_results.get(agent, {}).get("metrics", {}).get(key, default))

    valid_agents = [a for a in ["dqn", "ppo", "d3qn"] if "metrics" in single_env_results.get(a, {})]

    if valid_agents:
        best_perf = max(valid_agents, key=lambda a: metric(a, "mean_reward", -1e18))
        most_stable = min(valid_agents, key=lambda a: metric(a, "reward_std", 1e18))
        fastest = min(valid_agents, key=lambda a: metric(a, "time_per_step_s", 1e18))

        d3qn_reward = metric("d3qn", "mean_reward", -1e18)
        dqn_reward = metric("dqn", "mean_reward", -1e18)
        d3qn_std = metric("d3qn", "reward_std", 1e18)
        dqn_std = metric("dqn", "reward_std", 1e18)
        d3qn_wait = metric("d3qn", "avg_waiting_time", 1e18)
        dqn_wait = metric("dqn", "avg_waiting_time", 1e18)

        replace_dqn = bool((d3qn_reward >= dqn_reward) or (d3qn_std <= dqn_std) or (d3qn_wait <= dqn_wait))

        all_results["decision"] = {
            "best_performing_agent": best_perf,
            "most_stable_agent": most_stable,
            "fastest_agent": fastest,
            "recommendation": {
                "should_d3qn_replace_dqn": replace_dqn,
                "should_ppo_remain": True,
                "failure_modes": [
                    "Multi-agent benchmark may fail if grid topology/IDs do not match expected J0_0..J3_3 layout.",
                    "Incident scenario depends on asymmetric route file availability.",
                ],
            },
        }

    # Build summary CSV and plots only for complete runs.
    if not incomplete_run:
        df = pd.DataFrame(summary_rows)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        if not df.empty:
            df.sort_values(["environment", "agent"], inplace=True)
            df.to_csv(out_csv, index=False)

        single_curves = {
            a: single_env_results[a]["training"].get("eval_curve", [])
            for a in ["dqn", "ppo", "d3qn", "graph_d3qn"]
            if "training" in single_env_results.get(a, {})
        }

        plot_metric(single_curves, "mean_reward", "Reward", ROOT / "results" / "benchmark_reward_vs_timesteps.png")
        plot_metric(single_curves, "avg_waiting_time", "Waiting Time (s)", ROOT / "results" / "benchmark_waiting_vs_timesteps.png")
        plot_metric(single_curves, "avg_queue_length", "Queue Length", ROOT / "results" / "benchmark_queue_vs_timesteps.png")

        out_json.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(out_json, all_results)

        print(f"[done] {out_json}")
        print(f"[done] {out_csv}")
        print(f"[done] results/benchmark_reward_vs_timesteps.png")
        print(f"[done] results/benchmark_waiting_vs_timesteps.png")
        print(f"[done] results/benchmark_queue_vs_timesteps.png")
    else:
        all_results["meta"]["incomplete_run"] = True
        partial_path = write_partial_results(out_json, all_results, timestamp)
        print(f"[partial] {partial_path}")

    return 0 if not incomplete_run else 130


if __name__ == "__main__":
    raise SystemExit(main())
