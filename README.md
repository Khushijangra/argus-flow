# NEXUS-ATMS: AI-Powered Adaptive Traffic Signal Control

> **Transform urban congestion into data-driven optimization using Deep Reinforcement Learning, Computer Vision, and predictive AI.**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/fastapi-0.104+-green.svg)](https://fastapi.tiangolo.com/)

---

## 🚦 Problem Statement

**Urban traffic congestion is a $1.7 trillion annual problem.** Traditional fixed-time traffic signals are fundamentally reactive—they cannot adapt to:

- **Dynamic demand spikes** (events, accidents, rush hours)
- **Multi-modal priorities** (emergency vehicles, transit buses, cyclists)
- **Incident-induced instability** (accidents, road closures, weather)
- **Network-wide optimization** (coordinated multi-junction control)

Current solutions operate in silos: vehicle detection ≠ signal control ≠ incident response.

---

## 🎯 Solution: End-to-End AI Traffic Optimization

**NEXUS-ATMS** is a production-ready platform that unifies **sensing, prediction, anomaly detection, and adaptive control** into a single modular stack.

### Core Philosophy
From raw sensory input → AI inference → real-time backend → operator dashboard

```
🎥 Cameras/Sensors → 📊 Data Fusion → 🧠 AI Engines → ⚙️ Backend API → 📱 Dashboard
```

---

## 🏗️ Architecture Overview

### **Layer 1: Ingestion & Feature Engineering**
- **Vision Pipeline**: Vehicle detection, tracking, counting, incident detection
- **IoT Abstraction**: Sensor fusion, MQTT integration, synthetic stream simulation
- **Data Fusion**: Real-time state assembly per traffic junction

### **Layer 2: AI Intelligence Engine**
- **RL Signal Optimization**: DQN, PPO, Graph-Aware D3QN agents
- **Forecasting**: LSTM-based traffic flow prediction (5-30 min horizon)
- **Anomaly Detection**: Dual-mode (rule-based + ML) incident flagging
- **Explainability**: Counterfactual analysis, decision attribution

### **Layer 3: Control & Safety Logic**
- **Traffic Signal Orchestration**: Multi-junction coordination
- **Emergency Corridor**: Autonomous priority lanes for ambulances/fire trucks
- **Security Validation**: Cyberattack detection on signal commands
- **Maintenance Integration**: Road work advisory system

### **Layer 4: Backend Service Layer**
- **FastAPI Runtime**: 25+ REST endpoints + WebSocket live streaming
- **Demo Mode**: Standalone operation with synthetic data
- **Real Data Mode**: Live SUMO simulator or camera integration
- **Metrics Store**: Latency, carbon savings, congestion index tracking

### **Layer 5: Operator Dashboard**
- Real-time traffic visualization
- AI control metrics and performance
- Manual override capabilities
- Historical reports and analytics

---

## 📁 Project Structure (Clean Modular Design)

```
NEXUS-ATMS/
├── ai/                          ← AI Engine (single source of truth)
│   ├── rl/                      DQN, PPO, D3QN agents + graph coordination
│   ├── envs/                    SUMO environment interfaces
│   ├── vision/                  Detection, tracking, counting, rendering
│   ├── prediction/              LSTM forecasting models
│   ├── anomaly/                 Rule-based + ML detection
│   ├── explainability/          XAI analysis pipeline
│   └── utils/                   Metrics, logging, visualization
│
├── backend/                     ← FastAPI Application (single entry point)
│   ├── main.py                  App runtime with 25+ endpoints
│   ├── api/                     Endpoint handlers
│   ├── services/                Business logic layer
│   ├── core/                    Shared utilities
│   └── demo_data.py             Synthetic data generator
│
├── frontend/                    ← Dashboard UI
│   └── index.html               Operator interface
│
├── control/                     ← Traffic Signal Control
│   └── rl_controller.py         Signal optimization orchestrator
│
├── iot/                         ← Sensor & Data Integration
│   ├── mqtt_client.py           IoT messaging
│   ├── sensor_simulator.py      Test data generator
│   └── data_fusion.py           State assembly
│
├── scripts/                     ← Utilities
│   ├── train.py                 Training loop
│   ├── evaluate.py              Agent evaluation
│   └── benchmark_d3qn_suite.py  Comparative benchmarks
│
├── configs/                     ← Scenario Configuration
│   ├── default.yaml             Base config
│   ├── rush_hour.yaml           Peak traffic scenario
│   └── night_traffic.yaml       Low-volume scenario
│
└── docs/                        ← Architecture & Implementation Docs
```

---

## ⚙️ Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML5 + WebSocket | Real-time dashboard |
| **Backend API** | FastAPI + Uvicorn | REST + streaming endpoints |
| **AI/ML** | PyTorch, Stable-Baselines3 | RL agents, neural networks |
| **Simulation** | SUMO (CARLA support planned) | Realistic traffic environment |
| **Forecasting** | TensorFlow/Keras | LSTM predictor |
| **Anomaly Detection** | Scikit-learn + custom ML | Statistical + model-based |
| **Computer Vision** | OpenCV + YOLO | Vehicle detection/tracking |
| **Data/Logging** | NumPy, Pandas, TensorBoard | Analytics & visualization |
| **DevOps** | Docker, Render.yaml | Deployment ready |
| **CI/CD** | GitHub Actions | Automated testing |

---

## 🚀 Quick Start

### Prerequisites
```bash
# Python 3.13+ required
python --version
```

### 1️⃣ Environment Setup
```bash
# Clone and navigate
git clone https://github.com/Khushijangra/NEXUS-ATMS.git
cd NEXUS-ATMS

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2️⃣ Run Backend (Fast)
```bash
# Starts demo mode with synthetic data (~30 seconds)
python backend/main.py

# API available at: http://localhost:8000
# Swagger docs: http://localhost:8000/docs
# WebSocket stream: ws://localhost:8000/ws/live
```

### 3️⃣ Full Demo
```bash
# Runs end-to-end demo with visualization
python run_demo.py
```

### 4️⃣ Train a Custom Agent
```bash
# Train D3QN agent for 50k steps
python train.py --agent d3qn --timesteps 50000 --config configs/default.yaml

# Evaluate trained model
python evaluate.py --agent d3qn --model models/<run>/best/best_model.pt

# Benchmark multiple agents
python scripts/benchmark_d3qn_suite.py --config configs/default.yaml --timesteps 50000
```

### 5️⃣ Optional: GPU Acceleration
```bash
# Verify GPU availability
python scripts/check_gpu.py

# Training will auto-detect CUDA if available
```

---

## 📊 API Overview

### Key Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | System health + component status |
| `/api/snapshot` | GET | Current traffic state at all junctions |
| `/api/signal/override` | POST | Manual traffic light control |
| `/api/emergency/activate` | POST | Trigger emergency corridor |
| `/api/carbon/today` | GET | CO₂ emissions savings today |
| `/api/counterfactual` | GET | AI vs. baseline comparison |
| `/ws/live` | WebSocket | Real-time metric streaming (~1 Hz) |

📖 **Full API Docs**: `http://localhost:8000/docs` (interactive Swagger UI)

---

## 🎯 Key Features

### ✅ Adaptive Signal Control
- **Multi-agent RL**: DQN, PPO, and custom D3QN (Dueling Double Deep Q-Network)
- **Graph-aware coordination**: Optimize multi-junction flow
- **Real-time adaptation**: Respond to demand within seconds

### ✅ Predictive Intelligence
- **LSTM forecasting**: 5–30 minute traffic flow predictions
- **Anomaly detection**: Rule-based + ML-based incident flagging
- **Incident response**: Auto-activate emergency lanes for accidents

### ✅ Vision Pipeline
- **Vehicle detection**: YoloV8-based with fallback modes
- **Tracking**: Multi-object tracking across frames
- **Zone counting**: Real-time vehicle volume per region

### ✅ Safety & Control
- **Emergency corridors**: Automatic priority lanes for ambulances
- **Security validation**: Detect and reject malicious signal commands
- **Manual override**: Operator can always take control

### ✅ Transparency & Explainability
- **Counterfactual analysis**: Why did the AI choose this signal timing?
- **Decision attribution**: Which factors influenced the control decision?
- **Carbon savings**: Track environmental impact of optimization

### ✅ Production Ready
- **Deployment config**: Render.yaml + Docker ready
- **Modular design**: Swap components without breaking others
- **Robust error handling**: Graceful degradation if modules fail

---

## 📈 System Outputs & Metrics

### What the System Produces
- **Traffic metrics**: Queue length, avg speed, carbon emissions per cycle
- **Control decisions**: Next signal phase, override requests, priority levels
- **Predictions**: Forecasted congestion 5–30 minutes ahead
- **Anomalies**: Detected incidents, security threats, maintenance needs
- **Reports**: Daily performance, weekly benchmarks, agent comparisons

### Typical Improvements (Simulated)
- **Queue reduction**: 15–25% shorter average wait times
- **Throughput**: 10–18% more vehicles processed per hour
- **Emissions**: 8–12% CO₂ reduction from fewer idling cycles
- **Emergency response**: <60 second corridor activation

---

## 🔍 Design Decisions & Tradeoffs

### Why Modular?
- **Extensibility**: Add new RL agents, vision models, or safety rules independently
- **Testability**: Each component can be validated standalone
- **Maintainability**: Clear responsibilities; easy to debug and improve

### Why SUMO Simulation?
- **Realism**: Microscopic traffic dynamics are accurate
- **Safety**: Test dangerous scenarios without real damage
- **Reproducibility**: Fixed random seeds for consistent experiments

### Why RL (Not Rule-Based)?
- **Adaptability**: Learns optimal behavior from environment feedback
- **Scalability**: Same algorithm works for 1 junction or 100 junctions
- **Multi-objective**: Naturally balances throughput, emissions, fairness

### Why LSTM for Prediction?
- **Sequential dependency**: Traffic flow has temporal patterns
- **Efficiency**: Cheaper than online RL for short-horizon forecasting
- **Ensemble capability**: Can combine predictions from multiple models

---

## ⚠️ Current Limitations & Future Work

### Known Limitations
1. **Simulation gap**: Real-world deployment requires computer vision calibration
2. **Cold start**: RL agents require 10k–50k training steps before competence
3. **Multi-modal optimization**: Currently optimizes for flow; fairness is secondary
4. **Geospatial scale**: Handles single intersections; multi-city coordination is future work

### Planned Improvements (Roadmap)
- [ ] Integration with real traffic cameras (OpenCV + commercial APIs)
- [ ] Hierarchical control: single intersection → city district → metro area
- [ ] Uncertainty quantification: Confidence bands on predictions
- [ ] Federated learning: Train models across multiple cities privately
- [ ] Natural language interface: Operators issue voice commands

---

## 🧪 Testing & Validation

### Run Tests
```bash
# Validate all imports
python -m pytest tests/ -v

# Check code coverage
python -m pytest --cov=ai --cov=backend tests/
```

### Benchmarking
```bash
# Compare DQN vs PPO vs D3QN
python scripts/benchmark_d3qn_suite.py --config configs/default.yaml

# Multi-seed validation (statistical significance)
python scripts/evaluate_multiseed_gate.py --seeds 5 --timesteps 50000
```

---

## 📚 Documentation

- [Architecture Deep Dive](docs/architecture.md) — System design, dataflow, module interactions
- [Implementation Guide](docs/implementation_checklist.md) — How to add new features
- [Benchmarks & Results](docs/benchmarks.md) — Performance metrics and comparisons
- [Deployment Guide](docs/) — Production deployment steps

---

## 🤝 Contributing

We welcome contributions! Please:
1. Read [CONTRIBUTING.md](CONTRIBUTING.md)
2. Fork the repository
3. Create a feature branch (`git checkout -b feature/your-feature`)
4. Commit changes with clear messages
5. Push to branch and open a pull request

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

---

## 📄 License

This project is released under the **MIT License** — see [LICENSE](LICENSE) for details.

**Note**: This repository is intended for academic research, engineering portfolio demonstration, and educational use. Commercial deployment requires additional safety validation.

---

## 👤 Author & Contact

**Khushijangra** — AI Engineer & Traffic Systems Designer  
📧 Email: [in GITHUB profile]  
📍 GitHub: [@Khushijangra](https://github.com/Khushijangra)  

---

## 🌟 Acknowledgments

- **SUMO (Eclipse)**: Open-source microscopic traffic simulator
- **Stable-Baselines3**: Robust RL algorithm implementations
- **FastAPI**: Modern, fast API framework
- **OpenCV & YOLO**: Computer vision capabilities

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Khushijangra/NEXUS-ATMS/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Khushijangra/NEXUS-ATMS/discussions)
- **Documentation**: [Full docs](docs/)

---

**Last Updated**: April 2026 | **Status**: Production-Ready ✅
