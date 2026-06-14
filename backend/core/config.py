import os
from typing import Dict

_IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))
_demo_mode_env = os.getenv("DEMO_MODE")
if _demo_mode_env is None:
    _BOOT_DEMO_MODE = _IS_RAILWAY
else:
    _BOOT_DEMO_MODE = _demo_mode_env.lower() == "true"

_import_errors: Dict[str, str] = {}

HARDENED_MODE = os.getenv("HARDENED_MODE", "false").lower() == "true"
CONTROL_API_KEY = os.getenv("CONTROL_API_KEY", "").strip()

ANOMALY_MODEL_DIR = os.getenv("ANOMALY_MODEL_DIR", "models/ml_anomaly")
AI_STATUS_DQN_MODEL_PATH = os.getenv("AI_STATUS_DQN_MODEL_PATH", "models/dqn_20260226_014406/best/best_model.zip")
AI_STATUS_LSTM_MODEL_PATH = os.getenv("AI_STATUS_LSTM_MODEL_PATH", "models/lstm_predictor.pt")
AI_EXPLAIN_MODEL_PATH = os.getenv("AI_EXPLAIN_MODEL_PATH", AI_STATUS_DQN_MODEL_PATH)
