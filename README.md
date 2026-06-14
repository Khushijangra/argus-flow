# NEXUS-ATMS: AI-Powered Adaptive Traffic Management System

> **Transforming urban congestion into data-driven optimization using Deep Reinforcement Learning, LSTM Forecasting, and Computer Vision.**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch&logoColor=white)](#)
[![SUMO](https://img.shields.io/badge/Eclipse_SUMO-Traffic_Simulation-blue)](#)
[![Pytest](https://img.shields.io/badge/pytest-passed-brightgreen.svg)](#)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-Active-success)](#)

---

## 🚦 Problem Statement

Urban traffic congestion is a **$1.7 trillion annual problem**. Traditional fixed-time traffic signals are fundamentally reactive and cannot adapt to dynamic demand spikes, accidents, or complex multi-modal priorities (e.g., emergency vehicles).

**NEXUS-ATMS** addresses this by replacing siloed, fixed-time signals with an end-to-end AI optimization pipeline that adapts to real-time traffic flow.

---

## 🏗️ System Overview

NEXUS-ATMS is a production-ready, modular platform that unifies sensing, prediction, anomaly detection, and adaptive control into a single architecture. 

- **Data Ingestion**: Integrates camera feeds (YOLOv8) and IoT sensor telemetry.
- **AI Engine**: Deep Reinforcement Learning (D3QN) evaluates the traffic state to orchestrate optimal signal phases.
- **Backend Service**: A robust FastAPI layer managing state, WebSocket telemetry streaming, and REST API access.
- **Evaluation Environment**: Native integration with the Eclipse SUMO microscopic traffic simulator for rigorous agent benchmarking.

---

## 🎯 Key Features

- **Traffic Optimization**: Multi-agent D3QN dynamically adjusts signal timings to minimize global queue lengths.
- **Emergency Prioritization**: Autonomous clearing of traffic corridors for ambulances and fire trucks.
- **Traffic Prediction**: LSTM-based sequence models forecast congestion levels 5–30 minutes into the future.
- **Anomaly Detection**: An ensemble machine learning detector (F1=0.913) flags irregular traffic patterns and potential accidents.
- **Carbon Analytics**: Calculates precise CO₂ emission reductions resulting from decreased idling times.
- **Explainable AI (XAI)**: Saliency maps and SHAP values explain *why* the D3QN agent selected a specific signal phase.

---

## 📊 Verified Results

The system has been rigorously evaluated in SUMO simulation environments using standardized multi-seed testing.

| Metric | Baseline (Fixed Time) | NEXUS-ATMS (D3QN) |
|---------|-----------|------------|
| **Average Waiting Time** | 571.1 s | **10.2 s** |
| **Improvement** | - | **98.2% Reduction** |
| **Multi-seed Stability** | - | 9.96 ± 0.24 s |
| **Anomaly Detection F1** | - | 0.913 |
| **Anomaly Detection Recall** | - | 1.000 |

*(Note: Results are verifiable via the included `scripts/evaluate_multiseed_gate.py` evaluation suite).*

---

## 🗺️ Architecture Diagram

![System Architecture](docs/images/architecture.png)

![Live Operator Dashboard](docs/images/dashboard.png)

---

## ⚙️ Technology Stack

- **Backend**: Python 3.13+, FastAPI, Uvicorn, WebSockets
- **Machine Learning**: PyTorch, Stable-Baselines3, Scikit-learn
- **Computer Vision**: OpenCV, YOLOv8 (Ultralytics)
- **Simulation**: Eclipse SUMO (Simulation of Urban MObility)
- **Frontend**: HTML5, Vanilla JavaScript, Chart.js
- **DevOps/Testing**: Pytest, Docker, GitHub Actions CI/CD

---

## 🚀 Quick Start

### 1. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/Khushijangra/NEXUS-ATMS.git
cd NEXUS-ATMS

python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows

pip install -r requirements-dev.txt
```

### 2. SUMO Setup
Ensure Eclipse SUMO is installed on your system and the `SUMO_HOME` environment variable is configured.

### 3. Backend Startup
Launch the FastAPI backend server:
```bash
python backend/main.py
```
*API Docs available at: http://localhost:8080/docs*

### 4. Demo Execution
Run the full visual simulation dashboard:
```bash
python run_demo.py --episodes 1
```

### 5. Testing
Execute the recruiter-visible verification suite:
```bash
python -m pytest tests/ -v
```

---

## 📁 Repository Structure

```text
NEXUS-ATMS/
├── backend/                  # FastAPI Application Entrypoint
│   ├── api/                  # REST Endpoint Routers
│   ├── services/             # Business Logic & LiveRuntime Orchestration
│   ├── core/                 # Configurations and Utilities
│   ├── dependencies.py       # Global State Injection
│   └── main.py               # Uvicorn App Setup
├── ai/                       # AI/ML Core Logic
│   ├── rl/                   # D3QN Agent Implementations
│   ├── prediction/           # LSTM Forecasters
│   ├── anomaly/              # Ensemble ML Detectors
│   └── explainability/       # SHAP / XAI Parsers
├── tests/                    # Pytest Suite (Mocked Environments)
├── scripts/                  # Evaluation & Benchmark Utilities
├── configs/                  # Traffic Network Definitions
└── docs/                     # Architecture & API Documentation
```

---

## 🔮 Future Work

- **Graph RL**: Transitioning from independent agents to Graph Neural Network (GNN) based multi-agent coordination.
- **Digital Twins**: Native integration with CARLA for photo-realistic sensor simulation.
- **Federated Learning**: Decentralized training across multiple smart-city nodes without compromising data privacy.

---

## 📚 Citation

If you use this repository for academic research or portfolio reference, please link back to this repository:
```text
https://github.com/Khushijangra/NEXUS-ATMS
```
