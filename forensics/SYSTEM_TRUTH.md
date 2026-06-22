# EVOLUTION FORENSICS AUDIT
## Document 12: SYSTEM_TRUTH.md

### System Truth Report

This is the definitive, brutal truth of the entire repository as it currently stands.

| Feature | Reality | Evidence | Status |
| :--- | :--- | :--- | :--- |
| **RL Traffic Controller** | PPO Model successfully trained against a queueing-theory Gymnasium environment. It dynamically shifts signal phases. | `backend/runtime/hybrid_runtime.py:276` (`action, _ = self.rl_model.predict(obs)`) | **REAL** |
| **Live Anomaly Integration** | CV models process frames and output scores. | `argus_stream_extracted/argus stream A/demo.py` | **DISCONNECTED** |
| **Demo Scenario Orchestration** | React drives the demo narrative using timeouts and sends a hardcoded JSON to `/api/inject` to trigger the backend. | `ScenarioStudio.tsx:75` | **REAL** (But artificial mechanics) |
| **Visual Traffic Twin** | Hundreds of cars looping on a `<canvas>` mathematically driven by `requestAnimationFrame`. | `CanvasCityTwin.tsx:184` | **MOCKED** |
| **City Scale Network (16 Nodes)** | 1 Node (J5) runs RL. 15 Nodes are generated using `math.sin` and `random.uniform` in a backend loop. | `backend/demo_data.py:160` | **PARTIAL / MOCKED** |
| **Live Telemetry Websocket** | Backend streams `nexusState` at 5Hz to the React frontend. | `main.py:2774` | **REAL** |
| **Carbon Savings Engine** | Converts idle wait time into CO2 and Fuel savings. | `modules/engine.py` | **ABANDONED** (Not connected to Phase B) |
| **Emergency Corridors** | A* Graph routing to pre-clear traffic lights. | `modules/corridor.py` | **ABANDONED** (Not connected to Phase B) |
| **Cybersecurity Attacks** | HMAC signature verification and anomaly logging. | `modules/signal_security.py` | **ABANDONED** (Not connected to Phase B) |

### Final Conclusion
The project evolved from a highly theoretical, multi-module "Smart City" simulation (Phase A) into a highly polished, singular-focus Hackathon Demonstration (Phase B). 

To achieve the hackathon aesthetic, massive amounts of functional logic (Carbon, Corridors) were abandoned, and heavy CV models (VideoMAE) were bypassed in favor of hardcoded API triggers to ensure presentation stability. The core RL agent remains the single point of absolute, un-mocked technical truth.
