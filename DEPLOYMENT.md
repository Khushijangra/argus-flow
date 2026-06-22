# NEXUS-ATMS Deployment Guide

This document outlines how to deploy the NEXUS-ATMS suite for commercial demonstration. The deployment process is fully containerized via Docker and Docker Compose.

## Prerequisites
- Docker (v24+)
- Docker Compose (v2+)
- NVIDIA Container Toolkit (Optional but highly recommended for `stream-a` GPU passthrough)
- OpenStreetMap topology XML and SUMO `randomTrips` routing data in `data/networks/`
- Valid trained checkpoint in `data/models/anomaly_v4/best_model.zip`

## Service Startup Order

The `docker-compose.yml` ensures the exact sequence required for system stability:
1. **`stream-a`**: Boots the FastAPI inference server. Loads the VideoMAE + MULDE models into GPU memory. 
2. **`runtime`**: Boots the Orchestrator, Python PPO runtime, and headless SUMO. Waits for `stream-a` to report healthy. 
3. **`frontend`**: Boots the Next.js React Dashboard, binding WebSockets to the `runtime`.

## Clean-Machine Test Procedure

To verify a truly portable, environment-agnostic deployment on a fresh server, run the following:

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd urban-congestion
   ```

2. Execute the cluster initialization:
   ```bash
   docker compose up -d --build
   ```

3. Verify service health without manual path edits:
   ```bash
   docker compose logs -f
   ```
   **Expected output:**
   - `nexus-stream-a`: "Uvicorn running on http://0.0.0.0:8000"
   - `nexus-runtime`: "SUMO TraCI connected. WebSocket server listening on 8001"
   - `nexus-frontend`: Nginx started successfully.

## Hardware Scaling
- **Stream-A Module**: Bind to instances with NVIDIA T4/A10G or better for realtime 30FPS inference.
- **Runtime Module**: Highly dependent on CPU single-core performance due to SUMO's traci limits. Bound to instances with high base clocks.
