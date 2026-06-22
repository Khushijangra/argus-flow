# EVOLUTION FORENSICS AUDIT
## Document 7: BACKEND_FORENSICS.md

### Backend Service Audit

The FastAPI backend (`main.py` and `hybrid_runtime.py`) serves as the bridge between the mathematically robust Phase A models and the highly visual Phase B frontend.

#### Endpoint Traceability

| Endpoint | Caller | Purpose | Status |
| :--- | :--- | :--- | :--- |
| `GET /api/health` | Browser/Tester | Basic liveliness check. | **REAL**. |
| `WS /ws` | Frontend (`useNexusStream`) | Broadcasts 5Hz payload containing RL state and network state. | **REAL**. (Though payload contains mocked secondary junctions). |
| `POST /api/inject` | Frontend (`ScenarioStudio`) | Artificially triggers `anomaly_severity` spike to 0.85 in the backend runtime. | **DEMO API**. Created specifically to avoid live VideoMAE processing. |
| `GET /api/emergency/corridor` | Nobody | Phase A A* pathfinding. | **ORPHANED**. |
| `GET /api/esg/carbon` | Nobody | Phase A carbon calculation. | **ORPHANED**. |

#### Execution Loop (`hybrid_runtime.py`)
This is the only truly functional, continuous loop in the system.
1. Calls `TrafficEnvironment.step()`.
2. Extracts a 28D state vector.
3. Passes vector to `PPO.predict()`.
4. Executes the chosen action.
5. Emits state via the WebSocket queue.

#### The `demo_data.py` Mocker
Because simulating 16 intersections required too much CPU or was too complex for the hackathon deadline, `demo_data.py` was introduced. Every tick, it loops over `["J1", "J2", ..., "J16"]`. If the ID is not "J5", it populates wait times and queues using a `math.sin` wave + noise function. 

### Conclusion
The backend is a thin execution wrapper around the `TrafficEnvironment` and PPO agent. The vast majority of its REST endpoints (documented in Phase A) are now totally unused "Phantom APIs", while the primary communication lane is the WebSocket.
