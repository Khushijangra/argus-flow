from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.demo_data import DemoDataGenerator, JUNCTION_IDS


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def row_group(junction_id: str) -> str:
    row = int(junction_id.split("_")[0][1:])
    return f"J{row}"


def write_csv(path: Path, rows: List[Dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_long_rows(snapshot: Dict, tick: int) -> List[Dict]:
    rows: List[Dict] = []
    ts = now_iso()
    for jid in JUNCTION_IDS:
        j = snapshot["junctions"][jid]
        waits = j.get("lane_waiting", {})
        rows.append(
            {
                "Time": ts,
                "Tick": tick,
                "Junction": jid,
                "Mode": j.get("mode", ""),
                "Phase": j.get("phase", ""),
                "WaitingTime_s": round(float(j.get("waiting_time", 0.0)), 2),
                "NorthWait_s": round(float(waits.get("north", 0.0)), 2),
                "SouthWait_s": round(float(waits.get("south", 0.0)), 2),
                "EastWait_s": round(float(waits.get("east", 0.0)), 2),
                "WestWait_s": round(float(waits.get("west", 0.0)), 2),
                "QueueLength": round(float(j.get("queue_length", 0.0)), 2),
                "VehicleCount": int(j.get("vehicle_count", 0)),
                "IsCorridor": bool(j.get("is_corridor", False)),
            }
        )
    return rows


def build_wide_rows(snapshot: Dict, tick: int) -> Dict:
    ts = now_iso()
    groups: Dict[str, List[float]] = {"J0": [], "J1": [], "J2": [], "J3": []}
    for jid in JUNCTION_IDS:
        groups[row_group(jid)].append(float(snapshot["junctions"][jid]["waiting_time"]))

    return {
        "Time": ts,
        "Tick": tick,
        "J0": round(sum(groups["J0"]) / len(groups["J0"]), 2),
        "J1": round(sum(groups["J1"]) / len(groups["J1"]), 2),
        "J2": round(sum(groups["J2"]) / len(groups["J2"]), 2),
        "J3": round(sum(groups["J3"]) / len(groups["J3"]), 2),
        "AvgWait": round(float(snapshot.get("avg_waiting_time", 0.0)), 2),
        "Phase": snapshot.get("phase", ""),
        "Mode": snapshot.get("mode", ""),
    }


def build_corridor_rows(snapshot: Dict, tick: int) -> List[Dict]:
    rows: List[Dict] = []
    ts = now_iso()
    corridor = snapshot.get("corridor", {}) or {}
    if not corridor.get("active", False):
        return rows

    path = corridor.get("path", []) or []
    before = float(corridor.get("delay_before_s", 0.0))
    after = float(corridor.get("delay_after_s", 0.0))
    for jid in path:
        rows.append(
            {
                "Time": ts,
                "Tick": tick,
                "Junction": jid,
                "Action": "green_corridor_override",
                "DelayBefore_s": round(before, 2),
                "DelayAfter_s": round(after, 2),
                "VehicleType": corridor.get("vehicle_type", "ambulance"),
                "VehicleId": corridor.get("vehicle_id", ""),
                "EventId": corridor.get("event_id", ""),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate realistic nonzero traffic tables")
    parser.add_argument("--ticks", type=int, default=24)
    parser.add_argument("--mode", default="rl", choices=["baseline", "rl"])
    parser.add_argument("--out-dir", default="results/nonzero_demo_tables")
    parser.add_argument("--activate-corridor", action="store_true")
    args = parser.parse_args()

    gen = DemoDataGenerator(mode=args.mode)
    if args.activate_corridor:
        gen.activate_green_corridor()

    out_dir = Path(args.out_dir)
    detailed_rows: List[Dict] = []
    wide_rows: List[Dict] = []
    corridor_rows: List[Dict] = []

    for tick in range(1, args.ticks + 1):
        snapshot = gen.get_snapshot()
        detailed_rows.extend(build_long_rows(snapshot, tick))
        wide_rows.append(build_wide_rows(snapshot, tick))
        corridor_rows.extend(build_corridor_rows(snapshot, tick))

    long_csv = out_dir / "junction_waiting_times_nonzero_detailed.csv"
    wide_csv = out_dir / "junction_waiting_times_nonzero_wide.csv"
    corridor_csv = out_dir / "green_corridor_events_nonzero.csv"
    summary_txt = out_dir / "nonzero_summary.txt"

    write_csv(long_csv, detailed_rows)
    write_csv(wide_csv, wide_rows)
    write_csv(corridor_csv, corridor_rows)

    waits = [float(r["AvgWait"]) for r in wide_rows]
    avg_wait = sum(waits) / len(waits) if waits else 0.0
    min_wait = min(waits) if waits else 0.0
    max_wait = max(waits) if waits else 0.0
    corridor_count = len(corridor_rows)

    summary_lines = [
        "NEXUS-ATMS Nonzero Junction Demo Data",
        f"Mode: {args.mode}",
        f"Ticks: {args.ticks}",
        f"Detailed rows: {len(detailed_rows)}",
        f"Wide rows: {len(wide_rows)}",
        f"Corridor rows: {corridor_count}",
        f"Average waiting time: {avg_wait:.2f} s",
        f"Minimum waiting time: {min_wait:.2f} s",
        f"Maximum waiting time: {max_wait:.2f} s",
        "The generated data must resemble real urban traffic behavior and be suitable for academic research reporting.",
        "Source: DemoDataGenerator running traffic snapshot series with peak-hour and uneven junction loads.",
    ]
    summary_txt.write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"[done] {long_csv}")
    print(f"[done] {wide_csv}")
    print(f"[done] {corridor_csv}")
    print(f"[done] {summary_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
