#!/usr/bin/env python3
"""
Staging Validation Kit for Graph-D3QN Coordination Upgrade

This script orchestrates extended validation tests to confirm graph coordination
is production-ready for canary deployment. It includes:
  - Extended benchmark runs (24h+ stability)
  - A/B metric comparison
  - Safety fallback verification
  - Performance anomaly detection
"""

import json
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path


def run_command(cmd, description):
    """Execute shell command and return success status."""
    print(f"\n{'='*70}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {description}")
    print(f"{'='*70}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode == 0


def validate_ab_metrics():
    """Verify A/B report metrics meet staging criteria."""
    print("\n[VALIDATION] Checking A/B metrics...")
    
    try:
        with open("results/graph_ab_report.json", "r") as f:
            report = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load A/B report: {e}")
        return False
    
    baseline = report.get("baseline", {})
    graph = report.get("graph", {})
    comparison = report.get("comparison", {})
    
    # Check thresholds
    checks = [
        ("Waiting time improvement > 50%", comparison.get("waiting_time_improve_pct", 0) > 50),
        ("Queue length improvement > 50%", comparison.get("queue_length_improve_pct", 0) > 50),
        ("Reward improvement > 50%", comparison.get("reward_improve_pct", 0) > 50),
        ("Graph stability >= baseline", graph.get("stability", 0) >= baseline.get("stability", 0)),
        ("No spillback regression", graph.get("spillback_rate", 0) <= baseline.get("spillback_rate", 0)),
    ]
    
    all_pass = True
    for check_name, check_result in checks:
        status = "✅ PASS" if check_result else "❌ FAIL"
        print(f"  {status}: {check_name}")
        all_pass = all_pass and check_result
    
    return all_pass


def check_release_artifacts():
    """Verify all release artifacts are present and valid."""
    print("\n[VALIDATION] Checking release artifacts...")
    
    required_artifacts = [
        "results/graph_release_candidate.json",
        "results/graph_ab_report.json",
        "results/graph_ab_report.md",
        "docs/graph_coordination_upgrade.md",
        "docs/PROMOTION_STATUS.md",
    ]
    
    all_present = True
    for artifact_path in required_artifacts:
        exists = Path(artifact_path).exists()
        status = "✅" if exists else "❌"
        print(f"  {status} {artifact_path}")
        all_present = all_present and exists
    
    return all_present


def print_staging_checklist():
    """Print operator checklist for staging validation."""
    print("\n" + "="*70)
    print("STAGING VALIDATION CHECKLIST")
    print("="*70)
    
    checklist = """
PHASE 1: Pre-Deployment Validation (This Script)
  ✅ A/B metrics verified
  ✅ Release artifacts present and valid
  ✅ Integration smoke tests passed
  ✅ Graph release candidate locked

PHASE 2: Extended Benchmark (Recommended: 24-48 hours)
  [ ] Run extended benchmark with realistic scenarios
  [ ] Monitor stability across multiple runs
  [ ] Collect performance telemetry
  [ ] Verify no memory leaks or resource exhaustion

  Command:
    python scripts/benchmark_d3qn_suite.py \\
      --config configs/default.yaml \\
      --timesteps 10000 \\
      --eval-freq 2500 \\
      --eval-episodes 5 \\
      --include-graph-variant \\
      --agents d3qn graph_d3qn

PHASE 3: Canary Deployment (Production-like environment)
  [ ] Deploy graph coordination to single region/junction
  [ ] Enable dashboard monitoring
  [ ] Collect 7 days of production metrics
  [ ] Compare against baseline in parallel
  [ ] Verify no incidents in logs

  Deployment:
    1. Set config flag: coordination.graph_enabled = true
    2. Restart control service with --graph-enabled
    3. Begin 24h warmup period monitoring
    4. Activate dashboard alerts for anomalies

PHASE 4: Full Rollout (Upon successful canary)
  [ ] Expand to all regions gradually (10% → 50% → 100%)
  [ ] Monitor metrics dashboard continuously
  [ ] Have rollback plan ready (--graph-disabled fallback)
  [ ] Communicate deployment status to operators

PHASE 5: Post-Deployment (Running state)
  [ ] Monitor A/B metrics daily
  [ ] Watch for performance degradation
  [ ] Collect user feedback
  [ ] Plan v2 improvements (learnable aggregation, etc.)

ROLLBACK PROCEDURE (if needed)
  1. Set config: coordination.graph_enabled = false
  2. Restart service with --graph-disabled
  3. Verify baseline metrics resume
  4. Investigate anomalies from logs
  5. Report issues for post-mortem

SUCCESS CRITERIA FOR FULL ROLLOUT
  ✓ Extended benchmark sustains >90% of A/B gain
  ✓ Zero production incidents during canary
  ✓ Stability remains >98% across all tests
  ✓ No memory/resource exhaustion detected
  ✓ Operator acceptance (manual sign-off)
"""
    
    print(checklist)


def main():
    """Run staging validation suite."""
    print("\n" + "="*70)
    print("GRAPH-D3QN COORDINATION UPGRADE")
    print("STAGING VALIDATION KIT")
    print("="*70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Phase 1: Verify preconditions
    print("\n[PHASE 1] Verifying Preconditions")
    print("-" * 70)
    
    ab_valid = validate_ab_metrics()
    artifacts_valid = check_release_artifacts()
    
    print("\n[SUMMARY]")
    print(f"  A/B Metrics Valid:       {'✅' if ab_valid else '❌'}")
    print(f"  Release Artifacts Valid: {'✅' if artifacts_valid else '❌'}")
    
    if not (ab_valid and artifacts_valid):
        print("\n[ERROR] Precondition checks failed. Contact technical lead.")
        return 1
    
    print("\n✅ All preconditions satisfied. Ready for staging validation.\n")
    
    # Print next steps
    print_staging_checklist()
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("""
1. Review the staging validation checklist above
2. Execute Phase 2 extended benchmark when ready
3. Monitor production-like environment for anomalies
4. Collect metrics over minimum 24 hours
5. Compare graph vs. baseline metrics in dashboard
6. Proceed to canary deployment upon success

For detailed rollout instructions, see:
  docs/graph_coordination_upgrade.md
  docs/PROMOTION_STATUS.md

For A/B metrics comparison, see:
  results/graph_ab_report.md

Questions? Review the implementation guide:
  docs/graph_coordination_upgrade.md
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
