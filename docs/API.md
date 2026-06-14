# NEXUS-ATMS API Documentation

This document outlines the internal and external endpoints provided by the NEXUS-ATMS FastAPI backend.

## Health & System
* `GET /api/status` - Returns current system overview including mode and metrics.
* `GET /health`, `GET /api/health` - Basic health check (`{"status": "ok"}`).
* `GET /ping` - Application heartbeat.

## Traffic & Intersections
* `GET /api/intersections` - Fetch live telemetry for all connected junctions.
* `GET /api/junctions/{id}/state` - Comprehensive JSON state of a specific junction.
* `GET /api/snapshot` - Latest global telemetry snapshot.
* `GET /api/history` - Historical throughput and latency metrics over the last 1-6 hours.
* `POST /api/junctions/select` - Switch dashboard active focus to a new junction.
* `POST /api/mode/set` - Transition system mode (AI / Manual / Emergency).

## Video & Cameras
* `GET /api/live/camera/stream` - Active WebRTC/MJPEG video feed.
* `GET /api/live/camera/{id}/{direction}/snapshot` - Fetch JPEG frame for a specific junction and direction.
* `POST /api/live/upload_video` - Upload external video for processing.
* `DELETE /api/live/clear_uploaded_video` - Remove current uploaded video.

## Signals & Manual Override
* `POST /api/signal/override` - Force specific traffic light phase (requires `X-API-Key` if hardened).
* `POST /api/nl/command` - Natural Language command processor for ChatGPT-like system queries.

## Emergency Response
* `POST /api/emergency/activate` - Register priority corridor for an emergency vehicle.
* `GET /api/emergency/active` - List all currently active priority corridors.

## Analytics & ESG
* `GET /api/carbon/today` - Today's total $CO_2$ emissions saved compared to baseline.
* `GET /api/carbon/certificate` - PDF generation of current carbon offsets.
* `GET /api/pedestrian/analyze` - Risk assessment for vulnerable road users (VRUs).

## Security & Maintenance
* `GET /api/maintenance/orders` - Road defect locations and work orders.
* `GET /api/security/events` - Cybersecurity threat logs (e.g. signal manipulation).
* `POST /api/security/simulate` - Inject simulated attack for demo purposes.

## Explainable AI (XAI)
* `GET /api/ai/status` - Health of RL/LSTM models.
* `GET /api/ai/lstm/results` - Fetch sequence forecasting values.
* `GET /api/ai/anomaly/results` - Fetch ensemble anomaly detector confidences.
* `GET /api/ai/explain_decision` - SHAP/Saliency map logic for recent RL phase changes.

## WebSockets
* `WS /ws/live` - Main unified ~1Hz telemetry broadcast socket.
* `WS /ws` - Legacy backward-compatible broadcast stream.
