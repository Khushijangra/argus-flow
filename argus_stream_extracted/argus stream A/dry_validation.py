import sys
import os
sys.path.append(os.getcwd())
from pathlib import Path
from src.data.datasets import VideoMAEClipDataset
from torch.utils.data import DataLoader
import numpy as np
from sklearn.metrics import roc_auc_score

features_dir = Path('../../data/features/ua_detrac/videomae')
metadata_dir = Path('../../data/metadata')

val_dataset = VideoMAEClipDataset(features_dir, metadata_dir, split="val", mode="eval", dataset_name="ua_detrac")
test_dataset = VideoMAEClipDataset(features_dir, metadata_dir, split="test", mode="eval", dataset_name="ua_detrac")

print(f"Val dataset clips: {len(val_dataset)}")
print(f"Test dataset clips: {len(test_dataset)}")

val_loader = DataLoader(val_dataset, batch_size=2)
test_loader = DataLoader(test_dataset, batch_size=2)

print("Val batch shapes:")
for x, y in val_loader:
    print(x.shape, y.shape)
    break

print("Test batch shapes:")
for x, y in test_loader:
    print(x.shape, y.shape)
    break

labels = [item[1] for item in val_dataset.samples]
print(f"Val labels unique: {np.unique(labels, return_counts=True)}")
try:
    scores = np.random.rand(len(labels))
    auc = roc_auc_score(labels, scores)
    print("roc_auc_score successfully computed on Val!")
except Exception as e:
    print("Error computing AUC on val:", e)

labels_test = [item[1] for item in test_dataset.samples]
print(f"Test labels unique: {np.unique(labels_test, return_counts=True)}")
try:
    scores = np.random.rand(len(labels_test))
    auc = roc_auc_score(labels_test, scores)
    print("roc_auc_score successfully computed on Test!")
except Exception as e:
    print("Error computing AUC on test:", e)
