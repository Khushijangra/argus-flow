"""
Real-World Traffic Intersection Environment (Gymnasium)
=======================================================
No SUMO.  No external simulator.  The intersection dynamics are modelled
from first principles using traffic flow theory:

  • **Queue model**     : discrete-time D/D/1 / stochastic overflow model
  • **Phase model**     : multi-phase signal with configurable phase structure
  • **Demand**          : configurable traffic demand curves
  • **Observation**     : sensor-realistic state (mimics what IoT data delivers)
  • **Reward**          : multi-objective (throughput, delay, stops, emissions, safety)
  • **Action space**    : choose next signal phase (not just keep/switch)

This environment is designed to work with REAL IoT data too — pass a
``SensorFusion`` snapshot as the observation source to drive on live data.

The same Gymnasium API means any SB3 or custom RL algorithm works.

Intersection model
------------------
  4 approaches (N, S, E, W), each with 1 lane.
  Standard NEMA-inspired 4-phase structure:
    Phase 0 — N↔S through  Phase 1 — N↔S left-turn
    Phase 2 — E↔W through  Phase 3 — E↔W left-turn
  (configurable to any phase structure)
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import gymnasium as gym
from gymnasium import spaces


# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------

@dataclass
class PhaseConfig:
    name: str
    green_approaches: List[str]        # approaches that receive green
    min_green: int = 10                # seconds
    max_green: int = 60
    yellow: int = 3
    ped_cross: bool = False            # is pedestrian crossing active?


@dataclass
class IntersectionConfig:
    intersection_id: str = "INT_001"
    n_lanes_per_approach: int = 1
    lane_length_m: float = 120.0       # effective queue storage (m)
    saturation_flow_veh_h: int = 1800  # per lane (typical urban arterial)
    free_flow_speed_kmh: float = 50.0
    cycle_time_budget: int = 120       # max cycle length (s)
    delta_time: int = 5                # sim seconds per agent step
    demand_profile: str = "rush_hour"  # rush_hour | normal | night | custom
    phases: Optional[List[PhaseConfig]] = None

    def __post_init__(self):
        if self.phases is None:
            self.phases = [
                PhaseConfig("NS_through", ["north", "south"], min_green=15, max_green=60),
                PhaseConfig("NS_left",    ["north", "south"], min_green=8,  max_green=30, ped_cross=True),
                PhaseConfig("EW_through", ["east",  "west"],  min_green=15, max_green=60),
                PhaseConfig("EW_left",    ["east",  "west"],  min_green=8,  max_green=30, ped_cross=True),
            ]


# -----------------------------------------------------------------------
# Demand models
# -----------------------------------------------------------------------

_DEMAND_PROFILES: Dict[str, Dict[str, float]] = {
    "rush_hour": {"north": 0.85, "south": 0.90, "east": 0.80, "west": 0.75},
    "normal":    {"north": 0.50, "south": 0.50, "east": 0.45, "west": 0.45},
    "night":     {"north": 0.15, "south": 0.15, "east": 0.12, "west": 0.12},
    "asymmetric":{"north": 0.90, "south": 0.40, "east": 0.70, "west": 0.30},
}


def _arrival_rate(approach: str, profile: str, hour: float) -> float:
    """Vehicles arriving per delta-time second at given hour (Poisson mean)."""
    base = _DEMAND_PROFILES.get(profile, _DEMAND_PROFILES["normal"]).get(approach, 0.5)
    # Superimpose realistic hour-of-day curve
    am = math.exp(-((hour - 8.25) ** 2) / 0.7)
    pm = math.exp(-((hour - 17.5) ** 2) / 0.6)
    tod = max(0.1, am * 0.95 + pm * 0.85 + 0.1)
    return base * tod  # vehicles per second


# -----------------------------------------------------------------------
# Environment
# -----------------------------------------------------------------------

APPROACHES = ("north", "south", "east", "west")
OBS_DIM = (
    len(APPROACHES) * 5   # queue, wait, occupancy, flow/arrivals, anomaly_severity
    + 4                   # current phase one-hot
    + 1                   # time since phase change (normalised)
    + 1                   # time of day (normalised hour)
    + 1                   # emergency flag
    + 1                   # ped_request flag
)  # = 28


class TrafficEnvironment(gym.Env):
    """
    Gymnasium environment modelling a real urban intersection.

    Observation shape : (26,)
    Action            : Discrete(n_phases)  — select next signal phase
    Render mode       : "human" (ASCII) | "rgb_array" (not implemented yet)

    Key differences from SUMO-based env:
      - Uses queueing-theory dynamics (real-world deployable)
      - Phase selection (not just keep/switch)
      - Pedestrian cross requests
      - Emergency vehicle preemption (external injection)
      - Reward includes CO₂ estimate and safety cost
    """

    metadata = {"render_modes": ["human"], "render_fps": 4}

    def __init__(
        self,
        config: Optional[IntersectionConfig] = None,
        render_mode: Optional[str] = None,
        sim_start_hour: float = 8.0,
        use_real_data_callback=None,   # callable() → IntersectionSnapshot
    ) -> None:
        super().__init__()

        self.cfg = config or IntersectionConfig()
        self.render_mode = render_mode
        self._sim_hour = sim_start_hour
        self._real_data_cb = use_real_data_callback
        self._rng = np.random.default_rng(42)

        n_phases = len(self.cfg.phases)
        self.action_space = spaces.Discrete(n_phases)
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(OBS_DIM,), dtype=np.float32
        )

        # Internal state
        self._queue: Dict[str, float] = {a: 0.0 for a in APPROACHES}
        self._wait:  Dict[str, float] = {a: 0.0 for a in APPROACHES}
        self._occ:   Dict[str, float] = {a: 0.0 for a in APPROACHES}
        self._arrivals: Dict[str, float] = {a: 0.0 for a in APPROACHES}
        self._anomaly_severity: Dict[str, float] = {a: 0.0 for a in APPROACHES}
        self._anomaly_timer: Dict[str, float] = {a: 0.0 for a in APPROACHES}
        self._anomaly_prob = 0.003  # targeting ~10% active time
        self._anomaly_multiplier = 0.5  # Reduced from 3.0 to ease learning
        
        # Reward tracking for delta metrics
        self._prev_wait: Dict[str, float] = {a: 0.0 for a in APPROACHES}
        self._prev_queue: Dict[str, float] = {a: 0.0 for a in APPROACHES}
        self._phase_age: Dict[int, float] = {p: 0.0 for p in range(len(self.cfg.phases))}

        self._current_phase: int = 0
        self._phase_elapsed: int = 0    # seconds
        self._step_count: int = 0
        self._max_steps: int = self.cfg.cycle_time_budget * 30   # ~30 cycles
        self._emergency: bool = False
        self._ped_request: bool = False

        # Telemetry
        self._total_throughput: int = 0
        self._total_delay_s: float = 0.0
        self._total_stops: int = 0
        self._episode_reward: float = 0.0

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(
        self, *, seed=None, options=None
    ) -> Tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        self._queue  = {a: float(self._rng.integers(0, 5)) for a in APPROACHES}
        self._wait   = {a: 0.0 for a in APPROACHES}
        self._occ    = {a: 0.0 for a in APPROACHES}
        self._arrivals = {a: 0.0 for a in APPROACHES}
        self._anomaly_severity = {a: 0.0 for a in APPROACHES}
        self._anomaly_timer = {a: 0.0 for a in APPROACHES}
        self._current_phase = 0
        self._phase_elapsed = 0
        self._step_count = 0
        self._emergency = False
        self._ped_request = False
        self._total_throughput = 0
        self._total_delay_s = 0.0
        self._total_stops = 0
        self._episode_reward = 0.0
        self._sim_hour = float(self._rng.uniform(6.5, 20.0))
        
        self._prev_wait = {a: 0.0 for a in APPROACHES}
        self._prev_queue = {a: 0.0 for a in APPROACHES}
        self._phase_age = {p: 0.0 for p in range(len(self.cfg.phases))}
        
        self._last_reward_terms = {}

        obs = self._build_obs()
        return obs, self._info()

    def step(
        self, action: int
    ) -> Tuple[np.ndarray, float, bool, bool, dict]:
        dt = self.cfg.delta_time

        # --- Phase transition ---
        old_phase = self._current_phase
        phase_cfg = self.cfg.phases[action]
        switching = action != old_phase
        if switching:
            # Yellow interval: no throughput, vehicles stop
            self._total_stops += int(sum(self._queue.values()))
        self._current_phase = action
        if switching:
            self._phase_elapsed = 0
        else:
            self._phase_elapsed += dt

        # --- Arrivals (Poisson) ---
        for ap in APPROACHES:
            rate = _arrival_rate(ap, self.cfg.demand_profile, self._sim_hour) * dt
            arrivals = int(self._rng.poisson(rate))
            self._arrivals[ap] = arrivals / dt  # per second
            self._queue[ap] += arrivals

        # --- Departures (green approaches) ---
        sat = self.cfg.saturation_flow_veh_h / 3600.0 * dt   # veh per step
        throughput_step = 0
        for ap in APPROACHES:
            if ap in phase_cfg.green_approaches:
                departed = min(self._queue[ap], sat)
                self._queue[ap] -= departed
                throughput_step += int(departed)
                self._wait[ap] = max(0.0, self._wait[ap] - dt * 0.8)
            else:
                self._wait[ap] += dt
                # Cap queue at lane storage
                max_q = self.cfg.lane_length_m / 6.0   # ~6 m/vehicle
                self._queue[ap] = min(self._queue[ap], max_q)

        self._total_throughput += throughput_step

        # --- Occupancy (proxy for density) ---
        max_q = self.cfg.lane_length_m / 6.0
        for ap in APPROACHES:
            self._occ[ap] = self._queue[ap] / max_q

        # Delay accumulation
        total_queue = sum(self._queue.values())
        self._total_delay_s += total_queue * dt

        # --- Anomalies (Stochastic Spawning & Decay) ---
        for ap in APPROACHES:
            if self._anomaly_timer[ap] > 0:
                self._anomaly_timer[ap] -= dt
                if self._anomaly_timer[ap] <= 0:
                    self._anomaly_timer[ap] = 0.0
                    self._anomaly_severity[ap] = 0.0
            else:
                if self._rng.random() < self._anomaly_prob:
                    self._anomaly_severity[ap] = self._rng.uniform(0.5, 1.0)
                    self._anomaly_timer[ap] = self._rng.uniform(30.0, 120.0)

        # Emergency / pedestrian stochastic events
        if self._rng.random() < 0.002:
            self._emergency = True
        elif self._emergency and self._rng.random() < 0.05:
            self._emergency = False
        self._ped_request = self._rng.random() < 0.15

        # Time advance
        self._sim_hour = (self._sim_hour + dt / 3600.0) % 24.0
        self._step_count += 1

         # 4. Advance phase age
        for p in range(len(self.cfg.phases)):
            if p == self._current_phase:
                self._phase_age[p] = 0.0
            else:
                self._phase_age[p] += self.cfg.delta_time

        # 5. Compute reward
        reward = self._compute_reward(throughput_step, switching)
        self._episode_reward += reward

        terminated = self._step_count >= self._max_steps
        truncated = False

        if self.render_mode == "human":
            self._render_ascii()

        obs = self._build_obs()
        return obs, reward, terminated, truncated, self._info()

    def inject_emergency(self, active: bool = True) -> None:
        """Externally inject or clear an emergency vehicle event."""
        self._emergency = active

    def inject_sensor_snapshot(self, snapshot) -> None:
        """Override internal state with real sensor data."""
        APPROACHES_LIST = list(APPROACHES)
        for ap in APPROACHES_LIST:
            s = snapshot.approaches.get(ap)
            if s:
                self._queue[ap] = s.queue_length
                self._occ[ap] = s.occupancy_pct / 100.0
                self._arrivals[ap] = s.flow_veh_h / 3600.0
        self._emergency = snapshot.emergency_active

    # ------------------------------------------------------------------
    # Reward
    # ------------------------------------------------------------------

    def _compute_reward(self, throughput: int, switching: bool) -> float:
        """
        Multi-objective reward:
          + throughput (normalised)
          - total waiting time
          - switching penalty (phase change costs yellow time)
          - queue overflow penalty
          - emission penalty (idling ∝ queue)
          + pedestrian service bonus
        """
        sat = self.cfg.saturation_flow_veh_h / 3600.0 * self.cfg.delta_time
        r_throughput  = throughput / (sat * len(APPROACHES) + 1e-3)
        
        # Delta wait and Delta queue
        r_wait = 0.0
        r_queue = 0.0
        for a in APPROACHES:
            wait_improvement = self._prev_wait[a] - self._wait[a]
            queue_improvement = self._prev_queue[a] - self._queue[a]
            
            # Normalize improvements
            r_wait += (1.0 + self._anomaly_multiplier * self._anomaly_severity[a]) * wait_improvement / 300.0
            r_queue += (1.0 + self._anomaly_multiplier * self._anomaly_severity[a]) * queue_improvement / 20.0
            
            self._prev_wait[a] = self._wait[a]
            self._prev_queue[a] = self._queue[a]
            
        # Switch penalty disabled for debugging
        r_switch      = 0.0
        r_overflow    = -1.0 if any(q > 18 for q in self._queue.values()) else 0.0
        r_emission    = -sum(self._queue.values()) * 0.005   # idling CO2 proxy
        r_ped         = 0.1 if self._ped_request and self.cfg.phases[self._current_phase].ped_cross else -0.05
        
        # Starvation penalty (60 seconds)
        r_starvation = 0.0
        for p, age in self._phase_age.items():
            if age > 60.0:
                r_starvation -= 1.0

        self._last_reward_terms = {
            "r_throughput": r_throughput * 0.35,
            "r_wait": r_wait * 0.25,
            "r_queue": r_queue * 0.20,
            "r_switch": r_switch,
            "r_overflow": r_overflow * 0.05,
            "r_emission": r_emission * 0.04,
            "r_ped": r_ped * 0.03,
            "r_starvation": r_starvation * 0.1
        }

        reward = sum(self._last_reward_terms.values())
        return float(reward)

    # ------------------------------------------------------------------
    # Observation builder
    # ------------------------------------------------------------------

    def _build_obs(self) -> np.ndarray:
        max_q = self.cfg.lane_length_m / 6.0
        max_w = 180.0   # seconds
        obs = []
        for ap in APPROACHES:
            obs.append(float(np.clip(self._queue[ap]   / max_q, 0, 1)))
            obs.append(float(np.clip(self._wait[ap]    / max_w, 0, 1)))
            obs.append(float(np.clip(self._occ[ap],             0, 1)))
            obs.append(float(np.clip(self._arrivals[ap]/ 0.5,   0, 1)))
            obs.append(float(np.clip(self._anomaly_severity[ap], 0, 1)))

        # Phase one-hot
        n_phases = len(self.cfg.phases)
        phase_oh = [0.0] * n_phases
        phase_oh[self._current_phase] = 1.0
        obs.extend(phase_oh)

        # Phase elapsed (normalised)
        obs.append(float(np.clip(self._phase_elapsed / 60.0, 0, 1)))
        # Time of day (normalised)
        obs.append(float(self._sim_hour / 24.0))
        # Flags
        obs.append(float(self._emergency))
        obs.append(float(self._ped_request))

        return np.array(obs, dtype=np.float32)

    # ------------------------------------------------------------------
    # Info & Render
    # ------------------------------------------------------------------

    def _info(self) -> dict:
        return {
            "throughput": self._total_throughput,
            "total_delay_s": round(self._total_delay_s, 1),
            "total_stops": self._total_stops,
            "queue": {a: round(self._queue[a], 1) for a in APPROACHES},
            "wait":  {a: round(self._wait[a],  1) for a in APPROACHES},
            "phase": self.cfg.phases[self._current_phase].name,
            "episode_reward": round(self._episode_reward, 3),
            "sim_hour": round(self._sim_hour, 2),
            "anomalies": {a: round(self._anomaly_severity[a], 2) for a in APPROACHES},
            "reward_terms": self._last_reward_terms,
        }

    def _render_ascii(self) -> None:
        ph = self.cfg.phases[self._current_phase].name
        q = " | ".join(f"{a}: {self._queue[a]:.0f}" for a in APPROACHES)
        print(f"[t={self._step_count:4d}] Phase={ph:14s}  Queue=[{q}]  "
              f"Reward={self._episode_reward:.2f}")
