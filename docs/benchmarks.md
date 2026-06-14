# NEXUS-ATMS Benchmarks and Evaluation

This document outlines the rigorous evaluation methodology and the verified benchmark results for the NEXUS-ATMS predictive models and Reinforcement Learning (RL) agents.

---

## Evaluation Setup

Evaluations were conducted natively within the **Eclipse SUMO** (Simulation of Urban MObility) environment to ensure micro-simulation accuracy of vehicle kinematics and queuing behaviors.

- **Environment**: Multi-junction grid map featuring dynamic insertion flows.
- **Traffic Scenarios**: Tested under varying demand distributions (e.g., peak rush hour, irregular incident bursts).
- **Multi-Seed Evaluation**: To account for the inherent stochasticity of Reinforcement Learning exploration and SUMO routing models, the primary D3QN agent was evaluated across multiple distinct random seeds. Results are aggregated to ensure statistical significance and to rule out anomalous "lucky" policy runs.

*(Evaluation scripts utilized: `scripts/evaluate_multiseed_gate.py` and `scripts/benchmark_d3qn_suite.py`)*

---

## Verified Results

The following metrics have been verified through simulated scenario benchmarks against a standard fixed-time pre-timed signal baseline.

### 1. D3QN Traffic Signal Optimization Performance

| Metric | Baseline (Fixed Time) | NEXUS-ATMS (D3QN) | Improvement |
|--------|-----------------------|-------------------|-------------|
| **Average Waiting Time** | 571.1 s | **10.2 s** | **98.2% Reduction** |
| **Multi-seed Stability** | N/A | **9.96 ± 0.24 s** | N/A |

### 2. Anomaly Detection Performance

The anomaly detection module operates as an ensemble classifier monitoring time-series traffic density metrics.

| Metric | Score |
|--------|-------|
| **F1 Score** | 0.913 |
| **Recall** | 1.000 |

---

## Interpretation

- **98.2% Reduction in Wait Time**: The massive improvement from the baseline (571.1s to 10.2s) highlights the inefficiency of strict, unresponsive fixed-time signals during asymmetric or heavily congested scenarios. The D3QN agent successfully learns to clear approaching queues before they gridlock the junction.
- **9.96 ± 0.24 s Stability**: The tight standard deviation across multiple random seeds proves the D3QN agent's learned policy is generalized and robust, not heavily reliant on a specific random initialization.
- **Anomaly Detection (Recall = 1.000)**: A perfect recall score guarantees that the system did not miss any simulated incident or blockage events. Prioritizing recall over precision is intentional; in traffic management, missing an accident (False Negative) carries a significantly higher cost than a brief, harmless False Positive investigation.

---

## Limitations

- **Simulation Dependence**: While Eclipse SUMO provides industry-standard kinematics, all currently verified metrics are strictly simulated. Real-world physical deployments introduce computer vision occlusion, adverse weather limitations, and sensor latency that are not fully captured in the simulator.
- **Dataset Limitations**: The anomaly detection model is trained on synthetic SUMO injection anomalies. It has not been benchmarked against real-world dashcam anomaly datasets.
- **Need for Field Validation**: These results confirm algorithmic soundness and software reliability. Validating the 98.2% reduction metric in a physical deployment requires pilot testing at a controlled intersection.

---

## Future Evaluation

The following experimental evaluations are planned but currently **unverified**:

- **Graph RL**: Benchmarking spatial Graph Neural Networks (GNNs) to improve multi-junction coordination over independent D3QN agents.
- **Digital Twins**: Integrating CARLA for high-fidelity, photo-realistic visual validation.
- **Federated Learning**: Simulating multi-city decentralized model training to measure privacy-preserving data efficiency against centralized models.
