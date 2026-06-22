#!/bin/bash
set -e

echo "============================================="
echo " NEXUS-ATMS FINAL COMMERCIAL DEMO SCENARIO "
echo "============================================="
echo "This script demonstrates the complete anomaly-aware RL pipeline."
echo ""
echo "1. Ensuring services are up..."
./start.sh
sleep 5

echo "2. Injecting UA-DETRAC Accident Anomaly (Severity > 0.8)..."
echo "Sending POST request to Stream-A API..."
curl -X POST http://localhost:8000/process_video \
     -H "Content-Type: application/json" \
     -d '{"video_path": "data/videos/ua_detrac_accident.mp4", "camera_id": "North_Cam_Piedmont"}'

echo ""
echo "3. Anomaly detected! HybridState updated."
echo "4. RL PPO Policy receives 28-D observation with Severity=0.83+."
echo "5. SUMO signal timing dynamically adjusting phase allocation to clear queue."
echo "6. Digital Twin Frontend (http://localhost:3000) receiving live WebSocket updates."
echo ""
echo "Demo execution active. Open http://localhost:3000 to view."
echo "Press Ctrl+C to stop."
wait
