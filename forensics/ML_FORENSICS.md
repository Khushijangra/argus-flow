# EVOLUTION FORENSICS AUDIT
## Document 8: ML_FORENSICS.md

### Machine Learning Forensics

NEXUS-ATMS boasts two massive ML pipelines: The RL Control Agent and the CV Anomaly Detector.

#### 1. StableBaselines3 PPO (Reinforcement Learning)
*   **Training Script**: `scripts/train_anomaly_policy.py`. **EXISTS & WORKS**. It loads the custom Gymnasium `TrafficEnvironment` and trains for exactly 200,000 timesteps.
*   **Inference**: `backend/runtime/hybrid_runtime.py`. **INTEGRATED**. The backend correctly instantiates the environment and loads `models/anomaly_v4/best_model.zip`.
*   **Status**: **REAL & INTEGRATED**. This is the strongest intellectual property in the repository.

#### 2. VideoMAE + MULDE (Computer Vision / Stream A)
*   **Directory**: `argus_stream_extracted/argus stream A/`
*   **Training/Inference Scripts**: `scripts/train.py`, `demo.py`, `scripts/extract_features.py`. **EXISTS**.
*   **Checkpoints**: Exists in `data/` directories (e.g., Avenue dataset mappings).
*   **Integration**: **DISCONNECTED**. Despite being a fully functioning standalone Gradio application and CLI tool, the backend `hybrid_runtime.py` completely bypasses it. Rather than actually streaming video frames to VideoMAE, the backend expects a `POST /api/inject` to mathematically hardcode an `anomaly_severity` of 0.85.

#### 3. Legacy Deep Q-Network
*   **File**: `ai/rl/d3qn_multimodal.py`
*   **Status**: **LEGACY**. The codebase transitioned to SB3 PPO for greater stability.

### ML Conclusion
The RL pipeline is 100% legitimate and forms the core of the backend execution. The CV pipeline is real but relegated to "Offline/Standalone" status, heavily mocked in the live React UI to prevent heavy GPU processing bottlenecks during live demonstrations.
