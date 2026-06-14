# Backend Architecture

The backend of NEXUS-ATMS has been restructured to adhere to modern FastAPI standards, utilizing the Strangler Fig pattern for robust decoupling.

## Directory Structure
```
backend/
├── main.py              # Application entrypoint and middleware registration
├── dependencies.py      # Shared states, ConnectionManagers, and metrics
├── core/
│   ├── config.py        # Environment variables and configuration loaders
│   ├── logging.py       # Event auditing and consistency tracking
│   └── utils.py         # Dynamic imports and helper validations
├── api/
│   ├── health.py        # System uptime and schema endpoints
│   ├── traffic.py       # Snapshots, routing, and live video
│   ├── signals.py       # Overrides and LLM parsing bindings
│   ├── emergency.py     # Vehicle corridor allocation
│   ├── analytics.py     # Carbon metrics, baseline comparisons
│   └── maintenance.py   # Cybersecurity and worker payloads
└── services/
    └── traffic_service.py # LiveRuntime orchestrator and business logic
```

## Component Responsibilities

1. **`core/`**: Provides isolated utilities that do not rely on business domain concepts. It ensures modules fail gracefully (`_safe_import`) if the environment lacks dependencies (e.g., PyTorch).
2. **`dependencies.py`**: Acts as the single source of truth for global state matrices (`_junction_states`) to prevent circular dependencies.
3. **`services/`**: Holds the logic layer. `LiveRuntime` coordinates YOLO outputs, MQTT messages, and RL predictions.
4. **`api/`**: The presentation layer. Contains purely route-handling definitions using FastAPI `APIRouter`.
