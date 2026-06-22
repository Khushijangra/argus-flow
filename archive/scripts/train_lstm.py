"""
LSTM Traffic Predictor — Data Generation & Training Pipeline
==============================================================
Generates synthetic traffic flow data (mimicking sensor readings)
and trains the Seq2Seq LSTM encoder-decoder for 30-minute forecasting.

Pipeline:
  1. Generate 7 simulated days of 5-minute sensor readings
  2. Create sliding-window train/val/test splits (70/15/15)
  3. Train encoder-decoder LSTM on GPU
  4. Evaluate with MAE, RMSE, MAPE, R² metrics
  5. Plot predictions vs actuals + training curves
  6. Save model checkpoint

Usage:
  python scripts/train_lstm.py                     # default settings
  python scripts/train_lstm.py --epochs 50 --days 14
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

# -----------------------------------------------------------------------
# 1. Synthetic Data Generator
# -----------------------------------------------------------------------

def generate_traffic_data(
    n_days: int = 7,
    step_minutes: float = 5.0,
    n_approaches: int = 4,
    seed: int = 42,
) -> np.ndarray:
    """
    Generate realistic synthetic traffic sensor data.

    Returns array of shape [T, n_features] where T = n_days * 288 (5-min steps).
    Features per time step (10 per approach × 4 approaches = 40 features, but
    we simplify to 10 features total for the predictor):
      0-3: vehicle_count per approach (N, S, E, W)
      4-7: queue_length per approach
      8:   hour_sin
      9:   hour_cos
    """
    rng = np.random.RandomState(seed)
    steps_per_day = int(24 * 60 / step_minutes)
    total_steps = n_days * steps_per_day

    data = np.zeros((total_steps, 10), dtype=np.float32)

    for t in range(total_steps):
        # Time features
        hour = (t % steps_per_day) * step_minutes / 60.0
        day_in_week = (t // steps_per_day) % 7

        # Time-of-day traffic pattern (bimodal: morning + evening rush)
        morning_peak = np.exp(-0.5 * ((hour - 8.5) / 1.2) ** 2)
        evening_peak = np.exp(-0.5 * ((hour - 17.5) / 1.5) ** 2)
        lunch_bump = 0.3 * np.exp(-0.5 * ((hour - 12.5) / 0.8) ** 2)
        base_factor = 0.15 + 0.6 * morning_peak + 0.7 * evening_peak + lunch_bump

        # Weekend reduction
        if day_in_week >= 5:
            base_factor *= 0.6

        # Per-approach vehicle counts (slightly asymmetric)
        approach_weights = [1.0, 0.9, 0.8, 0.85]  # N, S, E, W
        for i in range(4):
            count = base_factor * approach_weights[i] * 25.0
            count += rng.normal(0, 2)
            data[t, i] = max(0, count)

        # Queue lengths (correlated with vehicle count, lagged)
        for i in range(4):
            q = data[t, i] * 0.4 + rng.normal(0, 1)
            data[t, 4 + i] = max(0, q)

        # Cyclical hour encoding
        data[t, 8] = math.sin(2 * math.pi * hour / 24.0)
        data[t, 9] = math.cos(2 * math.pi * hour / 24.0)

    return data


# -----------------------------------------------------------------------
# 2. Dataset Preparation (sliding windows)
# -----------------------------------------------------------------------

def create_sequences(
    data: np.ndarray,
    seq_len: int = 24,
    horizon: int = 6,
    target_cols: List[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create sliding window sequences for supervised learning.

    Args:
        data: [T, n_features]
        seq_len: input window length (24 × 5min = 2 hours)
        horizon: prediction steps ahead (6 × 5min = 30 min)
        target_cols: which columns to predict (default: 0-3 = vehicle counts)

    Returns:
        X: [N, seq_len, n_features]
        Y: [N, horizon, n_targets]
    """
    if target_cols is None:
        target_cols = list(range(4))  # predict vehicle counts per approach

    X, Y = [], []
    for i in range(len(data) - seq_len - horizon + 1):
        X.append(data[i : i + seq_len])
        Y.append(data[i + seq_len : i + seq_len + horizon, target_cols])

    return np.array(X), np.array(Y)


