import os
import sys
import json
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.stream_a import evaluate_checkpoint
from src.utils.config import load_config

def main():
    config = load_config(dataset="ua_detrac")
    checkpoint_path = Path("../../outputs/ua_detrac_stream_a_run1/checkpoints/stream_a/best_clip.pt")
    
    print("Loading test dataset and evaluating checkpoint...")
    results = evaluate_checkpoint(
        checkpoint_path=checkpoint_path,
        config=config,
        device="cuda",
        split="test",
        signal_kind="log_density",
        sigma_strategy="gmm",
        gmm_components=5,
        single_sigma_index=None,
        smoothing_sigma=0.0,
    )
    
    output_dir = Path("../../outputs/ua_detrac_stream_a_run1/evaluation")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Anomaly scores per clip
    clip_scores = {}
    for video_name, scores in results["clip_scores_by_video"].items():
        clip_scores[video_name] = scores.tolist()
    with open(output_dir / "clip_scores.json", "w") as f:
        json.dump(clip_scores, f, indent=2)
        
    # 2. Sequence ranking table & scores per sequence
    sequence_scores = {}
    for video_name, scores in results["clip_scores_by_video"].items():
        sequence_scores[video_name] = {
            "max_anomaly_score": float(np.max(scores)),
            "mean_anomaly_score": float(np.mean(scores)),
            "auc": float(results["per_video_auc"].get(video_name, 0.0))
        }
        
    with open(output_dir / "sequence_scores.json", "w") as f:
        json.dump(sequence_scores, f, indent=2)
        
    print("\n--- TOP ANOMALOUS SEQUENCES (by Max Clip Score) ---")
    sorted_seqs = sorted(sequence_scores.items(), key=lambda x: x[1]["max_anomaly_score"], reverse=True)
    for name, stats in sorted_seqs[:10]:
        print(f"Sequence: {name} | Max Score: {stats['max_anomaly_score']:.4f} | Mean Score: {stats['mean_anomaly_score']:.4f} | AUC: {stats['auc']:.4f}")
        
    print(f"\nTotal sequences evaluated: {results['num_videos']}")
    print(f"Total clips/frames: {results['num_frames']}")
    print(f"Micro AUC: {results['micro_auc']:.4f}")
    print(f"Macro AUC: {results['macro_auc']:.4f}")
    print(f"Clip AUC: {results['clip_auc']:.4f}")
    print(f"\nOutputs successfully saved to: {output_dir}")

if __name__ == "__main__":
    main()
