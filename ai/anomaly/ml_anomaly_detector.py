"""
ML-Enhanced Anomaly Detection for Traffic Data
================================================
Extends the statistical anomaly detector with learned models:

1. **Isolation Forest** (unsupervised) — detects out-of-distribution traffic patterns
2. **Autoencoder** (neural) — learns normal traffic manifold, flags high reconstruction error
3. **Ensemble Voting** — combines statistical + IsolationForest + Autoencoder detections

Both models train online on buffered observations and adapt to evolving patterns.

Usage:
  python -m prediction.ml_anomaly_detector --generate --train --evaluate
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

import torch.nn as nn

logger = logging.getLogger(__name__)

class TrafficAutoencoder(nn.Module):
    def __init__(self, in_dim, hidden, latent):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden, latent),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent, hidden),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden, in_dim),
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z), z



# Feature set for traffic anomaly detection (per intersection)
TRAFFIC_FEATURES = [
    "vehicle_count_N", "vehicle_count_S", "vehicle_count_E", "vehicle_count_W",
    "avg_speed_N", "avg_speed_S", "avg_speed_E", "avg_speed_W",
    "queue_length_N", "queue_length_S", "queue_length_E", "queue_length_W",
    "occupancy_pct",
    "hour_sin", "hour_cos",
]


@dataclass
class MLAnomalyAlert:
    """An anomaly detected by the ML ensemble."""
    timestamp: float
    anomaly_score: float          # combined score [0, 1]
    detectors_fired: List[str]    # which models flagged it
    severity: str                 # LOW | MEDIUM | HIGH | CRITICAL
    features: Dict[str, float]    # snapshot of feature values
    reconstruction_error: float = 0.0   # autoencoder reconstruction error
    isolation_score: float = 0.0        # isolation forest score

    @property
    def message(self) -> str:
        return (
            f"[{self.severity}] Anomaly (score={self.anomaly_score:.3f}): "
            f"{', '.join(self.detectors_fired)} | "
            f"recon_err={self.reconstruction_error:.4f}"
        )


class MLAnomalyDetector:
    """
    ML-enhanced anomaly detector combining:
      - Isolation Forest (scikit-learn)
      - Autoencoder (PyTorch)
      - Statistical baselines (Z-score, IQR)

    Trains online from buffered observations.
    """

    def __init__(
        self,
        n_features: int = 15,
        buffer_size: int = 2000,
        iforest_contamination: float = 0.05,
        ae_hidden: int = 32,
        ae_latent: int = 8,
        recon_threshold_pct: float = 95.0,
        z_threshold: float = 3.0,
        device: str = "cuda",
    ):
        self.n_features = n_features
        self.buffer_size = buffer_size
        self._buffer: Deque[np.ndarray] = deque(maxlen=buffer_size)
        self._alert_history: List[MLAnomalyAlert] = []

        # Config
        self.z_threshold = z_threshold
        self.iforest_contamination = iforest_contamination
        self.recon_threshold_pct = recon_threshold_pct
        self.ae_hidden = ae_hidden
        self.ae_latent = ae_latent

        # Models (initialized on first fit)
        self._iforest = None
        self._autoencoder = None
        self._ae_threshold = None
        self._fitted = False

        # Normalization
        self._mean = None
        self._std = None

        # Device for autoencoder
        import torch
        self.device = torch.device(
            device if device == "cuda" and torch.cuda.is_available() else "cpu"
        )

    # ------------------------------------------------------------------ #
    #  Data buffering                                                     #
    # ------------------------------------------------------------------ #

    def add_observation(self, features: np.ndarray) -> None:
        """Add a single observation vector [n_features]."""
        self._buffer.append(np.asarray(features, dtype=np.float32))

    def add_batch(self, features: np.ndarray) -> None:
        """Add multiple observations [N, n_features]."""
        for row in features:
            self._buffer.append(row.astype(np.float32))

    # ------------------------------------------------------------------ #
    #  Training                                                           #
    # ------------------------------------------------------------------ #

    def fit(self, data: Optional[np.ndarray] = None, ae_epochs: int = 50) -> Dict:
        """
        Train both Isolation Forest and Autoencoder.

        Parameters
        ----------
        data : optional external training data [N, n_features]
        ae_epochs : autoencoder training epochs

        Returns
        -------
        dict : training metrics
        """
        if data is None:
            if len(self._buffer) < 100:
                logger.warning("[MLAnomaly] Not enough data to train (need >= 100)")
                return {"error": "insufficient data"}
            data = np.array(self._buffer)

        # Normalize
        self._mean = data.mean(axis=0)
        self._std = data.std(axis=0) + 1e-8
        data_norm = (data - self._mean) / self._std

        metrics = {}

        # 1. Isolation Forest
        metrics["isolation_forest"] = self._fit_iforest(data_norm)

        # 2. Autoencoder
        metrics["autoencoder"] = self._fit_autoencoder(data_norm, epochs=ae_epochs)

        self._fitted = True
        logger.info(f"[MLAnomaly] Models trained on {len(data)} samples")
        return metrics

    def _fit_iforest(self, data: np.ndarray) -> Dict:
        """Train Isolation Forest."""
        from sklearn.ensemble import IsolationForest

        self._iforest = IsolationForest(
            n_estimators=100,
            contamination=self.iforest_contamination,
            random_state=42,
            n_jobs=-1,
        )
        self._iforest.fit(data)

        scores = -self._iforest.score_samples(data)  # higher = more anomalous
        return {
            "n_samples": len(data),
            "mean_score": float(scores.mean()),
            "anomaly_pct": float((self._iforest.predict(data) == -1).mean() * 100),
        }

    def _fit_autoencoder(self, data: np.ndarray, epochs: int = 50) -> Dict:
        """Train Autoencoder for reconstruction-based anomaly detection."""
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset

        n_feat = data.shape[1]

        self._autoencoder = TrafficAutoencoder(
            n_feat, self.ae_hidden, self.ae_latent
        ).to(self.device)

        optimizer = torch.optim.Adam(self._autoencoder.parameters(), lr=1e-3)
        criterion = nn.MSELoss()

        dataset = TensorDataset(torch.FloatTensor(data))
        loader = DataLoader(dataset, batch_size=64, shuffle=True)

        losses = []
        self._autoencoder.train()
        for epoch in range(1, epochs + 1):
            epoch_loss = 0
            for (batch,) in loader:
                batch = batch.to(self.device)
                recon, _ = self._autoencoder(batch)
                loss = criterion(recon, batch)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item() * len(batch)
            losses.append(epoch_loss / len(data))

        # Compute threshold as percentile of reconstruction errors on training data
        self._autoencoder.eval()
        with torch.no_grad():
            data_t = torch.FloatTensor(data).to(self.device)
            recon, _ = self._autoencoder(data_t)
            errors = ((recon - data_t) ** 2).mean(dim=1).cpu().numpy()

        self._ae_threshold = float(np.percentile(errors, self.recon_threshold_pct))

        return {
            "final_loss": float(losses[-1]),
            "threshold": self._ae_threshold,
            "epochs": epochs,
            "latent_dim": self.ae_latent,
        }

    # ------------------------------------------------------------------ #
    #  Detection                                                          #
    # ------------------------------------------------------------------ #

    def detect(self, features: np.ndarray) -> Optional[MLAnomalyAlert]:
        """
        Check a single observation for anomalies.

        Parameters
        ----------
        features : [n_features]

        Returns
        -------
        MLAnomalyAlert if anomaly detected, else None
        """
        if not self._fitted:
            return None

        features = np.asarray(features, dtype=np.float32)
        feat_norm = (features - self._mean) / self._std

        detectors_fired = []
        iso_score = 0.0
        recon_error = 0.0

        # 1. Statistical Z-score (any feature beyond threshold)
        z_scores = np.abs(feat_norm)
        if np.any(z_scores > self.z_threshold):
            detectors_fired.append("z_score")

        # 2. Isolation Forest
        if self._iforest is not None:
            iso_score = float(-self._iforest.score_samples(feat_norm.reshape(1, -1))[0])
            if self._iforest.predict(feat_norm.reshape(1, -1))[0] == -1:
                detectors_fired.append("isolation_forest")

        # 3. Autoencoder
        if self._autoencoder is not None:
            import torch
            self._autoencoder.eval()
            with torch.no_grad():
                x = torch.FloatTensor(feat_norm).unsqueeze(0).to(self.device)
                recon, latent = self._autoencoder(x)
                recon_error = float(((recon - x) ** 2).mean().cpu())
            if recon_error > self._ae_threshold:
                detectors_fired.append("autoencoder")

        if not detectors_fired:
            return None

        # Anomaly score = weighted combination
        n_fired = len(detectors_fired)
        anomaly_score = n_fired / 3.0  # simple: proportion of detectors

        severity = (
            "CRITICAL" if n_fired == 3
            else "HIGH" if n_fired == 2
            else "MEDIUM"
        )

        alert = MLAnomalyAlert(
            timestamp=time.time(),
            anomaly_score=anomaly_score,
            detectors_fired=detectors_fired,
            severity=severity,
            features={f"f{i}": float(features[i]) for i in range(len(features))},
            reconstruction_error=recon_error,
            isolation_score=iso_score,
        )
        self._alert_history.append(alert)
        return alert

    def detect_batch(self, data: np.ndarray) -> List[MLAnomalyAlert]:
        """Detect anomalies in a batch of observations."""
        alerts = []
        for row in data:
            alert = self.detect(row)
            if alert is not None:
                alerts.append(alert)
        return alerts

    # ------------------------------------------------------------------ #
    #  Evaluation                                                         #
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        normal_data: np.ndarray,
        anomaly_data: np.ndarray,
    ) -> Dict:
        """
        Evaluate detection performance with labeled normal/anomaly data.

        Returns precision, recall, F1, and per-detector breakdown.
        """
        tp = fp = tn = fn = 0
        detector_counts = {"z_score": 0, "isolation_forest": 0, "autoencoder": 0}

        # Normal data — expect no alerts
        for row in normal_data:
            alert = self.detect(row)
            if alert is None:
                tn += 1
            else:
                fp += 1

        # Anomaly data — expect alerts
        for row in anomaly_data:
            alert = self.detect(row)
            if alert is not None:
                tp += 1
                for d in alert.detectors_fired:
                    detector_counts[d] = detector_counts.get(d, 0) + 1
            else:
                fn += 1

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-10)

        return {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "accuracy": round((tp + tn) / max(tp + fp + tn + fn, 1), 4),
            "detector_breakdown": detector_counts,
        }

    def recent_alerts(self, n: int = 20) -> List[MLAnomalyAlert]:
        return list(reversed(self._alert_history[-n:]))

    def save(self, path: str = "models/ml_anomaly") -> None:
        """Save trained models to disk."""
        import torch
        import joblib

        os.makedirs(path, exist_ok=True)

        if self._iforest is not None:
            joblib.dump(self._iforest, os.path.join(path, "iforest.pkl"))

        if self._autoencoder is not None:
            torch.save(self._autoencoder.state_dict(),
                       os.path.join(path, "autoencoder.pt"))

        np.savez(os.path.join(path, "norm_params.npz"),
                 mean=self._mean, std=self._std)

        meta = {
            "n_features": self.n_features,
            "ae_hidden": self.ae_hidden,
            "ae_latent": self.ae_latent,
            "ae_threshold": self._ae_threshold,
            "z_threshold": self.z_threshold,
            "iforest_contamination": self.iforest_contamination,
        }
        with open(os.path.join(path, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        logger.info(f"[MLAnomaly] Models saved to {path}/")

    def load(self, path: str = "models/ml_anomaly") -> None:
        """Load trained models from disk."""
        import torch
        import joblib

        iforest_path = os.path.join(path, "iforest.pkl")
        if os.path.isfile(iforest_path):
            self._iforest = joblib.load(iforest_path)

        norm_path = os.path.join(path, "norm_params.npz")
        if os.path.isfile(norm_path):
            npz = np.load(norm_path)
            self._mean = npz["mean"]
            self._std = npz["std"]

        meta_path = os.path.join(path, "meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            self._ae_threshold = meta.get("ae_threshold")

        ae_path = os.path.join(path, "autoencoder.pt")
        if os.path.isfile(ae_path):

            self._autoencoder = TrafficAutoencoder(
                self.n_features, self.ae_hidden, self.ae_latent
            ).to(self.device)
            self._autoencoder.load_state_dict(
                torch.load(ae_path, map_location=self.device, weights_only=True)
            )

        self._fitted = True
        logger.info(f"[MLAnomaly] Models loaded from {path}/")


# -----------------------------------------------------------------------
# Synthetic data generation for demonstration / testing
# -----------------------------------------------------------------------

def generate_demo_data(
    n_normal: int = 2000,
    n_anomaly: int = 100,
    n_features: int = 15,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic traffic data for anomaly detection demo.

    Returns (normal_data, anomaly_data).
    """
    rng = np.random.RandomState(seed)

    # Normal: Gaussian cluster centered around typical traffic patterns
    normal = rng.normal(loc=50, scale=10, size=(n_normal, n_features)).astype(np.float32)
    # Add time-of-day pattern to first 4 features (vehicle counts)
    hours = np.linspace(0, 24 * 7, n_normal)
    for i in range(4):
        normal[:, i] += 20 * np.sin(2 * np.pi * hours / 24 + i * 0.5)

    # Anomaly patterns
    anomaly = np.zeros((n_anomaly, n_features), dtype=np.float32)
    n_per_type = n_anomaly // 4

    # Type 1: Sudden congestion (very high vehicle counts)
    anomaly[:n_per_type, :4] = rng.normal(120, 5, (n_per_type, 4))
    anomaly[:n_per_type, 4:] = rng.normal(50, 10, (n_per_type, n_features - 4))

    # Type 2: Ghost readings (near-zero on all)
    anomaly[n_per_type:2*n_per_type] = rng.normal(2, 1, (n_per_type, n_features))

    # Type 3: Speed anomaly (very low speed, high queue)
    idx = slice(2*n_per_type, 3*n_per_type)
    anomaly[idx] = rng.normal(50, 10, (n_per_type, n_features))
    anomaly[idx, 4:8] = rng.normal(5, 2, (n_per_type, 4))   # very low speed
    anomaly[idx, 8:12] = rng.normal(100, 10, (n_per_type, 4))  # very high queue

    # Type 4: Random outliers
    anomaly[3*n_per_type:] = rng.normal(50, 10, (n_anomaly - 3*n_per_type, n_features))
    anomaly[3*n_per_type:] += rng.choice([-1, 1], size=(n_anomaly - 3*n_per_type, n_features)) * 50

    return normal, anomaly


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="ML Anomaly Detection Pipeline")
    parser.add_argument("--generate", action="store_true", help="Generate demo data")
    parser.add_argument("--train", action="store_true", help="Train models")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate on labeled data")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output", default="results/anomaly")
    args = parser.parse_args()

    print("=" * 60)
    print("  NEXUS-ATMS — ML Anomaly Detection Pipeline")
    print("=" * 60)

    os.makedirs(args.output, exist_ok=True)

    # Generate data
    print("\n[1] Generating synthetic traffic data...")
    normal_data, anomaly_data = generate_demo_data()
    print(f"    Normal samples: {len(normal_data)}")
    print(f"    Anomaly samples: {len(anomaly_data)}")

    # Initialize detector
    detector = MLAnomalyDetector(
        n_features=normal_data.shape[1],
        device=args.device,
    )

    # Train
    if args.train or args.generate:
        print("\n[2] Training ML anomaly models...")
        metrics = detector.fit(normal_data, ae_epochs=args.epochs)
        print(f"    Isolation Forest: {metrics.get('isolation_forest', {})}")
        print(f"    Autoencoder: {metrics.get('autoencoder', {})}")

        detector.save("models/ml_anomaly")

    # Evaluate
    if args.evaluate or args.generate:
        print("\n[3] Evaluating detection performance...")
        eval_results = detector.evaluate(
            normal_data[:200],
            anomaly_data,
        )
        print(f"    Precision: {eval_results['precision']:.4f}")
        print(f"    Recall:    {eval_results['recall']:.4f}")
        print(f"    F1 Score:  {eval_results['f1_score']:.4f}")
        print(f"    Accuracy:  {eval_results['accuracy']:.4f}")
        print(f"    Detector breakdown: {eval_results['detector_breakdown']}")

        # Save results
        results_path = os.path.join(args.output, "anomaly_detection_results.json")
        with open(results_path, "w") as f:
            json.dump(eval_results, f, indent=2)
        print(f"    Results saved to {results_path}")

        # Plot confusion matrix
        _plot_results(eval_results, normal_data, anomaly_data, detector, args.output)