def train_val_test_split(X, Y, train_frac=0.7, val_frac=0.15):
    """Chronological split (no shuffling to preserve time-series ordering)."""
    n = len(X)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return (
        (X[:train_end], Y[:train_end]),
        (X[train_end:val_end], Y[train_end:val_end]),
        (X[val_end:], Y[val_end:]),
    )


# -----------------------------------------------------------------------
# 3. Training Loop
# -----------------------------------------------------------------------

def train_lstm(
    epochs: int = 30,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    seq_len: int = 24,
    horizon: int = 6,
    hidden: int = 128,
    n_days: int = 7,
    device_str: str = "cuda",
    model_path: str = "models/lstm_predictor.pt",
    output_dir: str = "results/lstm",
) -> Dict:
    """Full LSTM training pipeline."""
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    device = torch.device(device_str if torch.cuda.is_available() else "cpu")
    print(f"[LSTM] Device: {device}")
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # --- Generate data ---
    print(f"[LSTM] Generating {n_days} days of synthetic traffic data...")
    data = generate_traffic_data(n_days=n_days, seed=42)
    print(f"[LSTM] Data shape: {data.shape} ({data.shape[0]} time steps, {data.shape[1]} features)")

    # Normalize to [0, 1]
    data_min = data.min(axis=0, keepdims=True)
    data_max = data.max(axis=0, keepdims=True)
    data_range = data_max - data_min
    data_range[data_range < 1e-6] = 1.0
    data_norm = (data - data_min) / data_range

    # Save normalization params for inference
    norm_params = {"min": data_min.tolist(), "max": data_max.tolist()}

    # --- Create sequences ---
    target_cols = list(range(4))  # vehicle counts
    X, Y = create_sequences(data_norm, seq_len=seq_len, horizon=horizon,
                            target_cols=target_cols)
    print(f"[LSTM] Sequences: X={X.shape}, Y={Y.shape}")

    (X_train, Y_train), (X_val, Y_val), (X_test, Y_test) = train_val_test_split(X, Y)
    print(f"[LSTM] Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    # Convert to tensors
    train_ds = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(Y_train))
    val_ds = TensorDataset(torch.FloatTensor(X_val), torch.FloatTensor(Y_val))
    test_ds = TensorDataset(torch.FloatTensor(X_test), torch.FloatTensor(Y_test))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)
    test_loader = DataLoader(test_ds, batch_size=batch_size)

    # --- Build model ---
    n_features = X.shape[2]
    n_outputs = Y.shape[2]

    # Import the project's LSTM architecture
    try:
        from ai.prediction.lstm_predictor import LSTMPredictor
        predictor = LSTMPredictor(
            n_features=n_features,
            n_outputs=n_outputs,
            horizon=horizon,
            hidden=hidden,
            device=str(device),
        )
        model = predictor.model
        print(f"[LSTM] Using project's Seq2Seq encoder-decoder architecture")
    except Exception:
        # Fallback: build a simpler LSTM
        print(f"[LSTM] Building standalone LSTM model")
        model = _build_lstm(n_features, n_outputs, horizon, hidden)

    model = model.to(device)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[LSTM] Model parameters: {total_params:,} total, {trainable_params:,} trainable")

    # --- Optimizer & scheduler ---
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5
    )
    criterion = nn.MSELoss()

    # --- Training ---
    history = {"train_loss": [], "val_loss": [], "val_mae": []}
    best_val_loss = float("inf")
    patience_counter = 0
    max_patience = 10

    print(f"\n[LSTM] Training for {epochs} epochs...")
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        # Train
        model.train()
        train_losses = []
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            # Teacher forcing ratio decays over epochs
            tf_ratio = max(0.0, 1.0 - epoch / (epochs * 0.7))
            pred = model(xb, teacher_forcing_ratio=tf_ratio, target=yb)
            loss = criterion(pred, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_losses.append(loss.item())

        avg_train = np.mean(train_losses)
        history["train_loss"].append(float(avg_train))

        # Validate
        model.eval()
        val_losses = []
        val_maes = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                pred = model(xb)
                val_losses.append(criterion(pred, yb).item())
                val_maes.append(torch.abs(pred - yb).mean().item())

        avg_val = np.mean(val_losses)
        avg_mae = np.mean(val_maes)
        history["val_loss"].append(float(avg_val))
        history["val_mae"].append(float(avg_mae))

        scheduler.step(avg_val)

        # Early stopping
        if avg_val < best_val_loss:
            best_val_loss = avg_val
            patience_counter = 0
            torch.save(model.state_dict(), model_path)
        else:
            patience_counter += 1

        if epoch % 5 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d}/{epochs} | Train Loss: {avg_train:.6f} | "
                  f"Val Loss: {avg_val:.6f} | Val MAE: {avg_mae:.6f} | "
                  f"LR: {optimizer.param_groups[0]['lr']:.6f}")

        if patience_counter >= max_patience:
            print(f"  Early stopping at epoch {epoch} (no improvement for {max_patience} epochs)")
            break

    train_time = time.time() - start_time
    print(f"\n[LSTM] Training completed in {train_time:.1f}s")
    print(f"[LSTM] Best model saved to {model_path}")

    # --- Test evaluation ---
    model.load_state_dict(torch.load(model_path, weights_only=True))
    model.eval()

    all_preds = []
    all_targets = []
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(device)
            pred = model(xb)
            all_preds.append(pred.cpu().numpy())
            all_targets.append(yb.numpy())

    preds = np.concatenate(all_preds)
    targets = np.concatenate(all_targets)

    # Metrics
    mae = float(np.mean(np.abs(preds - targets)))
    rmse = float(np.sqrt(np.mean((preds - targets) ** 2)))
    # MAPE (avoid division by zero)
    mask = targets > 0.01
    mape = float(np.mean(np.abs((preds[mask] - targets[mask]) / targets[mask])) * 100) if mask.any() else 0.0
    # R² score
    ss_res = np.sum((targets - preds) ** 2)
    ss_tot = np.sum((targets - targets.mean()) ** 2)
    r2 = float(1 - ss_res / max(ss_tot, 1e-10))

    test_metrics = {
        "MAE": mae,
        "RMSE": rmse,
        "MAPE_%": mape,
        "R2": r2,
    }

    print(f"\n[LSTM] Test Metrics:")
    print(f"  MAE  : {mae:.6f}")
    print(f"  RMSE : {rmse:.6f}")
    print(f"  MAPE : {mape:.2f}%")
    print(f"  R²   : {r2:.4f}")

    # --- Save results ---
    results = {
        "model_path": model_path,
        "train_time_s": train_time,
        "epochs_trained": len(history["train_loss"]),
        "best_val_loss": best_val_loss,
        "test_metrics": test_metrics,
        "history": history,
        "model_params": {
            "total": total_params,
            "trainable": trainable_params,
            "n_features": n_features,
            "n_outputs": n_outputs,
            "horizon": horizon,
            "hidden": hidden,
            "seq_len": seq_len,
        },
        "data_params": {
            "n_days": n_days,
            "total_steps": len(data),
            "train_size": len(X_train),
            "val_size": len(X_val),
            "test_size": len(X_test),
        },
        "normalization": norm_params,
    }
    results_path = os.path.join(output_dir, "lstm_training_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # --- Plots ---
    _generate_lstm_plots(history, preds, targets, output_dir)

    return results


def _build_lstm(n_features, n_outputs, horizon, hidden):
    """Fallback standalone encoder-decoder LSTM."""
    import torch
    import torch.nn as nn

    class FallbackLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = nn.LSTM(n_features, hidden, num_layers=2,
                                   batch_first=True, dropout=0.2,
                                   bidirectional=True)
            self.bridge = nn.Linear(hidden * 2, hidden)
            self.decoder_cell = nn.LSTMCell(n_outputs, hidden)
            self.out_proj = nn.Linear(hidden, n_outputs)

        def forward(self, x, teacher_forcing_ratio=0.0, target=None):
            enc_out, (h_n, c_n) = self.encoder(x)
            h = torch.tanh(self.bridge(
                torch.cat([h_n[-2], h_n[-1]], dim=-1)))
            c = torch.zeros_like(h)

            outputs = []
            dec_input = torch.zeros(x.size(0), n_outputs, device=x.device)
            for t in range(horizon):
                h, c = self.decoder_cell(dec_input, (h, c))
                out = self.out_proj(h)
                outputs.append(out.unsqueeze(1))
                if target is not None and np.random.random() < teacher_forcing_ratio:
                    dec_input = target[:, t, :]
                else:
                    dec_input = out
            return torch.cat(outputs, dim=1)

    return FallbackLSTM()


def _generate_lstm_plots(history, preds, targets, output_dir):
    """Generate training curves and prediction plots."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[WARN] matplotlib not installed. Skipping plots.")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("NEXUS-ATMS — LSTM Traffic Predictor", fontsize=16, fontweight="bold")

    # 1. Training curves
    ax = axes[0, 0]
    ax.plot(history["train_loss"], label="Train Loss", color="#1f77b4")
    ax.plot(history["val_loss"], label="Val Loss", color="#ff7f0e")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("MSE Loss")
    ax.set_title("Training & Validation Loss")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2. Val MAE over epochs
    ax = axes[0, 1]
    ax.plot(history["val_mae"], color="#2ca02c")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("MAE")
    ax.set_title("Validation MAE")
    ax.grid(True, alpha=0.3)

    # 3. Prediction vs Actual (first approach, first horizon step)
    ax = axes[1, 0]
    n_show = min(200, len(preds))
    ax.plot(targets[:n_show, 0, 0], label="Actual", alpha=0.8, color="#1f77b4")
    ax.plot(preds[:n_show, 0, 0], label="Predicted", alpha=0.8, color="#ff7f0e", linestyle="--")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Normalized Vehicle Count")
    ax.set_title("5-min Forecast: Predicted vs Actual (North)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 4. Prediction vs Actual (30-min horizon)
    ax = axes[1, 1]
    last_horizon = preds.shape[1] - 1
    ax.plot(targets[:n_show, last_horizon, 0], label="Actual", alpha=0.8, color="#1f77b4")
    ax.plot(preds[:n_show, last_horizon, 0], label="Predicted", alpha=0.8,
            color="#d62728", linestyle="--")
    ax.set_xlabel("Time Step")
    ax.set_ylabel("Normalized Vehicle Count")
    ax.set_title("30-min Forecast: Predicted vs Actual (North)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = os.path.join(output_dir, "lstm_training_plots.png")
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  LSTM plots saved to {plot_path}")

    # --- Scatter plot ---
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(targets[:, 0, 0], preds[:, 0, 0], alpha=0.3, s=5, color="#1f77b4")
    ax.plot([0, 1], [0, 1], "r--", label="Perfect prediction")
    ax.set_xlabel("Actual")
    ax.set_ylabel("Predicted")
    ax.set_title("LSTM Prediction Scatter (5-min horizon, North)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    scatter_path = os.path.join(output_dir, "lstm_scatter.png")
    plt.savefig(scatter_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Scatter plot saved to {scatter_path}")


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Train LSTM traffic predictor")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden", type=int, default=128)
    parser.add_argument("--seq-len", type=int, default=24, help="Input window (×5min)")
    parser.add_argument("--horizon", type=int, default=6, help="Forecast steps (×5min)")
    parser.add_argument("--days", type=int, default=7, help="Days of training data")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--model-path", default="models/lstm_predictor.pt")
    args = parser.parse_args()

    print("=" * 60)
    print("  NEXUS-ATMS — LSTM Traffic Predictor Training")
    print("=" * 60)

    train_lstm(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        hidden=args.hidden,
        seq_len=args.seq_len,
        horizon=args.horizon,
        n_days=args.days,
        device_str=args.device,
        model_path=args.model_path,
    )


if __name__ == "__main__":
    main()
