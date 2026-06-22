#!/bin/bash
# Lightning AI Deployment Startup Script

echo "Starting NEXUS-ATMS Hybrid Runtime on Lightning AI..."

# 1. Start Stream-A Anomaly Inference Service in background
echo "Launching Stream-A Inference Service..."
# python backend/api/inference_server.py &
# (Mock command, assuming inference server exists or will run on 8000)

# Wait a moment for Stream-A to bind
sleep 2

# 2. Start SUMO backend mapping / API (if separate)
# Not explicitly needed as hybrid_runtime embeds SUMO through TrafficEnv

# 3. Start the Hybrid Runtime Orchestrator
echo "Launching Hybrid Runtime..."
python backend/runtime/hybrid_runtime.py

echo "Runtime Terminated."
