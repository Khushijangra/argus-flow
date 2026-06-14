# Phase 6 Backend Migration Notes

## Objective
To decompose the monolithic `backend/main.py` file (~2,800 lines) into a standard FastAPI directory structure without causing any functional regressions.

## Migration Steps Performed

1. **Architecture Setup**
   - Created `backend/api/`, `backend/services/`, and `backend/core/` directories.
   - Extracted global configurations, API keys, and environment fallbacks into `backend/core/config.py`.
   - Extracted safe dynamic import wrappers and logging functions to `backend/core/utils.py` and `backend/core/logging.py`.
   - Created `backend/dependencies.py` to hold global shared states such as `_junction_states`, `ConnectionManager`, and metric caches, removing global variables from `main.py`.

2. **Endpoint Extraction (Strangler Fig Pattern)**
   - Extracted stateless endpoints (`root`, `health`, `ping`) to `backend/api/health.py`.
   - Migrated business logic related to traffic interpretation (e.g., `_congestion_from_density`, `_lane_distribution_from_snapshot`) to `backend/services/traffic_service.py`.
   - Extracted the massive `LiveRuntime` class (~800 lines) into `backend/services/traffic_service.py`.
   - Grouped and extracted remaining endpoints into specific modules:
     - `backend/api/traffic.py` (Snapshots, mapping, live video paths)
     - `backend/api/signals.py` (Signal overrides, natural language parser bindings)
     - `backend/api/emergency.py` (Emergency vehicle corridor logic)
     - `backend/api/analytics.py` (Carbon engine, metrics, AI prediction history)
     - `backend/api/maintenance.py` (Maintenance orders, cybersecurity simulations)
     - `backend/api/websockets.py` (Live payload broadcasting)

## Before vs. After Statistics
- **Original `main.py` Length**: 3186 lines (inclusive of imports/comments)
- **Current `main.py` Length**: ~852 lines (reduced by ~73%)

## Technical Debt / Unresolved Items
- `main.py` is currently at 852 lines. The user requirement is <= 300 lines. The remaining lines primarily consist of Pydantic models (e.g., `EmergencyActivateRequest`, `SignalOverrideRequest`) and singleton initialization routines (`_init_decision_engine`, `_init_junctions`).
- These models should ideally be moved to `backend/core/schemas.py`, but doing so using automated python slicing without a full AST-aware refactoring tool risks breaking the fastAPI request bodies. We are pausing here to verify functional stability before extracting the final 500 lines of data schemas.

## Verification
- Local FastAPI syntax checking succeeds (`import backend.main`).
- WebSocket connections and routes remain identical in namespace.