def _plot_results(eval_results, normal_data, anomaly_data, detector, output_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle("NEXUS-ATMS — ML Anomaly Detection", fontsize=14, fontweight="bold")

    # 1. Confusion matrix
    ax = axes[0]
    cm = np.array([
        [eval_results["true_negatives"], eval_results["false_positives"]],
        [eval_results["false_negatives"], eval_results["true_positives"]],
    ])
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Normal", "Anomaly"])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Normal", "Anomaly"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black",
                    fontsize=16)

    # 2. Reconstruction error distribution
    ax = axes[1]
    if detector._autoencoder is not None:
        import torch
        detector._autoencoder.eval()
        with torch.no_grad():
            norm_d = (normal_data - detector._mean) / detector._std
            anom_d = (anomaly_data - detector._mean) / detector._std
            norm_t = torch.FloatTensor(norm_d).to(detector.device)
            anom_t = torch.FloatTensor(anom_d).to(detector.device)
            norm_recon, _ = detector._autoencoder(norm_t)
            anom_recon, _ = detector._autoencoder(anom_t)
            norm_err = ((norm_recon - norm_t) ** 2).mean(dim=1).cpu().numpy()
            anom_err = ((anom_recon - anom_t) ** 2).mean(dim=1).cpu().numpy()

        ax.hist(norm_err, bins=50, alpha=0.6, label="Normal", color="#1f77b4", density=True)
        ax.hist(anom_err, bins=50, alpha=0.6, label="Anomaly", color="#d62728", density=True)
        if detector._ae_threshold:
            ax.axvline(detector._ae_threshold, color="black", linestyle="--",
                       label=f"Threshold={detector._ae_threshold:.4f}")
        ax.set_xlabel("Reconstruction Error")
        ax.set_ylabel("Density")
        ax.set_title("Autoencoder Error Distribution")
        ax.legend()
    else:
        ax.text(0.5, 0.5, "Autoencoder not trained", ha="center", va="center")

    # 3. Detector agreement
    ax = axes[2]
    bd = eval_results.get("detector_breakdown", {})
    names = list(bd.keys())
    vals = list(bd.values())
    ax.bar(names, vals, color=["#1f77b4", "#ff7f0e", "#2ca02c"][:len(names)])
    ax.set_ylabel("Detections")
    ax.set_title("Per-Detector Anomaly Count")
    ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(output_dir, "anomaly_detection_plots.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    Plots saved to {path}")


if __name__ == "__main__":
    main()
