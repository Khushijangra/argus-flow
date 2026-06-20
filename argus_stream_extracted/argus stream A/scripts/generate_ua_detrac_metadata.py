import os
import json
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_dir', type=str, required=True)
    parser.add_argument('--output_dir', type=str, required=True)
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {input_path} for sequences...")
    
    seq_counts = {}
    for sub_dir in ['images/train', 'images/val']:
        target_dir = input_path / sub_dir
        if target_dir.exists():
            for img_path in target_dir.rglob('*.jpg'):
                seq_name = img_path.parent.name
                seq_counts[seq_name] = seq_counts.get(seq_name, 0) + 1

    if not seq_counts:
        for img_path in input_path.rglob('*.jpg'):
                seq_name = img_path.parent.name
            seq_counts[seq_name] = seq_counts.get(seq_name, 0) + 1

    sequences = [{'name': name, 'frames': count} for name, count in sorted(seq_counts.items())]

    if not sequences:
        print("Warning: No images found. Waiting for extraction to complete.")
        return

    # Split logic (simulate train/test split based on sequence availability)
    train_seqs = sequences[:len(sequences)//2]
    test_seqs = sequences[len(sequences)//2:]

    splits = {
        "train": {"normal": [s['name'] for s in train_seqs], "abnormal": []},
        "val": {"normal": [], "abnormal": []},
        "test": {"normal": [], "abnormal": [s['name'] for s in test_seqs]}
    }

    # Heuristically inject anomalies for the test set
    frame_labels = {}
    for s in test_seqs:
        n = s['frames']
        normal_len = int(n * 0.7)
        anomaly_len = n - normal_len
        labels = [0] * normal_len + [1] * anomaly_len
        frame_labels[s['name']] = labels

    scenes = {s['name']: 1 for s in sequences}

    with open(output_path / "ua_detrac_splits.json", "w") as f:
        json.dump(splits, f, indent=2)

    with open(output_path / "ua_detrac_frame_labels.json", "w") as f:
        json.dump(frame_labels, f, indent=2)

    with open(output_path / "ua_detrac_scenes.json", "w") as f:
        json.dump(scenes, f, indent=2)

    total_frames = sum(s['frames'] for s in sequences)
    print(f"total sequences found: {len(sequences)}")
    print(f"total frames found: {total_frames}")
    print(f"train sequences: {len(train_seqs)}")
    print(f"test sequences: {len(test_seqs)}")
    print(f"Output metadata files generated at {output_path}:")
    print(f"  - {output_path / 'ua_detrac_splits.json'}")
    print(f"  - {output_path / 'ua_detrac_frame_labels.json'}")
    print(f"  - {output_path / 'ua_detrac_scenes.json'}")

if __name__ == '__main__':
    main()
