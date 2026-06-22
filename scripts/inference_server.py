import sys
import os
import time
from typing import List, Dict
from collections import deque
import numpy as np
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import torch

# Add MULDE paths
STREAM_A_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "argus_stream_extracted", "argus stream A"))
sys.path.insert(0, STREAM_A_SRC)

try:
    from src.models.scorers.mulde import MULDEScorer
except ImportError as e:
    print(f"Warning: Could not import MULDEScorer: {e}")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_PT = PROJECT_ROOT / "models" / "stream_a" / "best_clip.pt"
CHECKPOINT_GMM = PROJECT_ROOT / "models" / "stream_a" / "best_clip_gmm.pkl"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

class InferenceRequest(BaseModel):
    camera_id: str
    intersection_id: str
    timestamp: str
    sequence_id: str
    features: List[float]  # 768-dim list

class AnomalyEvent(BaseModel):
    event_id: str
    timestamp: str
    camera_id: str
    intersection_id: str
    anomaly_score: float
    normalized_severity: float
    confidence: float
    source: str

app = FastAPI(title="Stream-A Inference API")

# Global State
scorer: MULDEScorer = None
camera_buffers: Dict[str, deque] = {}

@app.on_event("startup")
def load_models():
    global scorer
    if not CHECKPOINT_PT.exists():
        raise RuntimeError(f"Missing required artifact: {CHECKPOINT_PT}")
    if not CHECKPOINT_GMM.exists():
        raise RuntimeError(f"Missing required artifact: {CHECKPOINT_GMM}")
        
    print(f"Loading Stream-A MULDE on {DEVICE}...")
    scorer = MULDEScorer.load_checkpoint(CHECKPOINT_PT, device=DEVICE)
    scorer.eval()

def gaussian_smooth(scores: np.ndarray, sigma: float = 2.0) -> float:
    """Applies gaussian smoothing to a 1D array of scores. Returns the smoothed value for the last frame."""
    from scipy.ndimage import gaussian_filter1d
    if len(scores) < 2 or sigma == 0:
        return float(scores[-1])
    smoothed = gaussian_filter1d(scores, sigma=sigma)
    return float(smoothed[-1])

def normalize_severity(score: float, min_val: float = 0.0, max_val: float = 1000.0) -> float:
    """Converts a raw GMM/distance anomaly score into a [0,1] severity metric."""
    if score <= min_val: return 0.0
    if score >= max_val: return 1.0
    return (score - min_val) / (max_val - min_val)

@app.post("/api/v1/anomaly/detect", response_model=AnomalyEvent)
def detect_anomaly(req: InferenceRequest):
    if scorer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if len(req.features) != 768:
        raise HTTPException(status_code=400, detail="Expected 768-dim feature vector")
        
    cam = req.camera_id
    if cam not in camera_buffers:
        camera_buffers[cam] = deque(maxlen=5)
        
    with torch.no_grad():
        x = torch.tensor(req.features, dtype=torch.float32).unsqueeze(0).to(DEVICE) # [1, 768]
        raw_scores = scorer.score_anomaly(x)  # returns ndarray
        raw_score = float(raw_scores[0])
        
    camera_buffers[cam].append(raw_score)
    buffer_array = np.array(list(camera_buffers[cam]))
    
    # Smooth score over last up to 5 frames
    smoothed_score = gaussian_smooth(buffer_array, sigma=2.0)
    
    # Normalize
    # We will use an empirical range. In UA-DETRAC, GMM NLL often varies from 0 to 500+
    severity = normalize_severity(smoothed_score, min_val=50.0, max_val=400.0)
    
    # Confidence (dummy for now, inversely related to severity variance)
    confidence = 0.95
    
    event = AnomalyEvent(
        event_id=f"evt_{int(time.time()*1000)}",
        timestamp=req.timestamp,
        camera_id=cam,
        intersection_id=req.intersection_id,
        anomaly_score=smoothed_score,
        normalized_severity=severity,
        confidence=confidence,
        source="stream_a_mulde"
    )
    return event

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
