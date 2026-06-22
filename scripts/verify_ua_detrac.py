import os
import cv2
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DATA_DIR = Path("data/raw/ua_detrac")
OUTPUT_JSON = Path("data/raw/ua_detrac_inventory.json")

def verify_dataset():
    if not DATA_DIR.exists():
        logging.error(f"Dataset directory not found: {DATA_DIR}")
        return
        
    inventory = {
        "dataset": "UA-DETRAC",
        "total_videos": 0,
        "total_size_bytes": 0,
        "total_size_mb": 0.0,
        "corrupted_videos": [],
        "valid_videos": []
    }

    # Video extensions that OpenCV can read
    video_exts = {".mp4", ".avi", ".mkv", ".mov"}
    
    for file_path in DATA_DIR.rglob("*"):
        if file_path.is_file():
            inventory["total_size_bytes"] += file_path.stat().st_size
            
            if file_path.suffix.lower() in video_exts:
                inventory["total_videos"] += 1
                try:
                    cap = cv2.VideoCapture(str(file_path))
                    if not cap.isOpened():
                        raise ValueError("OpenCV cannot open file")
                    
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        raise ValueError("Cannot read first frame")
                    
                    # Read properties
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    
                    inventory["valid_videos"].append({
                        "path": str(file_path.relative_to(DATA_DIR)),
                        "resolution": f"{width}x{height}",
                        "fps": fps,
                        "frame_count": frame_count
                    })
                    cap.release()
                except Exception as e:
                    logging.warning(f"Corrupt or unreadable video: {file_path} - {e}")
                    inventory["corrupted_videos"].append(str(file_path.relative_to(DATA_DIR)))
                    
    inventory["total_size_mb"] = inventory["total_size_bytes"] / (1024 * 1024)
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump(inventory, f, indent=4)
        
    logging.info(f"Verification complete. Inventory saved to {OUTPUT_JSON}")
    logging.info(f"Total Videos: {inventory['total_videos']} | Valid: {len(inventory['valid_videos'])} | Corrupt: {len(inventory['corrupted_videos'])}")
    logging.info(f"Total Size: {inventory['total_size_mb']:.2f} MB")

if __name__ == "__main__":
    verify_dataset()
