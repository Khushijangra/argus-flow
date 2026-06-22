"""
Run full multi-seed D3QN training and evaluation.

Example:
    python scripts/run_multiseed_d3qn.py --timesteps 100000 --seeds 42 123 999
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
LOGS_DIR = ROOT / "logs"
RESULTS_DIR = ROOT / "results"


def _safe_float(value: Any) -> float | None:
    """Return a finite float value, otherwise None for JSON-safe output."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN check
        return None
    return v


def _list_d3qn_runs(base: Path) -> set[str]:
    if not base.exists():
        return set()
    return {p.name for p in base.iterdir() if p.is_dir() and p.name.startswith("d3qn_")}


def _run_cmd(cmd: List[str]) -> None:
    print("[exec]", " ".join(cmd))
    cp = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if cp.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {cp.returncode}: {' '.join(cmd)}")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_run_metadata(run_name: str) -> Dict[str, Any]:
    return _load_json(LOGS_DIR / run_name / "run_metadata.json")


def _select_run_name(new_runs: List[str], seed: int, timesteps: int) -> str:
    """Choose the run that matches expected seed/timesteps from metadata."""
    matching: List[str] = []
    for run_name in new_runs:
        meta = _read_run_metadata(run_name)
        if not meta:
            continue
        if int(meta.get("seed", -1)) != int(seed):
            continue
        if int(meta.get("timesteps", -1)) != int(timesteps):
            continue
        matching.append(run_name)

    if matching:
        return sorted(matching)[-1]
    return sorted(new_runs)[-1]


