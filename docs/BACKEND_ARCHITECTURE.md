# Backend Architecture

The NEXUS-ATMS backend is constructed using FastAPI and designed to handle high-frequency telemetry bridging between the AI traffic engine, SUMO simulation, YOLOv8 vision pipeline, and the live operator dashboard.

## Architecture Goals

The original prototype backend was housed in a single, monolithic `backend/main.py` file (~3,186 lines). While functional, this monolithic structure hindered testability, modular feature expansion, and readable dependency tracking.

**Refactoring Strategy**: The backend was refactored using the **Strangler Fig Pattern**. Endpoint routers, core configurations, and utilities were incrementally extracted from the monolith while preserving the `main.py` entrypoint. This guaranteed a Zero-Regression migration where existing components, including the highly-stateful `LiveRuntime`, did not experience breaking API changes or circular import crashes.

---

## Current Architecture

The backend now adheres to standard, modular API patterns:

### `backend/main.py`
The primary application entrypoint. It handles Uvicorn server initialization, FastAPI middleware configuration (CORS), router registration (`app.include_router()`), and application lifespan events (startup singletons and background loops).

### `backend/api/`
The presentation layer containing all REST and WebSocket route definitions. Endpoints are grouped strictly by domain (e.g., `traffic.py`, `signals.py`, `health.py`, `emergency.py`, `analytics.py`, `maintenance.py`, `websockets.py`). Routes handle HTTP validation and serialization, offloading business logic to the services layer.

### `backend/services/`
The business logic layer. The most critical component is `traffic_service.py`, which houses the `LiveRuntime` orchestrator. This layer coordinates asynchronous interactions between MQTT streams, PyTorch RL inferences, and camera rendering sequences.

### `backend/core/`
Stateless utility layers holding configurations (`config.py`), logging formatters (`logging.py`), Pydantic data schemas (`schemas.py`), and dynamic dependency loaders (`utils.py` for safe CV2/Torch imports).

### `backend/dependencies.py`
The global state and connection manager repository. 

---

## Request Lifecycle

When an operator or simulated vehicle interacts with the backend, the lifecycle flows systematically:

1. **Request**: An HTTP `POST` arrives (e.g., `POST /api/signal/override`).
2. **Router**: `backend/api/signals.py` intercepts the request, validates the JWT/API key against `CONTROL_API_KEY`, and parses the Pydantic schema.
3. **Service Layer**: The router calls the appropriate handler to inject the manual override instruction into the traffic control queue.
4. **Shared Dependencies**: The handler updates the globally tracked `_signal_overrides` dictionary inside `dependencies.py`.
5. **Response**: A confirmation payload is serialized and returned to the client.

---

## WebSocket Lifecycle

Live dashboard telemetry operates on a continuous WebSocket connection:

1. **Client Connection**: Dashboard connects to `ws://localhost:8080/ws/live`.
2. **ConnectionManager**: The request is routed to `backend/api/websockets.py`, accepted, and registered inside the globally shared `ws_manager` (from `dependencies.py`).
3. **State Updates**: The background `LiveRuntime` loop pulls predictions from the LSTM model, actions from the D3QN agent, and metrics from SUMO.
4. **Broadcast Flow**: Every ~1 second, `main.py`'s live tick broadcasts the unified state JSON payload to all connected clients in the `ws_manager.active` pool.
5. **Disconnection Handling**: On client disconnect or network timeout, a `WebSocketDisconnect` exception triggers the manager to safely unregister the client socket without blocking the simulation loop.

---

## Dependency Management

During the Strangler Fig refactor, circular imports posed a major threat because both `main.py` (broadcasting state) and `api/*.py` (modifying state) required access to the same globally mutating dictionaries.

To solve this, all shared caches (e.g., `_junction_states`, `_session_metrics`, `ConnectionManager`) were moved into an isolated `backend/dependencies.py` file. This acts as a single source of truth, enabling safe, bidirectional data flow between routers, background loops, and service orchestrators.

---

## Technical Debt

While the Strangler Fig migration successfully decoupled the presentation layer, minor technical debt remains:

- **Startup Singleton Concentration**: The `main.py` startup event still manually initializes several monolithic singleton agents (e.g., `_init_decision_engine`, `emergency_engine`). Moving these to a dedicated dependency injection container would improve testability.
- **Legacy Compatibility Hooks**: The `/ws` endpoint (legacy websocket format) is maintained purely for backward compatibility with older dashboard scripts. Once all dashboard consumers transition to `/ws/live`, this route can be safely deprecated.
