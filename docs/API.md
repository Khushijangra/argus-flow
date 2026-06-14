# NEXUS-ATMS API Documentation

This document outlines the internal and external endpoints provided by the NEXUS-ATMS FastAPI backend.

## API Design Principles

- **Backward Compatibility**: All endpoints are designed to maintain zero-regression backward compatibility with existing front-end dashboard payloads.
- **Schema Stability**: Pydantic models enforce strict data validation. Any future versioning will be introduced via `/api/v2/` prefixes rather than mutating existing structures.
- **Zero-Regression Migration Goals**: The backend monolith has been refactored into a modular architecture (`api/`, `services/`, `core/`). The Strangler Fig pattern was employed to ensure existing `LiveRuntime` consumers experienced zero downtime or payload mutation during the architectural transition.

---

## 🟢 Health Endpoints
**Relevant Module**: `backend/api/health.py`

### `GET /`
- **Purpose**: Root application health check.
- **Auth**: None
- **Request Body**: None
- **Response**: `{"status": "NEXUS ATMS running"}`

### `GET /api/health` (also mapped to `/health`)
- **Purpose**: Readiness probe for CI/CD and container orchestrators.
- **Auth**: None
- **Request Body**: None
- **Response**: `{"status": "ok"}`

### `GET /ping`
- **Purpose**: Liveness heartbeat check.
- **Auth**: None
- **Request Body**: None
- **Response**: `{"status": "ok"}`

---

## 🚦 Traffic & Simulation Endpoints
**Relevant Module**: `backend/api/traffic.py`

### `GET /api/status`
- **Purpose**: Retrieves the top-level status of the RL engine, runtime modes, and active components.
- **Auth**: None
- **Request Body**: None
- **Response**: JSON containing `status`, `mode`, `demo_mode`, `components`, `metrics`.

### `GET /api/intersections`
- **Purpose**: List all connected SUMO/Camera intersections and their macro-state.
- **Auth**: None
- **Request Body**: None
- **Response**: Dictionary mapping junction IDs to payload objects containing `vehicle_count`, `current_phase`, and `live_mode`.

### `GET /api/junctions/{id}/state`
- **Purpose**: Fetch detailed telemetry for a specific junction ID.
- **Auth**: None
- **Request Body**: None
- **Response**: `JunctionState` JSON representation including queued vehicles and camera orientation.

### `GET /api/snapshot`
- **Purpose**: Fetch the last known global traffic snapshot across the entire network.
- **Auth**: None
- **Request Body**: None
- **Response**: `_last_traffic_snapshot` global cache.

### `GET /api/history`
- **Purpose**: Time-series historical data (last N hours) for throughput and wait times.
- **Auth**: None
- **Request Body**: None
- **Response**: Aggregated array of historical data points.

### `POST /api/junctions/select`
- **Purpose**: Sets the active dashboard focus to a specified junction.
- **Auth**: None
- **Request Body**: `{"junction_id": "J1_1"}`
- **Response**: `{"status": "ok", "selected": "J1_1"}`

### `POST /api/mode/set`
- **Purpose**: Changes the global operating mode (e.g., fallback, manual).
- **Auth**: Requires `CONTROL_API_KEY` header if `HARDENED_MODE` is enabled.
- **Request Body**: `{"mode": "ai" | "manual" | "emergency"}`
- **Response**: Status confirmation of mode transition.

### `GET /api/live/camera/stream`
- **Purpose**: Streams active video feeds (MJPEG) based on the currently selected junction.
- **Auth**: None
- **Response**: `StreamingResponse` (multipart/x-mixed-replace).

### `GET /api/live/camera/{id}/{direction}/snapshot`
- **Purpose**: Returns a single static JPEG frame for external consumption.
- **Auth**: None
- **Response**: `Response(media_type="image/jpeg")`

### `POST /api/live/upload_video`
- **Purpose**: Upload an MP4 video file to bypass camera/simulator streams for demo processing.
- **Auth**: None
- **Request Body**: `UploadFile` (multipart/form-data)
- **Response**: `{"status": "ok", "filename": "uploaded.mp4"}`

### `DELETE /api/live/clear_uploaded_video`
- **Purpose**: Reverts the video source back to the default camera or simulation.
- **Auth**: None
- **Response**: `{"status": "cleared"}`

---

## 🛑 Signals & Override Endpoints
**Relevant Module**: `backend/api/signals.py`

### `POST /api/signal/override`
- **Purpose**: Force a specific traffic light phase at a specific junction. Bypasses the AI.
- **Auth**: Requires `CONTROL_API_KEY` header if `HARDENED_MODE` is enabled.
- **Request Body**: `SignalOverrideRequest(junction_id: str, phase: str, duration: int)`
- **Response**: `{"status": "override_accepted", "junction": id}`

### `POST /api/nl/command`
- **Purpose**: Parses Natural Language string and converts it into a structural signal override command.
- **Auth**: Requires `CONTROL_API_KEY` header if `HARDENED_MODE` is enabled.
- **Request Body**: `NLCommandRequest(command: str)`
- **Response**: `NLCommandResponse(action: str, target_junction: str, parameters: dict, success: bool, message: str)`

---

## 🚑 Emergency Corridors
**Relevant Module**: `backend/api/emergency.py`

### `POST /api/emergency/activate`
- **Purpose**: Activates a multi-junction green-wave corridor for an approaching emergency vehicle.
- **Auth**: Requires `CONTROL_API_KEY` header if `HARDENED_MODE` is enabled.
- **Request Body**: `EmergencyActivateRequest(vehicle_id: str, route: List[str], priority: str)`
- **Response**: `{"status": "activated", "corridor_id": str}`

### `GET /api/emergency/active`
- **Purpose**: Retrieves a list of all currently active emergency corridors.
- **Auth**: None
- **Request Body**: None
- **Response**: `{"active_corridors": List[EmergencyState]}`

---

## 📈 Analytics & XAI Endpoints
**Relevant Module**: `backend/api/analytics.py`

### `GET /api/carbon/today`
- **Purpose**: Calculate total daily CO₂ emission reductions from idle time optimization.
- **Auth**: None
- **Response**: `{"emissions_saved_kg": float, "equivalency": str}`

### `GET /api/carbon/certificate`
- **Purpose**: Generates a PDF certificate demonstrating ESG savings.
- **Auth**: None
- **Response**: PDF binary stream.

### `GET /api/ai/status`
- **Purpose**: Fetches the health, loss, and reward status of the active D3QN engine.
- **Auth**: None
- **Response**: Model telemetry JSON.

### `GET /api/ai/explain_decision`
- **Purpose**: Generates a SHAP explanation for why the RL agent took the most recent action.
- **Auth**: None
- **Response**: JSON array of feature importance (e.g., `QueueLength_N` contribution).

### `GET /api/ai/anomaly/results`
- **Purpose**: Returns recent flags triggered by the ensemble anomaly detector.
- **Auth**: None
- **Response**: JSON array of anomaly events.

---

## 🔌 WebSocket Streams
**Relevant Module**: `backend/api/websockets.py`

### `WS /ws/live`
- **Purpose**: Main unified ~1Hz telemetry broadcast socket for the dashboard.
- **Payload Structure**: `{timestamp: float, frame_id: int, system_state: dict}`
- **Auth**: None

### `WS /ws`
- **Purpose**: Legacy fallback stream for older dashboard clients.
- **Payload Structure**: `{...legacy dict format...}`
- **Auth**: None
