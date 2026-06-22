# TARGET ARCHITECTURE REPORT: REPO B
## Identity: Traffic Incident Intelligence System (TIIS)

This document formalizes the exact target architecture and repository boundary for Repo B based on the "Final Vision" strategy. It serves as the definitive blueprint before any repo-splitting or file deletion occurs.

---

### 1. Intended Product Vision
Repo B is an **Urban Incident Intelligence Platform**. 
It is a video-first platform that uses state-of-the-art transformer-based Computer Vision (VideoMAE) to detect and score traffic anomalies, and directly feeds those real-time severity metrics into a Reinforcement Learning (PPO) agent to dynamically recover traffic flow. The entire process is visually tracked via a Command Center Digital Twin.

*Unlike NEXUS-ATMS (Repo A), it does not manage general smart-city operations like carbon tracking or pedestrian safety. It exists purely to detect and mitigate anomalous traffic incidents.*

### 2. Final Runtime Pipeline
The required execution chain for 100% technical reality:
1. **Video Feed** (Upload or Webcam stream)
2. **Frame Buffer** (Batching frames for inference)
3. **VideoMAE Backbone** (Feature extraction)
4. **768-D Embedding** (Latent representation)
5. **MULDE** (Multi-scale density estimation)
6. **Anomaly Event** (Threshold-based trigger)
7. **Hybrid State Builder** (CV state + Traffic state fusion)
8. **RL Observation Mapper** (Converting to 28D Gym space)
9. **PPO Policy** (StableBaselines3 Phase selection)
10. **Traffic Simulator** (SUMO/Queue mathematical execution)
11. **Digital Twin** (WebSocket driven visual rendering)

### 3. Mandatory Components
These files form the backbone of Repo B and MUST be preserved and integrated:
- `argus_stream_extracted/.../videomae.py`
- `argus_stream_extracted/.../mulde.py`
- `argus_stream_extracted/.../stream_a.py`
- `backend/runtime/hybrid_runtime.py`
- `backend/api/websockets.py`
- `backend/services/video_service.py`
- `control/traffic_env.py` (Gymnasium Environment)
- `frontend/src/` (The Next.js Application)
- `models/anomaly_v4/best_model.zip` (PPO Checkpoint)

### 4. Optional Components
These files improve the presentation but are not strictly required for the core AI loop:
- `backend/demo_data.py` (For rendering the 15 non-RL junctions in the `NetworkStatusGrid`)
- `scripts/capture_dashboard_screenshots.py`

### 5. Shared Components With NEXUS
These files must exist in both repositories:
- `control/traffic_env.py`
- `backend/core/logging.py` & `backend/core/config.py`
- Base RL agent wrappers (e.g., StableBaselines integration logic).

### 6. Components That Must Stay In NEXUS (Do Not Move to Repo B)
Repo B must be purged of these Smart City modules to maintain architectural clarity:
- `modules/carbon/engine.py` (Carbon Engine)
- `modules/emergency/corridor.py` (A* Emergency Corridors)
- `modules/pedestrian_safety/safety.py` (Pedestrian AI)
- `modules/cybersecurity/signal_security.py` (Command Validation)
- `modules/road_maintenance/maintenance.py` (Pothole Detection)
- `modules/voice_broadcast/broadcast.py` (Public Address)
- `ai/prediction/lstm_predictor.py` (Legacy Forecasting)
- `ai/rl/d3qn.py` (Legacy Agent)

### 7. Components That Must Move To Repo B (Do Not Keep in NEXUS)
- `argus_stream_extracted/` (The entire VideoMAE/MULDE pipeline)
- `frontend/` (The React/Tailwind command center UI)
- `backend/api/websockets.py` (The 5Hz data streamer)

### 8. Components That Must Exist But Are Currently Disconnected
These files exist in the Repo B branch but currently have zero live execution logic mapping them to the backend:
- `argus_stream_extracted/.../videomae.py` (Currently orphaned)
- `argus_stream_extracted/.../mulde.py` (Currently orphaned)
- `argus_stream_extracted/.../stream_a.py` (Currently orphaned)
- `backend/services/video_service.py` (Currently receives no byte streams)

### 9. Components That Can Be Deleted Entirely
Dead code that serves neither NEXUS nor TIIS:
- Legacy evaluation scripts: `generate_dti_final_report.py`, `generate_results_pdf.py`
- Legacy vision pipeline: `ai/vision/road_camera_renderer.py`, `ai/vision/traffic_renderer.py`
- Legacy UI attempts: `frontend_old/`

### 10. Gap To 100% Technical Reality
To achieve the "Final Vision" (Option 3), the following engineering work must be completed on Repo B after the split:
1. **Bridge CV Input**: Update `AIVisionPanel.tsx` to actually POST video blobs/frames to `backend/api/analytics.py`.
2. **Bridge CV Processing**: Update `backend/services/video_service.py` to route received frames through `videomae.py` and `mulde.py` to generate a live, mathematically real `severity_score`.
3. **Bridge Hybrid Runtime**: Remove the `/api/inject` mock trigger and instead have `hybrid_runtime.py` listen to the live output of `mulde.py`.
4. **Bridge Digital Twin**: Update `CanvasCityTwin.tsx` to stop using a random `requestAnimationFrame` loop, and instead read vehicle queue lengths from the live `nexusState.rl.queue` WebSocket payload to spawn corresponding canvas entities.