def _load_yaml(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    base_path = cfg.get("extends")
    if not base_path:
        return cfg

    parent = p.parent / str(base_path)
    with parent.open("r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f) or {}

    cfg.pop("extends", None)
    return _deep_update(base_cfg, cfg)


def _deep_update(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def _calc_seed_stats(eval_results: Dict[str, Any], history: Dict[str, Any]) -> Dict[str, Any]:
    eval_curve = history.get("eval", []) if isinstance(history, dict) else []
    loss_curve = history.get("loss", []) if isinstance(history, dict) else []
    eps_curve = history.get("epsilon", []) if isinstance(history, dict) else []

    rewards = [float(x.get("mean_reward", 0.0)) for x in eval_curve]
    losses = [float(x.get("loss", 0.0)) for x in loss_curve]

    return {
        "eval": eval_results,
        "reward_curve_mean": mean(rewards) if rewards else None,
        "reward_curve_std": pstdev(rewards) if len(rewards) > 1 else 0.0,
        "loss_mean": mean(losses) if losses else None,
        "loss_std": pstdev(losses) if len(losses) > 1 else 0.0,
        "loss_nan": any((x != x) for x in losses),
        "epsilon_final": float(eps_curve[-1]["epsilon"]) if eps_curve else None,
        "n_eval_points": len(eval_curve),
        "n_loss_points": len(loss_curve),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-seed D3QN retraining runner")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--timesteps", type=int, default=None)
    parser.add_argument("--seeds", nargs="+", type=int, default=None)
    parser.add_argument("--n-episodes", type=int, default=None, help="Evaluation episodes per seed")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter for child runs")
    parser.add_argument(
        "--run-gate",
        action="store_true",
        help="Run multi-seed promotion gate check after training/evaluation completes",
    )
    parser.add_argument(
        "--gate-required-improved-seeds",
        type=int,
        default=None,
        help="Minimum seeds that must improve wait+queue for gate pass",
    )
    parser.add_argument(
        "--gate-max-throughput-drop-pct",
        type=float,
        default=None,
        help="Maximum allowed throughput drop percentage per seed",
    )
    parser.add_argument(
        "--gate-output",
        default=str(RESULTS_DIR / "d3qn_gate_report.json"),
        help="Output JSON path for gate report",
    )
    args = parser.parse_args()

    cfg = _load_yaml(args.config)
    bench_cfg = cfg.get("benchmark", {}).get("multiseed", {}) if isinstance(cfg, dict) else {}
    gate_cfg = cfg.get("benchmark", {}).get("gate", {}) if isinstance(cfg, dict) else {}

    timesteps = int(args.timesteps if args.timesteps is not None else bench_cfg.get("timesteps", 100000))
    seeds = [int(s) for s in (args.seeds if args.seeds is not None else bench_cfg.get("seeds", [42, 123, 999]))]
    n_episodes = int(args.n_episodes if args.n_episodes is not None else bench_cfg.get("n_episodes", 10))
    gate_required_improved = int(
        args.gate_required_improved_seeds
        if args.gate_required_improved_seeds is not None
        else gate_cfg.get("require_improved_seeds", 2)
    )
    gate_max_drop = float(
        args.gate_max_throughput_drop_pct
        if args.gate_max_throughput_drop_pct is not None
        else gate_cfg.get("max_throughput_drop_pct", 15.0)
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "timesteps": timesteps,
        "config": args.config,
        "python": args.python,
        "seeds": {},
        "aggregate": {},
    }

    rows: List[Dict[str, Any]] = []

    for seed in seeds:
        print("=" * 80)
        print(f"[seed] {seed}")
        before = _list_d3qn_runs(MODELS_DIR)

        _run_cmd(
            [
                args.python,
                "train.py",
                "--agent",
                "d3qn",
                "--config",
                args.config,
                "--timesteps",
                str(timesteps),
                "--seed",
                str(seed),
            ]
        )

        after = _list_d3qn_runs(MODELS_DIR)
        new_runs = sorted(after - before)
        if not new_runs:
            raise RuntimeError(f"No new d3qn run folder detected after seed {seed}")
        run_name = _select_run_name(new_runs, seed=seed, timesteps=timesteps)

        model_path = MODELS_DIR / run_name / "best" / "best_model.pt"
        if not model_path.exists():
            model_path = MODELS_DIR / run_name / "d3qn_final.pt"

        _run_cmd(
            [
                args.python,
                "evaluate.py",
                "--agent",
                "d3qn",
                "--config",
                args.config,
                "--model",
                str(model_path),
                "--n-episodes",
                str(n_episodes),
                "--output-dir",
                str(RESULTS_DIR / f"d3qn_seed_{seed}"),
            ]
        )

        eval_json = _load_json(RESULTS_DIR / f"d3qn_seed_{seed}" / "evaluation_results.json")
        history_json = _load_json(LOGS_DIR / run_name / "d3qn_history.json")

        seed_stats = _calc_seed_stats(eval_json.get("rl_agent", {}), history_json)
        seed_stats["run_name"] = run_name
        seed_stats["model_path"] = str(model_path)
        summary["seeds"][str(seed)] = seed_stats

        rows.append(
            {
                "seed": seed,
                "run_name": run_name,
                "model_path": str(model_path),
                "mean_reward": seed_stats["eval"].get("mean_reward"),
                "std_reward": seed_stats["eval"].get("std_reward"),
                "avg_waiting_time": seed_stats["eval"].get("avg_waiting_time"),
                "avg_queue_length": seed_stats["eval"].get("avg_queue_length"),
                "avg_throughput": seed_stats["eval"].get("avg_throughput"),
                "loss_mean": seed_stats.get("loss_mean"),
                "loss_std": seed_stats.get("loss_std"),
                "epsilon_final": seed_stats.get("epsilon_final"),
                "loss_nan": seed_stats.get("loss_nan"),
            }
        )

    if rows:
        df = pd.DataFrame(rows)
        loss_mean = _safe_float(df["loss_mean"].mean())
        loss_std = _safe_float(df["loss_mean"].std(ddof=0))
        summary["aggregate"] = {
            "mean_reward": float(df["mean_reward"].mean()),
            "std_reward": float(df["mean_reward"].std(ddof=0)),
            "avg_waiting_time": float(df["avg_waiting_time"].mean()),
            "avg_queue_length": float(df["avg_queue_length"].mean()),
            "avg_throughput": float(df["avg_throughput"].mean()),
            "loss_mean": loss_mean,
            "loss_std": loss_std,
            "any_nan_loss": bool(df["loss_nan"].any()),
        }

        out_csv = RESULTS_DIR / "d3qn_multiseed_summary.csv"
        df.to_csv(out_csv, index=False)
        print(f"[done] {out_csv}")

    out_json = RESULTS_DIR / "d3qn_multiseed_summary.json"
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[done] {out_json}")

    if args.run_gate:
        gate_cmd = [
            args.python,
            "scripts/evaluate_multiseed_gate.py",
            "--seeds",
            *[str(s) for s in seeds],
            "--require-improved-seeds",
            str(gate_required_improved),
            "--max-throughput-drop-pct",
            str(gate_max_drop),
            "--output",
            str(args.gate_output),
        ]
        _run_cmd(gate_cmd)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
