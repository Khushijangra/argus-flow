# EVOLUTION FORENSICS AUDIT
## Document 10: REPO_SPLIT_PLAN.md

### Repository Split Analysis

The user intends to split the monolithic repository into two distinct codebases:
**Repo A**: Original NEXUS-ATMS (Pure RL Smart City Engine)
**Repo B**: NEXUS-ATMS Phase B (Hackathon Cinematic UI + Anomaly Engine)

#### Files belonging ONLY to Repo A
*   `modules/corridor.py`
*   `modules/engine.py`
*   `modules/safety.py`
*   `modules/signal_security.py`
*   `modules/maintenance.py`
*   `modules/parser.py`
*   `modules/broadcast.py`
*   `scripts/test4_24h_stability.py`
*   `frontend_old/` (Legacy HTML views)

#### Files belonging ONLY to Repo B
*   `frontend/` (The entire Next.js Application)
*   `argus_stream_extracted/` (The Stream A VideoMAE models)
*   `backend/demo_data.py` (The 16-junction mocker)
*   `scripts/demo_incident_scenario.py`

#### Files Shared By Both (Need Duplication)
*   `control/traffic_env.py` (The core Gym environment)
*   `backend/main.py` (Though Repo A should strip WebSockets and keep pure REST)
*   `models/anomaly_v4/best_model.zip`
*   `requirements.txt` (Though Repo B needs heavier Next.js and VideoMAE dependencies)

#### Files Needing Refactor for Split
*   `backend/runtime/hybrid_runtime.py`: Repo A does not need this orchestrator since it doesn't stream via WebSocket. Repo A can rely on simpler test loops.
*   `control/traffic_env.py`: Remove `_anomaly_severity` and `_anomaly_timer` from Repo A to keep it a pure RL traffic simulator without CV collision injections.
