import time
import collections
from typing import Dict, Any, Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self._active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._active.add(ws)

    def disconnect(self, ws: WebSocket):
        self._active.discard(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self._active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._active.discard(ws)

    @property
    def count(self) -> int:
        return len(self._active)

ws_manager = ConnectionManager()

# Global States
_junction_states: Dict[str, Dict] = {}
_signal_overrides: Dict[str, Dict] = {}
_selected_junction_id = "J1_1"
_session_started_at = time.time()
_session_metrics: Dict[str, float] = {
    "samples": 0,
    "ai_wait_sum": 0.0,
    "baseline_wait_sum": 0.0,
    "ai_idle_sum": 0.0,
    "baseline_idle_sum": 0.0,
    "queue_sum": 0.0,
    "saved_vehicle_minutes": 0.0,
    "emissions_saved_kg": 0.0,
}
_ai_decision_feed: collections.deque = collections.deque(maxlen=24)
_completed_emergency_events: collections.deque = collections.deque(maxlen=30)
_active_emergency_ids: Set[str] = set()
_incident_log: collections.deque = collections.deque(maxlen=80)
_audit_log: collections.deque = collections.deque(maxlen=5000)
_state_replay_buffer: collections.deque = collections.deque(maxlen=1800)
_frame_seq = 0
_last_tick_ms = int(time.time() * 1000)
_last_ws_tx_ms = 0.0
_last_traffic_snapshot: Dict[str, Any] = {}

# We will store LiveRuntime instance here later if needed, but for now we'll import it from main.
