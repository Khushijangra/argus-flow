# EVOLUTION FORENSICS AUDIT
## Document 1: ORIGINAL_SYSTEM.md

### Phase A: Original NEXUS-ATMS Architecture
Based on forensics of `theory.txt`, `how was built.txt`, and legacy directory structures, the original NEXUS-ATMS (Phase A) was an ambitious, monolithic, pure Reinforcement Learning (RL) traffic signal control system.

It was designed as a "closed-loop control system" heavily focused on algorithmic correctness, multi-objective reward tuning, and practical city operations (like emergency corridors and carbon tracking) rather than high-fidelity visual presentations.

#### 1. Core Architecture (Pre-Anomaly)
The original architecture relied on a local simulation-based pipeline:
- **Sense**: YOLO (v8) for vehicle detection + DeepSORT for tracking.
- **Predict**: LSTM for near-future queue growth estimation.
- **Decide**: D3QN (Double Dueling Deep Q-Network) or PPO agent to select the next signal phase.
- **Act**: A mathematical `TrafficEnvironment` (or optionally `SUMO`) executing the signal switch.

#### 2. Key Components & Directories
The following directories constituted the original core:
- `control/`: Contained `traffic_env.py` (the mathematical D/D/1 queueing environment) and `rl_controller.py` (StableBaselines3 wrapper).
- `ai/`: Contained various models:
  - `ai/rl/d3qn_multimodal.py`: Original Deep RL logic.
  - `ai/vision/`: YOLO and DeepSORT wrappers.
  - `ai/envs/env_anomaly.py`: Legacy RL environments.
- `modules/`: Contained isolated operational scripts (Emergency Corridor, Carbon Savings, Cybersecurity).
- `frontend_old/`: A legacy frontend.
- `backend/`: The early FastAPI orchestrator (`main.py`) which primarily served REST endpoints rather than the complex hackathon WebSocket loops.

#### 3. Core Services & APIs
The Phase A backend (`main.py`) had distinct endpoints aimed at physical operations:
- `/api/health`: System health.
- `/api/junctions/{id}/state`: Raw traffic queue metrics.
- `/api/emergency/corridor`: A* graph path planning to pre-clear signals.
- `/api/esg/carbon`: Calculation of CO2 savings based on idle minutes.

#### 4. UI Components (Pre-Next.js)
The original UI was drastically simpler, likely relying on an `index.html` static serve (referenced in `how was built.txt`) or the legacy `frontend_old/` directory. It focused on raw numerical data:
- Ranked Junction Board
- Simple Flowview
- Signal Timeline

### Summary of Evolution Shift
Phase A was a rigorous data-science project validating that RL could beat fixed-time controllers. It possessed deep but disconnected technical modules (Carbon, Pedestrian Safety, Cybersecurity). 

The shift to Phase B (Anomaly Integration) abandoned many of the "smart city" modules (Carbon, Pedestrian) in favor of a highly visual, cinematic integration of `argus stream A` (VideoMAE) and a Next.js `CanvasCityTwin` dashboard built specifically to win hackathons.
