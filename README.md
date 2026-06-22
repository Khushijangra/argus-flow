# NEXUS-ATMS
**Next-Generation Urban Congestion & Anomaly-Aware Traffic Management System**

![Status](https://img.shields.io/badge/Status-Commercial_Demo_Ready-brightgreen)
![Version](https://img.shields.io/badge/Version-1.0.0-blue)
![License](https://img.shields.io/badge/License-MIT-purple)

NEXUS-ATMS is an advanced AI-driven traffic signal controller that dynamically adapts to real-time traffic conditions and unexpected anomalies (accidents, construction, weather events). 

Unlike traditional static signal controllers or standard Reinforcement Learning agents, NEXUS-ATMS leverages a **Hybrid State Architecture** that seamlessly integrates deep visual feature extraction (VideoMAE) with traffic-simulator data (SUMO). This allows the RL agent (PPO) to make proactive phase adjustments *before* congestion cascades.

## Key Features
* **Live Anomaly Detection (Stream-A):** Processes live video feeds via VideoMAE and MULDE to generate a normalized severity score for intersection anomalies.
* **HybridState RL:** A highly optimized 28-dimensional canonical observation schema combining microscopic traffic data (queue lengths, wait times) with macroscopic event awareness.
* **Real-World OSM Scalability:** Dynamically loads and operates on OpenStreetMap (OSM) topologies rather than synthetic grid assumptions.
* **Digital Twin Frontend:** A WebSocket-powered Next.js React UI providing live observability of anomaly events, active signal phases, and wait times.
* **Fault Tolerant:** Implements a graceful fallback system to static signal logic if the anomaly engine or API times out.

## Project Maturity
* [x] Research Prototype
* [x] Commercial Demonstration Ready
* [ ] Production Traffic Authority Deployment

## Documentation Directory
- [Architecture Overview](ARCHITECTURE.md) - Deep dive into the 28D RL schema and data pipelines.
- [Deployment Guide](DEPLOYMENT.md) - Instructions for Docker clustering and bare-metal initialization.
- [API Reference](API_REFERENCE.md) - WebSocket and REST contracts.
- [Demo Guide](DEMO_GUIDE.md) - How to run the UA-DETRAC anomaly injection scenario.
