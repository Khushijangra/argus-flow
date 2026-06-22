"""
Quick Training Script for Demonstrations
Runs a short training session (~5-10 min) and produces results.
"""

import argparse
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.utils.logger import setup_logger


def main():
    parser = argparse.ArgumentParser(description="Quick RL training demo")
    parser.add_argument("--agent", type=str, default="ppo", choices=["dqn", "ppo"])
    parser.add_argument("--timesteps", type=int, default=50000)
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()

    log = setup_logger("quick_train")
    log.info("=" * 50)
    log.info("  QUICK TRAINING DEMO")
    log.info("=" * 50)
    log.info(f"Agent: {args.agent.upper()} | Timesteps: {args.timesteps:,}")

    # Run train.py with demo flag
    cmd = (
        f"{sys.executable} train.py"
        f" --agent {args.agent}"
        f" --timesteps {args.timesteps}"
        f" --demo"
    )
    if args.gui:
        cmd += " --gui"

    log.info("Starting training...")
    os.system(cmd)
    log.info("Quick training complete!")


if __name__ == "__main__":
    main()
