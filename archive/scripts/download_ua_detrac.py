import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DATA_DIR = Path("data/raw/ua_detrac")
KAGGLE_CREDS_PATH = Path(os.path.expanduser("~/.kaggle/kaggle.json"))

# Official source is gated by a web form, so we prioritize Kaggle community uploads.
KAGGLE_DATASET_ID = "ssrb5000/ua-detrac"  # Example community dataset for DETRAC

def install_kaggle():
    try:
        import kaggle
    except ImportError:
        logging.info("Kaggle module not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "kaggle"])
        import kaggle

def download_via_kaggle():
    if not KAGGLE_CREDS_PATH.exists():
        logging.error(f"Kaggle credentials not found at {KAGGLE_CREDS_PATH}")
        return False
    
    install_kaggle()
    logging.info(f"Downloading {KAGGLE_DATASET_ID} via Kaggle API to {DATA_DIR}...")
    try:
        # The Kaggle CLI natively supports resuming interrupted downloads.
        subprocess.check_call([
            sys.executable, "-m", "kaggle", "datasets", "download",
            "-d", KAGGLE_DATASET_ID,
            "-p", str(DATA_DIR),
            "--unzip"
        ])
        logging.info("Download and extraction completed via Kaggle.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Kaggle download failed: {e}")
        return False

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    success = download_via_kaggle()
    if not success:
        logging.error("Automated acquisition blocked due to missing Kaggle credentials or blocked access.")
        logging.info("--- MANUAL ACQUISITION INSTRUCTIONS ---")
        logging.info("1. Visit the official website: https://detrac-db.rit.albany.edu/Downloads")
        logging.info("2. Register and accept the Data Usage Agreement.")
        logging.info("3. Download the 'DETRAC-train-data' and 'DETRAC-test-data' zip files.")
        logging.info(f"4. Extract the contents directly into: {DATA_DIR.absolute()}")
        logging.info("---------------------------------------")
        sys.exit(1)

if __name__ == "__main__":
    main()
