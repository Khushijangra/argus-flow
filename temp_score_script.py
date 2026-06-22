
import sys
import torch
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(r'C:\Users\Asus\OneDrive\Desktop\projects\urban congestion')))
sys.path.insert(0, str(Path(r'C:\Users\Asus\OneDrive\Desktop\projects\urban congestion\argus_stream_extracted\argus stream A')))
from src.models.scorers.mulde import MULDEScorer

embeddings = np.load("temp_embeddings.npy")
ckpt_path = Path(r'C:\Users\Asus\OneDrive\Desktop\projects\urban congestion') / "models/stream_a/best_clip.pt"
scorer = MULDEScorer.load_checkpoint(ckpt_path, device="cuda" if torch.cuda.is_available() else "cpu")
scorer.eval()
with torch.no_grad():
    x = torch.tensor(embeddings, dtype=torch.float32).to(next(scorer.parameters()).device)
    raw_scores = scorer.score_anomaly(x)
    raw_score = float(raw_scores[0])

with open("temp_score.txt", "w") as f:
    f.write(str(raw_score))
