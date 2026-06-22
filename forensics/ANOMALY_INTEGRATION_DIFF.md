# EVOLUTION FORENSICS AUDIT
## Document 2: ANOMALY_INTEGRATION_DIFF.md

### Identification of Phase B (Anomaly Integration) Changes

This document traces exactly which files were created or modified to morph NEXUS-ATMS into its current Anomaly-Aware Hackathon iteration.

| File Name | Purpose | Before | After | Reason for Change | Integration Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `frontend/` (Entire Directory) | Next.js Hackathon UI | Did not exist (or existed as raw HTML) | Full React/Tailwind application | Provide a cinematic, "Government Command Center" visual wrapper for the hackathon presentation. | **PARTIALLY INTEGRATED** (Visuals are heavily mocked; RL telemetry is live). |
| `backend/runtime/hybrid_runtime.py` | Orchestration Engine | Did not exist | Combines `TrafficEnvironment`, PPO Agent, and Stream A fetching. | Replaces modular script execution with a unified FastAPI-managed simulation loop. | **FULLY INTEGRATED** (Core backend engine). |
| `backend/demo_data.py` | Traffic Data Mocker | Did not exist | Generates mathematical traffic JSON payloads for 16 junctions. | To fake city-scale grid traffic without running 16 actual SUMO/Gym environments. | **FULLY INTEGRATED** (Drives the non-J5 junctions in UI). |
| `argus_stream_extracted/argus stream A/` | Computer Vision Models | Did not exist | Contains VideoMAE and MULDE implementation. | Introduce deep learning anomaly detection capabilities. | **NOT INTEGRATED** (Files exist, but runtime bypasses them via `/api/inject` API injection for demo stability). |
| `scripts/eval_anomaly_policy.py` | RL Verification | Legacy pure RL eval | Evaluates PPO specifically against `_anomaly_severity` metrics. | Prove that the RL model actually learned to mitigate anomalies. | **FULLY INTEGRATED** (Used offline to generate validation stats). |
| `control/traffic_env.py` | Simulation Environment | Basic queue modeling | Added `_anomaly_severity`, `_anomaly_timer`, `_anomaly_prob`. | Allow the mathematical RL environment to simulate crash events. | **FULLY INTEGRATED** (Core training env). |
| `frontend/src/components/studio/ScenarioStudio.tsx` | Demo Orchestrator | N/A | React component managing a 30-second `setTimeout` cinematic flow. | Control the visual narrative for judges without risking live backend failures. | **PARTIALLY INTEGRATED** (Triggers backend `/api/inject` but ignores backend websocket for main visualization). |
| `backend/main.py` | API Entrypoint | Simple REST | Added WebSocket manager and `HybridRuntime` initialization. | Bridge the FastAPI ecosystem to the new React Next.js UI. | **FULLY INTEGRATED**. |

### Summary
The anomaly integration caused a massive architectural shift from a *local research script* into a *web-orchestrated simulation*. The highest integration debt is `argus stream A`, which was successfully built but ultimately bypassed in the live demo loop in favor of a triggered `POST /api/inject`.
