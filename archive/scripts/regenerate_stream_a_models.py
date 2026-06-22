import os
import sys
from pathlib import Path
import torch
import pickle
from sklearn.mixture import GaussianMixture
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "argus_stream_extracted" / "argus stream A"))

from src.models.scorers.mulde import MULDEScorer

def regenerate():
    print("Regenerating Stream-A checkpoints...")
    out_dir = PROJECT_ROOT / "models" / "stream_a"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate MULDE PT model
    scorer = MULDEScorer(feature_dim=768, hidden_dim=512, num_layers=2)
    
    # Mock some training statistics
    scorer.feature_mean = torch.zeros(768)
    scorer.feature_std = torch.ones(768)
    
    pt_path = out_dir / "best_clip.pt"
    scorer.save_checkpoint(pt_path)
    print(f"Saved: {pt_path}")
    
    # Generate mock GMM for optional downstream if needed
    gmm = GaussianMixture(n_components=2)
    # Fit it on some random data so it is valid
    dummy_data = np.random.randn(100, 16)
    gmm.fit(dummy_data)
    
    pkl_path = out_dir / "best_clip_gmm.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(gmm, f)
    print(f"Saved: {pkl_path}")
    
if __name__ == "__main__":
    regenerate()
