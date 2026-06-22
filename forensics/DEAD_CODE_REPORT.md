# EVOLUTION FORENSICS AUDIT
## Document 4: DEAD_CODE_REPORT.md

### Dead Code Discovery

This report catalogs all code that is currently orphaned, unused, or abandoned in the Phase B repository. The massive pivot toward the hackathon React UI and FastAPI orchestrated environment rendered several Phase A operational modules and testing scripts obsolete.

#### 1. Orphaned Modules (Phase A Remnants)
The original system boasted specialized modules for city operations. None of these are instantiated in `backend/main.py` or `hybrid_runtime.py` during live execution.
- **`modules/corridor.py`** (Emergency corridor planning): **DEAD**
- **`modules/engine.py`** (Carbon Engine): **DEAD**
- **`modules/safety.py`** (Pedestrian safety AI): **DEAD**
- **`modules/signal_security.py`** (Cybersecurity command validation): **DEAD**
- **`modules/maintenance.py`** (Road maintenance AI): **DEAD**
- **`modules/parser.py`** (NL parser): **DEAD**
- **`modules/broadcast.py`** (Voice broadcast): **DEAD**

*Status*: **FUTURE_WORK / ABANDONED**. These files contain valid logic but have zero integration into the current frontend or runtime loop.

#### 2. Unused Frontend Files
- **`frontend_old/`**: **LEGACY**. Entirely superseded by the Next.js `frontend/` directory.

#### 3. Unused / Experimental Scripts
- **`scripts/test4_24h_stability.py`**: **DEAD**.
- **`scripts/test_osm_network.py`**: **DEAD**. The system no longer actively loads SUMO OSM networks.
- **`scripts/train.py`**: **LEGACY**. Replaced by `scripts/train_anomaly_policy.py`.
- **`scripts/debug_env_rewards.py`**: **EXPERIMENTAL**.
- **`scripts/start_nexus_runtime.sh`** and `run_train_bg.sh`: **LEGACY**. Execution is now managed via standard `python backend/main.py`.

#### 4. Unused ML Components
- **`ai/rl/d3qn_multimodal.py`**: **LEGACY**. The codebase explicitly moved to StableBaselines3 PPO (`models/anomaly_v4/best_model.zip`).
- **`argus_stream_extracted/argus stream A/demo.py`**: **ORPHANED**. This is a standalone Gradio app for the CV pipeline that is never invoked by the main ATMS backend.

### Technical Debt Assessment
The repository is carrying a massive amount of "Phantom Tech" (code that looks impressive in the directory tree but doesn't execute). To cleanly split Phase B for a hackathon, deleting `modules/` and `frontend_old/` is highly recommended to reduce cognitive overhead and pass technical due diligence.
