# EVOLUTION FORENSICS AUDIT
## Document 5: INTEGRATION_MATRIX.md

### Feature Integration Matrix

This matrix traces the top-level claims of NEXUS-ATMS to determine exactly how "real" they are in the current executable state.

| Feature Claim | Entry Point | Execution Path | Output Status | Truth |
| :--- | :--- | :--- | :--- | :--- |
| **Video Upload** | `AIVisionPanel.tsx` | React state `videoUrl` -> `<video>` element. | Visually displayed. **NO** API call made. | **VISUALLY CONNECTED ONLY**. The video does not reach the backend. |
| **Anomaly Detection** | `/api/inject` | Triggered via `setTimeout` in UI. Calls `hybrid_runtime.inject_anomaly`. | Modifies `_anomaly_severity` in Gym env. | **PARTIALLY CONNECTED**. The math works, but it's triggered artificially, not from live video. |
| **RL Inference** | `hybrid_runtime.py` | `PPO.predict()` -> `env.step()` | Changes traffic phase, reduces wait times mathematically. | **ACTUALLY CONNECTED**. This is the strongest piece of the repo. |
| **Digital Twin (Canvas)** | `CanvasCityTwin.tsx` | React `requestAnimationFrame` drawing boxes randomly looping. | Visually stunning UI. | **NOT CONNECTED**. The cars on screen have 0 relation to the RL agent or backend data. |
| **WebSocket Stream** | `main.py` -> `ScenarioStudio.tsx` | `useNexusStream` React hook reads from `ws://localhost:8001/ws`. | `nexusState` object in UI. | **ACTUALLY CONNECTED**. Telemetry displayed in the `AIDecisionEngine` is real. |
| **Multi-Junction Grid** | `demo_data.py` | Generates 15 random payloads to append to J5's real payload. | 16 junctions visible in the `NetworkStatusGrid`. | **MOCKED**. Only J5 is real. |
| **Metrics Dashboard** | `ScenarioStudio.tsx` | Hardcoded percentages (or static evaluations) rendered in a grid. | Visual display. | **VISUALLY CONNECTED ONLY**. |
| **Incident Timeline** | `ScenarioStudio.tsx` | Arrays of string messages updated via `setTimeout`. | Visual display. | **VISUALLY CONNECTED ONLY**. |
| **Emergency Corridors** | `modules/corridor.py` | None. | None. | **NOT CONNECTED**. |

### Summary Conclusion
NEXUS-ATMS Phase B is a brilliantly staged theater production. The core engine (RL PPO inside a Gym environment) is highly legitimate and mathematically sound. However, every visual layer surrounding it (Canvas Twin, Video Upload, Timeline, 16-Junction Grid) is a hardcoded or simulated façade designed to secure a hackathon win.
