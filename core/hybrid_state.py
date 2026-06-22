"""
NEXUS-ATMS Dedicated State-Management Layer
===========================================
Decouples canonical platform state from IoT parsers and RL environments.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
import numpy as np


class HybridStateBuilder:
    """Builds the Canonical Hybrid State V1."""

    @staticmethod
    def build_from_telemetry(
        intersection_id: str,
        approaches: Dict[str, Any],
        phase_index: int = 0,
        phase_name: str = "NS_GREEN",
        elapsed_s: float = 0.0,
        ped_active: bool = False,
        emergency_active: bool = False,
        anomalies: Optional[List[Dict[str, Any]]] = None,
        weather: Optional[Dict[str, float]] = None,
        neighbors: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Constructs the canonical JSON-serializable state object.
        """
        state = {
            "$schema": "nexus-hybrid-state-v1",
            "intersection_id": intersection_id,
            "timestamp_ms": int(time.time() * 1000),
            "traffic": {},
            "signals": {
                "current_phase": phase_name,
                "phase_index": phase_index,
                "elapsed_s": elapsed_s,
                "pedestrian_request_active": ped_active,
            },
            "anomalies": anomalies or [],
            "environment": {
                "emergency_active": emergency_active,
                "weather": weather or {"rainfall_mm_h": 0.0, "visibility_m": 1000.0},
            },
            "network_topology": {
                "neighbors": neighbors or {"north": None, "south": None, "east": None, "west": None}
            },
        }

        # Populate traffic telemetry per approach
        for ap in ("north", "south", "east", "west"):
            st = approaches.get(ap)
            if st:
                state["traffic"][ap] = {
                    "queue_length": getattr(st, "queue_length", 0.0),
                    "wait_time_s": getattr(st, "wait_time", getattr(st, "vehicle_count", 0.0)),  # Fallback approximation if wait not tracked natively by IoT
                    "occupancy_pct": getattr(st, "occupancy_pct", 0.0),
                    "speed_kmh": getattr(st, "speed_kmh", 0.0),
                    "arrival_rate": getattr(st, "flow_veh_h", 0.0) / 3600.0,  # vehicles per second
                }
            else:
                state["traffic"][ap] = {
                    "queue_length": 0.0,
                    "wait_time_s": 0.0,
                    "occupancy_pct": 0.0,
                    "speed_kmh": 0.0,
                    "arrival_rate": 0.0,
                }
                
        return state


class RLObservationMapper:
    """Transforms Canonical Hybrid State into the fixed 28-dim PyTorch array."""

    @staticmethod
    def to_vector(hybrid_state: Dict[str, Any]) -> np.ndarray:
        """
        Converts the state into a 28-dimensional normalized vector.
        """
        obs = np.zeros(28, dtype=np.float32)

        traffic = hybrid_state.get("traffic", {})
        anomalies = hybrid_state.get("anomalies", [])
        signals = hybrid_state.get("signals", {})
        environment = hybrid_state.get("environment", {})
        
        # Helper to get anomaly severity for a specific lane
        def _get_anomaly_severity(lane: str) -> float:
            for a in anomalies:
                if a.get("lane") == lane:
                    return float(a.get("severity", 0.0))
            return 0.0

        # Indices 0-19: Traffic and Anomalies per approach
        # Format per approach: [Queue, Wait, Occupancy, Flow, Anomaly]
        approach_order = ("north", "south", "east", "west")
        for i, ap in enumerate(approach_order):
            base_idx = i * 5
            ap_data = traffic.get(ap, {})
            
            # 1. Queue (normalize max 30m)
            obs[base_idx + 0] = min(1.0, float(ap_data.get("queue_length", 0.0)) / 30.0)
            # 2. Wait (normalize max 180s)
            obs[base_idx + 1] = min(1.0, float(ap_data.get("wait_time_s", 0.0)) / 180.0)
            # 3. Occupancy (normalize max 100%)
            obs[base_idx + 2] = min(1.0, float(ap_data.get("occupancy_pct", 0.0)) / 100.0)
            # 4. Arrival Rate (normalize max 1.0 veh/s)
            obs[base_idx + 3] = min(1.0, float(ap_data.get("arrival_rate", 0.0)))
            # 5. Anomaly Severity (already 0.0-1.0)
            obs[base_idx + 4] = min(1.0, max(0.0, _get_anomaly_severity(ap)))

        # Indices 20-23: Phase One-hot
        phase_idx = int(signals.get("phase_index", 0))
        if 0 <= phase_idx <= 3:
            obs[20 + phase_idx] = 1.0
            
        # Index 24: Phase Elapsed Time
        obs[24] = min(1.0, float(signals.get("elapsed_s", 0.0)) / 60.0)
        
        # Index 25: Time of Day
        ts = hybrid_state.get("timestamp_ms", 0)
        hour = (ts / 3600000.0) % 24.0
        obs[25] = hour / 24.0
        
        # Index 26: Emergency Flag
        obs[26] = 1.0 if environment.get("emergency_active", False) else 0.0
        
        # Index 27: Pedestrian Request Flag
        obs[27] = 1.0 if signals.get("pedestrian_request_active", False) else 0.0

        return obs
