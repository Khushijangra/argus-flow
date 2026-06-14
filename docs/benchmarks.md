# NEXUS-ATMS — Benchmark Results

## Experimental Setup

| Parameter | Value |
|-----------|-------|
| Environment | Standalone `TrafficEnvironment` (4-phase NEMA) |
| State dimension | 26 |
| Simulation duration | 720 steps per episode |
| Decision interval | 5 seconds |
| Training timesteps | 50 000 (DQN quick-train) |
| Evaluation episodes | 5 |
| Hardware | AMD Ryzen 5 5600H · NVIDIA RTX 2050 (4.3 GB) |
| Software | Python 3.13.7 · PyTorch 2.6.0+cu124 · SB3 2.x |

---

## RL Agent vs Fixed-Timing Baseline

Results from `results/evaluation_results.json` (actual evaluation run):

| Metric | Fixed-Timing Baseline | DQN Agent | Change |
|--------|-----------------------|-----------|--------|
| Mean Reward | −1 149.1 ± 317.3 | **−20.7 ± 2.2** | **+98.2 %** |
| Avg Waiting Time (s) | 581.3 | **10.2** | **↓ 98.24 %** |
| Avg Queue Length (veh) | 26.16 | **2.62** | **↓ 89.97 %** |
| Throughput (veh/hr) | 510.8 | 453.8 | ↓ 11.16 % |
| Episode Length | 720 | 720 | — |

> **Insight:** The trained DQN achieves a near-zero waiting time and a
> 10× reduction in queue length. Throughput drops slightly (−11.16 %) because
> the agent prioritises delay reduction over raw vehicle count — a favourable
> trade-off for urban livability.

---

## LSTM Traffic Predictor

| Metric | Value |
|--------|-------|
| Architecture | Seq2Seq Bidirectional LSTM (Encoder-Decoder) |
| R² Score | **0.6126** |
| MAE | **0.0746** |
| Training Epochs | 50 |
| Input Sequence | 24 time-steps |
| Forecast Horizon | 6 time-steps (~30 min) |

---

## ML Anomaly Detection

| Metric | IsolationForest | Autoencoder | Ensemble |
|--------|-----------------|-------------|----------|
| Accuracy | 0.850 | 0.900 | — |
| Precision | — | — | 0.840 |
| Recall | — | — | **1.000** |
| **F1 Score** | — | — | **0.913** |

The ensemble combines IsolationForest + Autoencoder + Z-score voting,
achieving perfect recall (no missed anomalies) at an acceptable precision.

---

## Key Observations

1. **Waiting-time reduction is dramatic (98 %)** — the RL agent virtually
   eliminates idle queuing vs the fixed-timing baseline.
2. **Queue lengths drop by 91 %**, indicating efficient green-phase allocation.
3. **Throughput trades off modestly (−15 %)** — the reward function weights
   delay more heavily than raw vehicle count.
4. **LSTM R² of 0.61** is reasonable for first-principles simulated data;
   real-world sensor data with richer features should improve this.
5. **Anomaly F1 of 0.91 with perfect recall** makes the detector suitable
   for safety-critical alerting where misses are unacceptable.

---

## Hardware Utilisation

| Component | Specification | Notes |
|-----------|---------------|-------|
| CPU | AMD Ryzen 5 5600H (6C/12T) | Used for SB3 training |
| GPU | NVIDIA RTX 2050, 4.3 GB VRAM, CUDA 12.4 | PyTorch GPU training |
| RAM | 16 GB | Sufficient for all workloads |
| Training (50K steps, DQN) | ~3 min (GPU) | Quick-train mode |
| LSTM Training (50 epochs) | ~2 min | CPU-based |

---

*Benchmarks from actual evaluation runs on ASUS VivoBook 15 Pro,
Windows 11, Python 3.13.7, PyTorch 2.6.0+cu124.*
