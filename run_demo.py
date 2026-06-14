"""
One-Click Demo Script for Smart Traffic Management System
Run training ➜ evaluation ➜ report ➜ dashboard in a single command.
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent))

from ai.utils.logger import setup_logger


def check_sumo() -> bool:
    """Check if SUMO is installed and accessible."""
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home and os.path.isdir(sumo_home):
        return True
    # Try running sumo --version
    try:
        subprocess.run(["sumo", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def run_cmd(cmd: List[str], log, description: str) -> bool:
    """Run a shell command, logging success/failure."""
    log.info(f"▶ {description}")
    log.info("  $ %s", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode == 0:
        log.info(f"  ✓ {description} complete")
        return True
    else:
        log.error(f"  ✗ {description} failed (exit {result.returncode})")
        return False


def _set_dashboard_env_live() -> None:
    """Launch backend with live camera/video pipeline enabled."""
    os.environ["DEMO_MODE"] = "false"
    os.environ["LIVE_MODE"] = "true"
    os.environ["DEBUG_CV"] = "true"
    os.environ.setdefault("REAL_DATA_ONLY", "true")
    os.environ.setdefault("ENABLE_SIMULATION_FALLBACK", "false")
    os.environ.setdefault("FAIL_FAST_VIDEO", "false")


def _set_dashboard_env_demo() -> None:
    """Launch backend in lightweight demo mode."""
    os.environ["DEMO_MODE"] = "true"
    os.environ["LIVE_MODE"] = "false"
    os.environ["FAIL_FAST_VIDEO"] = "false"


def main():
    parser = argparse.ArgumentParser(
        description="One-click demo: train → evaluate → report → dashboard"
    )
    parser.add_argument("--agent", type=str, default="ppo", choices=["dqn", "ppo"])
    parser.add_argument("--timesteps", type=int, default=50000)
    parser.add_argument("--dashboard-only", action="store_true",
                        help="Skip training, just launch dashboard in demo mode")
    parser.add_argument("--skip-dashboard", action="store_true",
                        help="Run training + eval but don't launch dashboard")
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()

    log = setup_logger("demo", log_to_file=False)
    py = sys.executable

    log.info("=" * 60)
    log.info("🚦 Smart Traffic Management System — Demo")
    log.info("=" * 60)

    # Dashboard-only mode
    if args.dashboard_only:
        log.info("Launching dashboard in live camera mode (no SUMO required)...")
        _set_dashboard_env_live()
        run_cmd([py, "backend/main.py"], log, "Dashboard")
        return

    # Full pipeline
    has_sumo = check_sumo()
    if not has_sumo:
        log.warning("SUMO not found. Launching dashboard in live camera mode instead.")
        log.info("To run full training pipeline, install SUMO and set SUMO_HOME.")
        _set_dashboard_env_live()
        run_cmd([py, "backend/main.py"], log, "Dashboard (live)")
        return

    log.info(f"SUMO detected ✓")
    log.info(f"Agent: {args.agent.upper()} | Timesteps: {args.timesteps:,}")
    log.info("")

    # Step 1: Generate scenarios
    run_cmd([py, "scripts/generate_scenarios.py", "--scenario", "all"], log, "Generate Scenarios")

    # Step 2: Train
    ok = run_cmd(
        [py, "train.py", "--agent", args.agent, "--timesteps", str(args.timesteps), "--demo"],
        log, "Training"
    )
    if not ok:
        log.error("Training failed. Launching dashboard in live camera mode.")
        _set_dashboard_env_live()
        run_cmd([py, "backend/main.py"], log, "Dashboard (live)")
        return

    # Step 3: Find the latest model
    model_dirs = sorted(Path("models").iterdir(), key=os.path.getmtime, reverse=True)
    best_model = None
    for md in model_dirs:
        candidate = md / "best" / "best_model.zip"
        if candidate.exists():
            best_model = str(candidate)
            break
    if not best_model:
        # Fallback to final model
        for md in model_dirs:
            for f in md.iterdir():
                if f.suffix == ".zip":
                    best_model = str(f)
                    break
            if best_model:
                break

    if not best_model:
        log.error("No trained model found.")
        return

    log.info(f"Best model: {best_model}")

    # Step 4: Evaluate
    run_cmd(
        [py, "evaluate.py", "--model", best_model, "--agent", args.agent, "--report"],
        log, "Evaluation"
    )

    # Step 5: Generate report
    run_cmd([py, "scripts/generate_report.py"], log, "Report Generation")

    log.info("")
    log.info("=" * 60)
    log.info("🎉 Demo Complete!")
    log.info("  Results  → results/")
    log.info("  Report   → results/report.html")
    log.info("=" * 60)

    # Step 6: Launch dashboard
    if not args.skip_dashboard:
        log.info("Launching dashboard...")
        _set_dashboard_env_live()
        run_cmd([py, "backend/main.py"], log, "Dashboard")


if __name__ == "__main__":
    main()
