"""
Evaluate D3QN multi-seed gate results and produce a promotion decision.

This script reads per-seed evaluation JSON files created by run_multiseed_d3qn.py
and emits a concise pass/fail report with configurable thresholds.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _deep_update(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def _load_yaml(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}

    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    parent_ref = cfg.get("extends")
    if not parent_ref:
        return cfg

    parent = p.parent / str(parent_ref)
    with parent.open("r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f) or {}

    cfg.pop("extends", None)
    return _deep_update(base_cfg, cfg)


def _pct_change(new_value: float, base_value: float) -> float:
    if base_value == 0.0:
        return 0.0
    return (new_value - base_value) / abs(base_value) * 100.0


def _seed_result(seed: int) -> Dict[str, Any]:
    eval_path = RESULTS_DIR / f"d3qn_seed_{seed}" / "evaluation_results.json"
    payload = _load_json(eval_path)
    base = payload.get("baseline", {})
    rl = payload.get("rl_agent", {})

    baseline_wait = float(base.get("avg_waiting_time", 0.0))
    baseline_queue = float(base.get("avg_queue_length", 0.0))
    baseline_throughput = float(base.get("throughput", 0.0))

    rl_wait = float(rl.get("avg_waiting_time", 0.0))
    rl_queue = float(rl.get("avg_queue_length", 0.0))
    rl_throughput = float(rl.get("throughput", rl.get("avg_throughput", 0.0)))

    return {
        "seed": seed,
        "file": str(eval_path),
        "exists": bool(payload),
        "wait_change_pct": _pct_change(rl_wait, baseline_wait),
        "queue_change_pct": _pct_change(rl_queue, baseline_queue),
        "throughput_change_pct": _pct_change(rl_throughput, baseline_throughput),
        "baseline": {
            "avg_waiting_time": baseline_wait,
            "avg_queue_length": baseline_queue,
            "throughput": baseline_throughput,
        },
        "rl": {
            "avg_waiting_time": rl_wait,
            "avg_queue_length": rl_queue,
            "throughput": rl_throughput,
            "mean_reward": float(rl.get("mean_reward", 0.0)),
            "std_reward": float(rl.get("std_reward", 0.0)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate D3QN multi-seed promotion gate")
    parser.add_argument("--config", type=str, default=None, help="Optional config YAML (supports extends)")
    parser.add_argument("--seeds", nargs="+", type=int, default=None)
    parser.add_argument("--require-improved-seeds", type=int, default=None)
    parser.add_argument("--max-throughput-drop-pct", type=float, default=None)
    parser.add_argument("--output", type=str, default=str(RESULTS_DIR / "d3qn_gate_report.json"))
    args = parser.parse_args()

    cfg = _load_yaml(args.config) if args.config else {}
    bench_cfg = cfg.get("benchmark", {}).get("multiseed", {}) if isinstance(cfg, dict) else {}
    gate_cfg = cfg.get("benchmark", {}).get("gate", {}) if isinstance(cfg, dict) else {}

    seeds = [
        int(s)
        for s in (
            args.seeds if args.seeds is not None else bench_cfg.get("seeds", [42, 123, 999])
        )
    ]
    required_improved = int(
        args.require_improved_seeds
        if args.require_improved_seeds is not None
        else gate_cfg.get("require_improved_seeds", 2)
    )
    max_drop_pct = float(
        args.max_throughput_drop_pct
        if args.max_throughput_drop_pct is not None
        else gate_cfg.get("max_throughput_drop_pct", 15.0)
    )

    seed_rows: List[Dict[str, Any]] = [_seed_result(s) for s in seeds]
    required_improved = min(int(required_improved), len(seed_rows))
    missing = [r["seed"] for r in seed_rows if not r["exists"]]

    improved_wait = [r for r in seed_rows if r["exists"] and r["wait_change_pct"] < 0.0]
    improved_queue = [r for r in seed_rows if r["exists"] and r["queue_change_pct"] < 0.0]
    acceptable_throughput = [
        r
        for r in seed_rows
        if r["exists"] and r["throughput_change_pct"] >= -abs(max_drop_pct)
    ]

    # A near miss means throughput drop exceeded threshold by <= 0.5 percentage points.
    near_miss_throughput = []
    for r in seed_rows:
        if not r["exists"]:
            continue
        miss_margin = max(0.0, (-r["throughput_change_pct"]) - abs(max_drop_pct))
        r["throughput_drop_excess_pct"] = miss_margin
        if 0.0 < miss_margin <= 0.5:
            near_miss_throughput.append(r)

    improved_both = [
        r
        for r in seed_rows
        if r["exists"] and r["wait_change_pct"] < 0.0 and r["queue_change_pct"] < 0.0
    ]

    gate_pass = (
        not missing
        and len(improved_both) >= required_improved
        and len(acceptable_throughput) == len(seed_rows)
    )

    report: Dict[str, Any] = {
        "seeds": seeds,
        "config": args.config,
        "thresholds": {
            "require_improved_seeds": int(required_improved),
            "max_throughput_drop_pct": float(max_drop_pct),
        },
        "counts": {
            "missing": len(missing),
            "improved_wait": len(improved_wait),
            "improved_queue": len(improved_queue),
            "improved_both": len(improved_both),
            "acceptable_throughput": len(acceptable_throughput),
            "near_miss_throughput": len(near_miss_throughput),
        },
        "missing_seeds": missing,
        "gate_pass": gate_pass,
        "seed_results": seed_rows,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"[gate] {'PASS' if gate_pass else 'FAIL'}")
    print(f"[gate] report: {out_path}")
    if missing:
        print(f"[gate] missing seeds: {missing}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
