# ArgusFlow

### Vision-Guided Traffic Incident Intelligence & Recovery Platform

## 1. Problem
Urban traffic systems rely on basic mathematical metrics like queue lengths and static timers, making them entirely blind to real-world incidents. When accidents, road maintenance, or severe anomalies occur, traditional networks fail to react, leading to cascading gridlocks. They lack the *visual perception* required to understand context and severity.

## 2. Solution
**ArgusFlow** introduces visual intelligence to traffic optimization. Built on a powerful reinforcement learning core (NEXUS), it acts as a Vision-Guided Traffic Incident Intelligence & Recovery Platform. By identifying anomalous traffic events from camera streams and computing severity scores, ArgusFlow dynamically instructs a Deep Reinforcement Learning engine to autonomously adapt signal phases, clear blockages, and recover traffic flow.

## 3. Architecture Diagram
![ArgusFlow Architecture](docs/media/media__1781973451680.png)

## 4. Demo Screenshot
*(Insert YouTube Link or High-Res Screenshot here)*

## 5. Runtime Pipeline
ArgusFlow executes a hybrid pipeline combining Computer Vision (Argus Vision Stack) with Reinforcement Learning (NEXUS Engine):

```mermaid
graph TD
    VF[Live Video Feed / Camera Edge] --> SI[Command Center Gateway]
    SI --> HR[ArgusFlow Hybrid Runtime]
    HR --> PPO[PPO Autonomous Recovery Engine]
    PPO --> TE[Traffic Micro-Simulator]
    TE --> DT[Next.js Digital Twin]
```
*(Note: Full technical research implementation for direct VideoMAE and MULDE integration is archived within `archive/stream_a_research`)*

## 6. Tech Stack
- **Frontend**: Next.js, React, TailwindCSS, Recharts
- **Backend**: FastAPI, WebSockets, Python
- **Intelligence**: PyTorch (PPO, D3QN), Scikit-Learn
- **Simulation**: Eclipse SUMO (Simulation of Urban MObility)
- **Deployment**: Docker, Docker Compose

## 7. Run Locally
ArgusFlow provides a comprehensive Command Center built with Next.js and FastAPI.

### 1. Start the Intelligent Backend
The backend initializes the Hybrid Runtime, anomaly detectors, and PPO engines.
```bash
python backend/main.py
```

### 2. Start the Command Center
Launch the Next.js Digital Twin and Scenario Studio.
```bash
cd frontend
npm run dev
```
Navigate to `http://localhost:3000` to interact with the Digital Twin and monitor active traffic states.

## 8. Future Work
- **Direct Edge Deployment**: Move the MULDE anomaly scorer directly to edge camera nodes to reduce bandwidth overhead.
- **V2X Integration**: Expand the emergency corridor engine to communicate directly with connected emergency vehicles.
- **Multi-Modal Vision**: Combine infrared and RGB streams for robust nighttime anomaly detection.
