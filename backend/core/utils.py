import importlib
import logging
import json
from backend.core.config import _BOOT_DEMO_MODE, _import_errors

logger = logging.getLogger(__name__)

def _safe_import(module_path: str, class_name: str):
    """Import a class, returning None on failure."""
    if _BOOT_DEMO_MODE and module_path.startswith(("ai.", "modules.", "control.", "iot.")):
        if module_path.startswith("modules."):
            _import_errors[module_path] = "skipped in demo mode"
        return None
    try:
        mod = __import__(module_path, fromlist=[class_name])
        return getattr(mod, class_name)
    except Exception as exc:
        _import_errors[module_path] = str(exc)
        return None


EmergencyCorridorEngine = _safe_import("modules.emergency.corridor", "EmergencyCorridorEngine")
CarbonCreditEngine = _safe_import("modules.carbon.engine", "CarbonCreditEngine")
PedestrianSafetyAI = _safe_import("modules.pedestrian_safety.safety", "PedestrianSafetyAI")
SignalAnomalyDetector = _safe_import("modules.cybersecurity.signal_security", "SignalAnomalyDetector")
RoadMaintenanceAI = _safe_import("modules.road_maintenance.maintenance", "RoadMaintenanceAI")
NLCommandParser = _safe_import("modules.nl_command.parser", "NLCommandParser")
CounterfactualEngine = _safe_import("modules.counterfactual.engine", "CounterfactualEngine")
VoiceBroadcast = _safe_import("modules.voice_broadcast.broadcast", "VoiceBroadcast")


def _optional_cv2():
    try:
        import cv2  # type: ignore
        return cv2
    except Exception:
        return None



def _optional_torch():
    try:
        import torch  # type: ignore
        return torch
    except Exception:
        return None


def _check_gpu() -> dict:
    try:
        torch = _optional_torch()
        if torch is None:
            return {"available": False}
        if torch.cuda.is_available():
            return {"available": True, "name": torch.cuda.get_device_name(0),
                    "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)}
    except Exception:
        pass
    return {"available": False}



def _load_json_safe(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}



