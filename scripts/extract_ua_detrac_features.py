import os
import sys
import argparse
import numpy as np
import logging
from pathlib import Path
from collections import defaultdict

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Make sure we can import from argus stream A
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARGUS_STREAM_A = PROJECT_ROOT / "argus_stream_extracted" / "argus stream A"
if str(ARGUS_STREAM_A) not in sys.path:
    sys.path.append(str(ARGUS_STREAM_A))

try:
    from src.models.backbones.videomae import VideoMAEFeatureExtractor
except ImportError:
    logger.error(f"Cannot import VideoMAEFeatureExtractor. Make sure {ARGUS_STREAM_A} exists and contains src.models.backbones.videomae.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Extract VideoMAE features for UA-DETRAC dataset.")
    parser.add_argument('--input_dir', type=str, default='data/raw/ua_detrac/extracted/content/UA-DETRAC/DETRAC_Upload', help="Base directory containing images/train and images/val")
    parser.add_argument('--output_dir', type=str, default='data/features/ua_detrac/videomae', help="Where to save .npy features")
    parser.add_argument('--batch_size', type=int, default=16)
    parser.add_argument('--num_workers', type=int, default=4)
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Scanning {input_path} for frames...")
    
    # Group frames by sequence
    sequences = defaultdict(list)
    for sub_dir in ['images/train', 'images/val']:
        target_dir = input_path / sub_dir
        if target_dir.exists():
            for img_path in target_dir.rglob('*.jpg'):
                seq_name = img_path.parent.name
                sequences[seq_name].append(img_path)

    # Fallback if specific folders aren't found
    if not sequences:
        for img_path in input_path.rglob('*.jpg'):
                seq_name = img_path.parent.name
            sequences[seq_name].append(img_path)

    if not sequences:
        logger.error("No images found. Exiting.")
        return

    # Sort each sequence numerically
    for seq_name in sequences:
        sequences[seq_name].sort(key=lambda p: p.name)

    logger.info(f"Found {len(sequences)} sequences.")

    # Ensure CUDA
    import torch
    if not torch.cuda.is_available():
        logger.warning("CUDA is NOT available! Using CPU.")
    else:
        logger.info(f"CUDA is available: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB)")

    # Load extractor
    extractor = VideoMAEFeatureExtractor()

    processed_count = 0
    written_count = 0

    seq_names = sorted(sequences.keys())
    for idx, seq_name in enumerate(seq_names, 1):
        out_file = output_path / f"{seq_name}.npy"
        
        # Skip if already exists
        if out_file.exists():
            logger.info(f"[{idx}/{len(seq_names)}] Skipping {seq_name}, feature file already exists.")
            processed_count += 1
            continue

        frame_paths = sequences[seq_name]
        logger.info(f"[{idx}/{len(seq_names)}] Extracting features for {seq_name} ({len(frame_paths)} frames)...")
        
        current_batch_size = args.batch_size
        features = None
        
        while current_batch_size > 0:
            try:
                features = extractor.extract_single_video(
                    frame_paths,
                    batch_size=current_batch_size,
                    num_workers=args.num_workers
                )
                break  # Success
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    logger.warning(f"  -> CUDA OOM at batch size {current_batch_size}. Retrying with {current_batch_size // 2}...")
                    current_batch_size //= 2
                    if current_batch_size == 0:
                        logger.error(f"  -> Failed to extract {seq_name}: OOM even at batch size 1.")
                        break
                else:
                    logger.error(f"  -> Failed to extract features for {seq_name}: {e}")
                    break
        
        if features is not None:
            np.save(str(out_file), features)
            logger.info(f"  -> Saved {out_file.name} with shape {features.shape}")
            written_count += 1
            
        processed_count += 1

    logger.info("Extraction complete.")
    logger.info(f"Total sequences processed: {processed_count}")
    logger.info(f"Total feature files written: {written_count}")

if __name__ == "__main__":
    main()
