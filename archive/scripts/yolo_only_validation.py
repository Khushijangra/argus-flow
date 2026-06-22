from __future__ import annotations

import argparse
import json
import time
from collections import Counter

import cv2
from ultralytics import YOLO


VEHICLE_CLASS_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def main() -> int:
    parser = argparse.ArgumentParser(description="YOLO-only object-class quality benchmark")
    parser.add_argument("--video", required=True, help="Path to input video file")
    parser.add_argument("--model", default="yolov8n.pt", help="Ultralytics model path/name")
    parser.add_argument("--frames", type=int, default=180, help="Max frames to evaluate")
    parser.add_argument("--stride", type=int, default=3, help="Sample every Nth frame")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(json.dumps({"ok": False, "error": f"Could not open video: {args.video}"}, indent=2))
        return 2

    model = YOLO(args.model)

    frame_idx = 0
    sampled = 0
    total_dets = 0
    latencies_ms = []
    confs = []
    cls_counter = Counter()
    vehicle_frames = 0

    while sampled < args.frames:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        if frame_idx % max(1, args.stride) != 0:
            continue

        t0 = time.perf_counter()
        res = model(frame, conf=args.conf, verbose=False)[0]
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(dt_ms)
        sampled += 1

        frame_vehicle_dets = 0
        for box in res.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in VEHICLE_CLASS_IDS:
                continue
            frame_vehicle_dets += 1
            total_dets += 1
            cls_counter[VEHICLE_CLASS_IDS[cls_id]] += 1
            confs.append(float(box.conf[0]))

        if frame_vehicle_dets > 0:
            vehicle_frames += 1

    cap.release()

    if not latencies_ms:
        print(json.dumps({"ok": False, "error": "No frames sampled"}, indent=2))
        return 3

    lat_sorted = sorted(latencies_ms)
    p95 = lat_sorted[int((len(lat_sorted) - 1) * 0.95)]
    avg_latency = sum(latencies_ms) / len(latencies_ms)
    avg_conf = (sum(confs) / len(confs)) if confs else 0.0

    out = {
        "ok": True,
        "video": args.video,
        "model": args.model,
        "sampled_frames": sampled,
        "sample_stride": args.stride,
        "conf_threshold": args.conf,
        "vehicle_detection_frames": vehicle_frames,
        "vehicle_detection_frame_rate": round(vehicle_frames / max(1, sampled), 4),
        "total_vehicle_detections": total_dets,
        "class_counts": dict(cls_counter),
        "avg_confidence": round(avg_conf, 4),
        "latency_ms": {
            "avg": round(avg_latency, 2),
            "p95": round(p95, 2),
            "min": round(min(latencies_ms), 2),
            "max": round(max(latencies_ms), 2),
        },
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
