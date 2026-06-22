from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fetch_json(url: str, timeout: int = 5) -> Any:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def build_waiting_row(ts: str, item: Dict[str, Any]) -> Dict[str, Any]:
    lane_waits = item.get("lane_waiting", {}) or {}
    return {
        "timestamp": ts,
        "junction_id": item.get("junction_id", ""),
        "mode": item.get("mode", ""),
        "phase": item.get("phase", ""),
        "is_corridor": bool(item.get("is_corridor", False)),
        "avg_waiting_time_s": safe_float(item.get("avg_waiting_time", 0.0)),
        "north_wait_s": safe_float(lane_waits.get("north", 0.0)),
        "south_wait_s": safe_float(lane_waits.get("south", 0.0)),
        "east_wait_s": safe_float(lane_waits.get("east", 0.0)),
        "west_wait_s": safe_float(lane_waits.get("west", 0.0)),
        "queue_length": safe_float(item.get("queue_length", 0.0)),
        "vehicle_count": safe_float(item.get("vehicle_count", 0.0)),
    }


def build_corridor_rows(ts: str, active_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not active_events:
        rows.append(
            {
                "timestamp": ts,
                "event_id": "",
                "vehicle_id": "",
                "vehicle_type": "",
                "current_junction": "",
                "eta_seconds": "",
                "path": "",
                "active": False,
            }
        )
        return rows

    for e in active_events:
        path = e.get("path", []) or []
        rows.append(
            {
                "timestamp": ts,
                "event_id": e.get("event_id", ""),
                "vehicle_id": e.get("vehicle_id", ""),
                "vehicle_type": e.get("vehicle_type", ""),
                "current_junction": e.get("current_junction", ""),
                "eta_seconds": safe_float(e.get("eta_seconds", 0.0)),
                "path": " -> ".join(path),
                "active": True,
            }
        )
    return rows


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, waiting_rows: List[Dict[str, Any]], corridor_rows: List[Dict[str, Any]]) -> None:
    by_junction: Dict[str, List[float]] = {}
    for r in waiting_rows:
        by_junction.setdefault(r["junction_id"], []).append(safe_float(r["avg_waiting_time_s"]))

    lines = []
    lines.append("NEXUS-ATMS Waiting Time and Green Corridor Summary")
    lines.append(f"Generated: {now_iso()}")
    lines.append("")
    lines.append("Average waiting time by junction (seconds):")
    lines.append("junction_id, avg_wait_s, min_wait_s, max_wait_s, samples")
    for jid in sorted(by_junction.keys()):
        vals = by_junction[jid]
        avg_v = sum(vals) / len(vals) if vals else 0.0
        min_v = min(vals) if vals else 0.0
        max_v = max(vals) if vals else 0.0
        lines.append(f"{jid}, {avg_v:.2f}, {min_v:.2f}, {max_v:.2f}, {len(vals)}")

    active_count = sum(1 for r in corridor_rows if r.get("active") is True)
    lines.append("")
    lines.append(f"Green corridor active rows: {active_count}")
    lines.append("Note: If this is 0, no emergency corridor was active during the capture window.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect time-series waiting time at all junctions and green-corridor data"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--out-dir", default="results/research_tables")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    out_dir = Path(args.out_dir)

    waiting_rows: List[Dict[str, Any]] = []
    corridor_rows: List[Dict[str, Any]] = []

    start = time.time()
    end = start + max(1, args.seconds)

    print(f"[collect] start={now_iso()} duration={args.seconds}s interval={args.interval}s")

    while time.time() < end:
        ts = now_iso()
        try:
            intersections = fetch_json(f"{base}/api/intersections", timeout=8)
            if isinstance(intersections, list):
                for item in intersections:
                    waiting_rows.append(build_waiting_row(ts, item))
            else:
                print(f"[warn] /api/intersections returned non-list at {ts}")
        except Exception as exc:
            print(f"[warn] intersections fetch failed at {ts}: {exc}")

        try:
            active = fetch_json(f"{base}/api/emergency/active", timeout=8)
            if isinstance(active, list):
                corridor_rows.extend(build_corridor_rows(ts, active))
            else:
                print(f"[warn] /api/emergency/active returned non-list at {ts}")
        except Exception as exc:
            print(f"[warn] emergency fetch failed at {ts}: {exc}")

        time.sleep(max(0.5, args.interval))

    waiting_csv = out_dir / "waiting_time_all_junctions_timeseries.csv"
    corridor_csv = out_dir / "green_corridor_timeseries.csv"
    summary_txt = out_dir / "waiting_corridor_summary.txt"

    write_csv(waiting_csv, waiting_rows)
    write_csv(corridor_csv, corridor_rows)
    write_summary(summary_txt, waiting_rows, corridor_rows)

    print(f"[done] waiting rows: {len(waiting_rows)} -> {waiting_csv}")
    print(f"[done] corridor rows: {len(corridor_rows)} -> {corridor_csv}")
    print(f"[done] summary -> {summary_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
