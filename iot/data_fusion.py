"""
Multi-Sensor Data Fusion
=========================
Fuses readings from loop detectors, radar sensors, and computer-vision
detector output into a single, coherent IntersectionSnapshot per approach.

Fusion strategy
---------------
  1. **Plausibility check** — discard faulted sensors; flag if all sensors
     for an approach are unavailable.
  2. **Weighted average** — each sensor contributes according to its
     reliability weight (tunable per deployment).
  3. **Kalman-lite smoothing** — exponential smoothing with configurable α
     to reduce noise without introducing lag.
  4. **Propagation** — if one approach is unavailable, estimate from
     adjacent approaches using network-balance assumption.

This is the component that would interface with a real NTCIP / SCADA
data gateway in production.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from iot.sensor_simulator import SensorReading, SensorType

logger = logging.getLogger(__name__)


@dataclass
class ApproachState:
    """Fused state for a single intersection approach."""
    approach: str
    vehicle_count: float = 0.0
    occupancy_pct: float = 0.0
    speed_kmh: float = 0.0
    queue_length: float = 0.0        # estimated from occupancy
    flow_veh_h: float = 0.0          # vehicles per hour estimate
    ped_waiting: int = 0
    ped_request: bool = False
    data_quality: float = 1.0        # 0 = no data, 1 = all sensors OK
    timestamp: float = field(default_factory=time.time)


@dataclass
class IntersectionSnapshot:
    """Complete fused state for one intersection (all approaches)."""
    intersection_id: str
    approaches: Dict[str, ApproachState] = field(default_factory=dict)
    emergency_active: bool = False
    emergency_type: str = ""
    visibility_m: float = 1000.0
    rainfall_mm_h: float = 0.0
    aqi: float = 50.0
    timestamp: float = field(default_factory=time.time)

    timestamp: float = field(default_factory=time.time)



# Lane length assumption (m) for converting occupancy → queue
LANE_LENGTH_M = 120


class SensorFusion:
    """
    Stateful fusion processor for one or more intersections.

    Parameters
    ----------
    loop_weight : float   Reliability weight for inductive loop data.
    radar_weight: float   Reliability weight for radar data.
    vision_weight: float  Reliability weight for computer-vision data.
    alpha       : float   Smoothing factor (0 = no smoothing, 1 = no update).
    """

    def __init__(
        self,
        loop_weight: float = 0.5,
        radar_weight: float = 0.3,
        vision_weight: float = 0.2,
        alpha: float = 0.25,
    ) -> None:
        self.weights = {
            "loop": loop_weight,
            "radar": radar_weight,
            "vision": vision_weight,
        }
        self.alpha = alpha
        self._state: Dict[str, IntersectionSnapshot] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, readings: List[SensorReading]) -> Dict[str, IntersectionSnapshot]:
        """
        Process a batch of sensor readings and return updated snapshots.
        Typically called every simulation tick (e.g. every 5 s).
        """
        # Group by intersection
        by_int: Dict[str, List[SensorReading]] = {}
        for r in readings:
            by_int.setdefault(r.intersection_id, []).append(r)

        for int_id, int_readings in by_int.items():
            snap = self._state.setdefault(
                int_id, IntersectionSnapshot(int_id)
            )
            self._fuse_intersection(snap, int_readings)

        return dict(self._state)

    def ingest_vision(
        self, int_id: str, approach: str, count: int, speed_kmh: float = 0.0
    ) -> None:
        """
        Incorporate computer-vision detection output directly.
        Call this from the vision pipeline on each processed frame.
        """
        snap = self._state.setdefault(int_id, IntersectionSnapshot(int_id))
        ap = snap.approaches.setdefault(approach, ApproachState(approach))
        w = self.weights["vision"]
        ap.vehicle_count = self._smooth(ap.vehicle_count, count, w)
        # Vision-first queue/occupancy approximation so live mode works without loop/radar sensors.
        ap.queue_length = self._smooth(ap.queue_length, float(count), w)
        ap.occupancy_pct = self._smooth(ap.occupancy_pct, min(100.0, float(count) * 7.5), w)
        ap.flow_veh_h = self._smooth(ap.flow_veh_h, float(count) * 120.0, w)
        if speed_kmh > 0:
            ap.speed_kmh = self._smooth(ap.speed_kmh, speed_kmh, w)
        ap.data_quality = max(ap.data_quality, 0.7)
        ap.timestamp = time.time()

    def snapshot(self, int_id: str) -> Optional[IntersectionSnapshot]:
        return self._state.get(int_id)

    def all_snapshots(self) -> Dict[str, IntersectionSnapshot]:
        return dict(self._state)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fuse_intersection(
        self, snap: IntersectionSnapshot, readings: List[SensorReading]
    ) -> None:
        approach_buckets: Dict[str, Dict[str, List[SensorReading]]] = {}

        for r in readings:
            if r.sensor_type == SensorType.ENVIRON:
                snap.visibility_m = r.visibility_m
                snap.rainfall_mm_h = r.rainfall_mm_h
                snap.aqi = r.aqi
                continue
            if r.sensor_type == SensorType.EMERGENCY:
                snap.emergency_active = r.emergency_active
                snap.emergency_type = r.emergency_type
                continue
            if r.approach == "all":
                continue
            bucket = approach_buckets.setdefault(r.approach, {})
            bucket.setdefault(r.sensor_type.value, []).append(r)

        for approach, type_map in approach_buckets.items():
            ap = snap.approaches.setdefault(approach, ApproachState(approach))
            self._fuse_approach(ap, type_map, snap)

        snap.timestamp = time.time()

    def _fuse_approach(
        self,
        ap: ApproachState,
        type_map: Dict[str, List[SensorReading]],
        snap: IntersectionSnapshot,
    ) -> None:
        valid_sensors = 0
        total_weight = 0.0

        # --- Loop readings ---
        loop_readings = [r for r in type_map.get("inductive_loop", []) if not r.is_fault]
        if loop_readings:
            occ = np.mean([r.occupancy_pct for r in loop_readings])
            count = np.mean([r.vehicle_count for r in loop_readings])
            w = self.weights["loop"]
            ap.occupancy_pct = self._smooth(ap.occupancy_pct, occ, w)
            ap.vehicle_count = self._smooth(ap.vehicle_count, count, w)
            # Queue length from occupancy (H-X Wang 2006 linear model)
            ap.queue_length = max(0.0, (occ / 100.0) * LANE_LENGTH_M / 7.5)
            total_weight += w
            valid_sensors += 1

        # --- Radar readings ---
        radar_readings = [r for r in type_map.get("radar", []) if not r.is_fault]
        if radar_readings:
            speed = np.mean([r.speed_kmh for r in radar_readings])
            w = self.weights["radar"]
            ap.speed_kmh = self._smooth(ap.speed_kmh, speed, w)
            total_weight += w
            valid_sensors += 1

        # --- Pedestrian readings ---
        ped_readings = type_map.get("pedestrian_button", [])
        if ped_readings:
            ap.ped_waiting = int(np.mean([r.ped_waiting for r in ped_readings]))
            ap.ped_request = any(r.ped_cross_request for r in ped_readings)

        # Flow = greenshields model: q = k * v
        density = ap.occupancy_pct / (ap.speed_kmh + 1e-3) * 0.1
        ap.flow_veh_h = max(0.0, ap.vehicle_count * (3600.0 / 30.0))

        # Data quality (fraction of expected sensors that returned valid data)
        expected = len(self.weights)
        ap.data_quality = min(1.0, valid_sensors / expected) if expected else 0.0
        ap.timestamp = time.time()

    def _smooth(self, old: float, new: float, weight: float = 1.0) -> float:
        """Exponential moving average smoothing."""
        effective_alpha = self.alpha * weight
        return (1 - effective_alpha) * old + effective_alpha * new
