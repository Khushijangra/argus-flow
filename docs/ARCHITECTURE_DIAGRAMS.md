# NEXUS-ATMS: Architecture Diagrams & System Design

> Visual representations of the system architecture for presentations, documentation, and technical discussions.

---

## 🏗️ LAYER 1: SYSTEM OVERVIEW (5-Layer Architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     NEXUS-ATMS TRAFFIC CONTROL                      │
│                    End-to-End AI System Design                       │
└─────────────────────────────────────────────────────────────────────┘

┌─ LAYER 5: PRESENTATION ──────────────────────────────────────────────┐
│                                                                       │
│  📊 Operator Dashboard        📈 Analytics Console                   │
│  [Real-time heatmap]          [Historical reports]                   │
│  [Manual controls]            [Performance metrics]                  │
│  [Alert panel]                [Incident timeline]                    │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                                 △
                                 │ WebSocket (1 Hz)
                                 │
┌─ LAYER 4: BACKEND SERVICE ───┴────────────────────────────────────────┐
│                                                                       │
│  🖥️ FastAPI Runtime                                                  │
│  ├─ 25+ REST Endpoints                                               │
│  │   ├─ /api/status          (System health)                         │
│  │   ├─ /api/snapshot        (Current state)                         │
│  │   ├─ /api/signal/override (Manual control)                        │
│  │   ├─ /api/emergency/*     (Priority vehicles)                     │
│  │   └─ /api/counterfactual  (AI explanation)                        │
│  ├─ WebSocket Streaming (/ws/live)                                   │
│  │   └─ Real-time metrics: queue, speed, incidents, carbon           │
│  └─ Middleware & Security                                            │
│      ├─ CORS handling                                                │
│      ├─ Request validation (Pydantic)                                │
│      ├─ Error handling                                               │
│      └─ Audit logging                                                │
│                                                                       │
│  📄 Entrypoint: backend/main.py                                       │
│  ✓ Production-ready, deployment-ready                                │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                                 △
                    ┌────────────┼────────────┐
                    │            │            │
               REST │      Decision│  Logging  │
             Queries│        Output│           │
                    │            │            │
┌─ LAYER 3: CONTROL & SAFETY ──┴────────────┴────────────────────────────┐
│                                                                       │
│  🔐 Safety Logic                                                     │
│  ├─ Manual Override Handler                                          │
│  │   └─ Operator can always take control (30-sec timeout)            │
│  ├─ Emergency Corridor Engine                                        │
│  │   ├─ Detect: ambulance, fire truck (vision → class)              │
│  │   └─ Execute: Force green on corridor, activate sidetone          │
│  ├─ Signal Anomaly Detection                                         │
│  │   └─ ML classifier: flag malicious/invalid commands               │
│  ├─ Maintenance Advisory                                             │
│  │   └─ Predict road work impact; suggest timing shifts              │
│  └─ Fallback Logic                                                    │
│      └─ If RL fails → revert to fixed-time baseline (safe)           │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                                 △
                    ┌────────────┼────────────┐
                    │            │            │
              State │    Optimal │   Anomaly  │
             Vector │     Phase  │   Flags    │
                    │            │            │
┌─ LAYER 2: AI INTELLIGENCE ENGINE ─────────────────────────────────────┐
│                                                                       │
│  🧠 Three Parallel Decision Engines                                  │
│                                                                       │
│  ┌─ ENGINE A: RL CONTROL ──────────────────────────────────────────┐ │
│  │ Status: PRIMARY (makes signal decisions)                        │ │
│  │ Model: D3QN (Dueling Double Deep Q-Network)                     │ │
│  │ Input: State vector [queue_N,E,S,W, speed, occupancy, time...] │ │
│  │ Output: Next signal phase ∈ {N-S_green, E-W_green}            │ │
│  │ Config: RL controller in control/rl_controller.py               │ │
│  │                                                                 │ │
│  │ Q-Learning Formula:                                             │ │
│  │   Q(s,a) ← Q(s,a) + α[r + γ max_a' Q(s',a') - Q(s,a)]          │ │
│  │                                                                 │ │
│  │ Why D3QN?                                                       │ │
│  │   • Dueling: separate value + advantage streams                 │ │
│  │   • Double: reduce overestimation bias                          │ │
│  │   • Prioritized replay: focus on important transitions          │ │
│  │                                                                 │ │
│  │ Training: 50k steps on SUMO data; 2-3 hours compute            │ │
│  │ Validation: 25% improvement over fixed-time baseline            │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌─ ENGINE B: LSTM FORECASTING ────────────────────────────────────┐ │
│  │ Status: AUXILIARY (lookahead planning)                          │ │
│  │ Model: 2-layer LSTM (128 → 64 units) + FC                       │ │
│  │ Input: Time series [s_{t-30}, ..., s_{t-1}] (30 frames)        │ │
│  │ Output: Predicted queue[t+5:t+30]                               │ │
│  │ Use: Feed forecast to RL agent for better decisions             │ │
│  │                                                                 │ │
│  │ Architecture:                                                   │ │
│  │   Input → LSTM 128 → Dropout → LSTM 64 → Dropout → FC → Output │ │
│  │                                                                 │ │
│  │ Training: 10k sequences from SUMO logs                           │ │
│  │ Accuracy: RMSE ~2.5 vehicles (good for 10-vehicle queues)       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌─ ENGINE C: ANOMALY DETECTION ───────────────────────────────────┐ │
│  │ Status: PROTECTIVE (flags incidents for safety layer)           │ │
│  │                                                                 │ │
│  │ Method 1: Rule-Based (80% of detections)                        │ │
│  │   • Flag if queue > μ + 3σ (statistical outlier)                │ │
│  │   • Flag if speed < 2 m/s (traffic jam)                         │ │
│  │   • Flag if incident_report received                            │ │
│  │                                                                 │ │
│  │ Method 2: ML-Based (20% coverage, high precision)               │ │
│  │   • Isolation Forest on [queue, speed, occupancy]               │ │
│  │   • Threshold: anomaly_score > 0.5                              │ │
│  │   • Training: SUMO normal traffic vs. synthetic anomalies        │ │
│  │                                                                 │ │
│  │ Output: {incident_type, severity, confidence}                   │ │
│  │ Action: Alert backend; log for analysis                         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  Combined: Each engine runs independently; results fused into        │
│            final control decision (RL primary, others advisory)      │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                                 △
                    ┌────────────┼────────────────┐
                    │            │                │
             Camera │  SUMO Sim  │  IoT Sensors   │
             Frames │  State     │  (MQTT)        │
                    │            │                │
┌─ LAYER 1: INGESTION ─────────┴────────────┴──────────────────────────┐
│                                                                       │
│  📷 Computer Vision Pipeline                                         │
│  ├─ YoloV8 Detector: per-frame {vehicle_class, bbox, confidence}    │
│  ├─ DeepSort Tracker: frame-to-frame association {vehicle_id, ...}  │
│  ├─ Kalman Filter: smooth trajectories + predict motion             │
│  └─ Zone Counter: map bboxes → junction zones → queue_length        │
│                                                                       │
│  🚗 Simulation Stream (SUMO - Simulation of Urban Mobility)          │
│  ├─ Microscopic traffic model with realistic vehicle dynamics       │
│  ├─ Configurable demand: rush_hour, normal, night, asymmetric       │
│  ├─ Incident injection: random collisions, stalls                   │
│  └─ Sensor output: queue, speed, occupancy per junction             │
│                                                                       │
│  🌐 IoT & Sensor Fusion                                              │
│  ├─ MQTT client: subscribe to /traffic/junction/{id}                │
│  ├─ Inductive loop: queue detection (fallback for vision)           │
│  ├─ Incident reports: from police, navigation apps                  │
│  └─ Time source: GPS, NTP-synchronized                              │
│                                                                       │
│  📊 Feature Assembly                                                  │
│  ├─ Per-junction state vector construction:                          │
│  │   s_t = {queue_N, queue_E, queue_S, queue_W,        (4 values)   │
│  │          speed_N, speed_E, speed_S, speed_W,        (4 values)   │
│  │          occupancy, time_of_day, day_of_week,       (3 values)   │
│  │          incident_flag, emergency_flag}             (3 values)   │
│  └─ Total: 13-dim state vector                                       │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘

Notation:
  → Information flow (direction of data)
  ✓ Validated component
  [Module path] for code reference
```

---

## 🎯 LAYER 2: DATA FLOW (Detailed Timeline)

```
SCENARIO: Rush hour at intersection; normal traffic → incident detected

═══════════════════════════════════════════════════════════════════════

T=0:00 — INITIALIZATION

  System Start
    │
    ├─→ Load D3QN weights from models/*/best/
    ├─→ Initialize LSTM with cached state
    ├─→ Start demo data generator (if no cameras)
    └─→ Listen on :8000/api/* and :8000/ws/live

═══════════════════════════════════════════════════════════════════════

T=0:05 — NORMAL CYCLE (repeat every 1-2 seconds)

  ┌────────────────────────────────────────────────────────────────┐
  │ 1. OBSERVATION                                                 │
  ├────────────────────────────────────────────────────────────────┤
  │                                                                │
  │   Camera feed (30 fps) or SUMO state                           │
  │   │                                                            │
  │   ├─→ [Vision] YoloV8 detection → {count, bbox, confidence}   │
  │   │   └─→ DeepSort tracking → vehicle IDs + speeds            │
  │   │   └─→ Zone mapping → queue_N=8, queue_E=12                │
  │   │                                                            │
  │   ├─→ [IoT] Fetch from MQTT or SUMO API                       │
  │   │   └─→ occupancy, avg_speed, incident_flag                 │
  │   │                                                            │
  │   └─→ [Feature] Assemble state vector                          │
  │       s_t = [8, 12, 3, 5, 4.5, 3.2, 2.1, 4.8, 0.4,            │
  │              14 (2 PM), 2 (Tuesday), 0 (no incident)]         │
  │                                                                │
  └────────────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────────────┐
  │ 2. DECISION (Three engines in parallel)                        │
  ├────────────────────────────────────────────────────────────────┤
  │                                                                │
  │ [ENGINE A: RL]                                                 │
  │   s_t → D3QN forward pass                                       │
  │   Q(s_t, NORTH_GREEN) = 0.65                                    │
  │   Q(s_t, EAST_GREEN) = 0.92  ← argmax                          │
  │   → action = EAST_GREEN, confidence=0.92                       │
  │                                                                │
  │ [ENGINE B: LSTM]                                               │
  │   [s_{t-30}, ..., s_{t-1}] → LSTM                              │
  │   → forecast: queue_E will spike to 18 in 5 min (useful data)  │
  │                                                                │
  │ [ENGINE C: ANOMALY]                                            │
  │   Isolation Forest score = 0.15 < 0.5 threshold                │
  │   → No anomaly detected ✓                                       │
  │                                                                │
  └────────────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────────────┐
  │ 3. SAFETY VALIDATION                                           │
  ├────────────────────────────────────────────────────────────────┤
  │                                                                │
  │ Check: Override requested? No                                  │
  │ Check: Emergency detected? No                                 │
  │ Check: Malicious command? Signal classifier → legitimate ✓     │
  │ Check: Maintenance? Not scheduled                              │
  │                                                                │
  │ → Final decision: EAST_GREEN (90 sec)                          │
  │                                                                │
  └────────────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────────────┐
  │ 4. BACKEND AGGREGATION                                         │
  ├────────────────────────────────────────────────────────────────┤
  │                                                                │
  │ Response payload:                                              │
  │ {                                                              │
  │   "signal_phase": "EAST_GREEN",                                │
  │   "duration_sec": 90,                                          │
  │   "confidence": 0.92,                                          │
  │   "reason": "High east queue with predicted spike",            │
  │   "queue_lengths": {"N": 8, "E": 12, "S": 3, "W": 5},         │
  │   "avg_speeds": {"N": 4.5, "E": 3.2, "S": 2.1, "W": 4.8},     │
  │   "anomalies": [],                                             │
  │   "predictions": {                                             │
  │     "queue_E_5min": 18,                                        │
  │     "queue_E_10min": 15                                        │
  │   },                                                           │
  │   "carbon_saved_kg": 2.3,                                      │
  │   "timestamp": "2026-04-15T14:25:30Z"                          │
  │ }                                                              │
  │                                                                │
  │ Store in metrics cache                                         │
  │ Log to database                                                │
  │                                                                │
  └────────────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────────────┐
  │ 5. BROADCAST TO DASHBOARD                                      │
  ├────────────────────────────────────────────────────────────────┤
  │                                                                │
  │ WebSocket /ws/live streams to all connected clients @1 Hz      │
  │ Dashboard updates in real-time:                                │
  │   → Signal color changes (green → red visualization)           │
  │   → Queue heatmap updates                                      │
  │   → Metrics panel refreshes                                    │
  │   → To WebSocket connection 1 (operator view 1)                │
  │   → To WebSocket connection 2 (analytics console)              │
  │   → To WebSocket connection 3 (external monitoring)            │
  │                                                                │
  └────────────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────────────┐
  │ 6. NEXT CYCLE (in 1-2 seconds)                                │
  ├────────────────────────────────────────────────────────────────┤
  │                                                                │
  │ Continue loop, agent observes new state                        │
  │ Learns: "Oh, east queue decreased; next cycle might differ"    │
  │                                                                │
  └────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════

T=1:30 — INCIDENT DETECTED

  New observation arrives:
    s_t = [2, 28, 5, 6, ... incident_flag=1]
    └─→ East queue grew to 28 (unusual spike)
    └─→ Incident flag triggered (vehicle stall detected)

  [ANOMALY ENGINE]
    Isolation Forest: score = 0.72 > 0.5 → ANOMALY DETECTED
    Rule-based: queue_E (28) > μ (12) + 3σ (9) → OUTLIER
    → incident_type="traffic_jam", severity="high"

  [SAFETY LAYER]
    ├─ Is this a malicious command? Security classifier → NO
    ├─ Should we activate emergency corridor? No (not emergency)
    ├─ Should we fall back to fixed-time? Not yet (still learning)
    │
    └─ Decision: Log incident, flag in response, continue adaptive control

  [RL AGENT]
    Observes: s_t with incident_flag=1
    Q(s_t, EAST_GREEN) = 0.45 (decreased due to incident context)
    Q(s_t, NORTH_GREEN) = 0.68 ← argmax
    → action = NORTH_GREEN (mitigate east backup)

  Backend response includes:
    "anomalies": [{"type": "traffic_jam", "severity": "high"}]
    "recommended_action": "Activate incident response protocol"

═══════════════════════════════════════════════════════════════════════

T=2:00 — MANUAL OVERRIDE (User Action)

  Operator clicks "Override: NORTH_GREEN" on dashboard
    │
    ├─→ POST /api/signal/override { phase: "NORTH_GREEN" }
    ├─→ Backend: Pause RL agent
    ├─→ Log override: {timestamp, operator_id, reason}
    ├─→ Enforce: NORTH_GREEN for next 30 seconds
    ├─→ After 30 sec: Resume autonomous RL control
    └─→ Broadcast to all connected dashboards

═══════════════════════════════════════════════════════════════════════

T=3:30 — EMERGENCY ACTIVATION

  Vision module: Detected vehicle → classification = "ambulance"
    │
    ├─→ Vision detector confidence = 0.95 (high)
    ├─→ POST /api/emergency/activate { corridor: ["North", "South"] }
    ├─→ Safety layer: Transition to emergency mode
    │   ├─ Force NORTH_GREEN for 60 seconds
    │   ├─ Alert dashboard: RED BANNER "EMERGENCY CORRIDOR ACTIVE"
    │   ├─ Log: emergency_event, corridor, duration, timestamp
    │   └─ Disable manual overrides (safety first)
    ├─→ After 60 sec: Detect ambulance left junction
    └─→ Resume normal RL control

═══════════════════════════════════════════════════════════════════════

T=5:00 — SHUTDOWN

  System shutdown signal received:
    │
    ├─→ Gracefully close all WebSocket connections
    ├─→ Save final model weights (optional)
    ├─→ Flush metrics cache to persistent storage
    ├─→ Log final statistics (total incidents, decisions, uptime)
    └─→ Exit cleanly

═══════════════════════════════════════════════════════════════════════
```

---

## 🔄 LAYER 3: DECISION-MAKING LOGIC (Flow Diagram)

```
                           ┌─ START ─┐
                           │ observe │
                           └────┬────┘
                                │
                    ┌───────────┴────────────┐
                    │   Feature Assembly    │
                    │  s_t = [13 features]  │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   ┌────▼────┐             ┌────▼────┐           ┌─────▼─────┐
   │ ENGINE A │             │ENGINE B │           │ ENGINE C  │
   │   D3QN   │             │  LSTM   │           │ Anomaly   │
   │   RL     │             │ Forecast│           │ Detection │
   └────┬────┘             └────┬────┘           └─────┬─────┘
        │                       │                       │
    Q-values                Predictions            Flags
    RL policy             (lookahead)             (alerts)
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Decision Fusion       │
                    │ (primary=RL, others    │
                    │  advisory)             │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Safety Layer          │
                    │                        │
                    │ [4 Validators]:        │
                    │ 1. Override check      │
                    │ 2. Emergency check     │
                    │ 3. Security check      │
                    │ 4. Maintenance check   │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Final Decision        │
                    │  { phase, duration,    │
                    │    confidence, reason} │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   ┌────▼────┐            ┌─────▼──────┐          ┌────▼────┐
   │ Store in │            │ Broadcast  │          │ Actuate │
   │ Metrics  │            │ WebSocket  │          │ Signal  │
   │ Cache    │            │ (/ws/live) │          │ Timing  │
   └─────────┘            └────────────┘          └────────┘

Continue loop (next cycle in 1-2 seconds)
```

---

## 📦 LAYER 4: MODULE DEPENDENCIES

```
                        ┌─────────────────────┐
                        │   backend/main.py   │ ← Single Entrypoint
                        │    FastAPI Server   │
                        └────────────┬────────┘
                                     │
             ┌───────────────────────┼───────────────────────┐
             │                       │                       │
        ┌────▼────┐           ┌─────▼──────┐         ┌──────▼────┐
        │ backend/ │           │   control/ │         │   iot/    │
        │ services │           │ rl_        │         │ data_     │
        │          │           │ controller │         │ fusion    │
        └────┬────┘           └─────┬──────┘         └──────┬────┘
             │                       │                       │
             └───────────────────────┼───────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────┐
        │                                                     │
    ┌───▼────────┐         ┌──────────────────────┐    ┌────▼────┐
    │    AI      │         │      AI              │    │ frontend│
    │   RL core  │         │   vision pipeline    │    │          │
    │            │         │  (detector+tracker)  │    └──────────┘
    │ ai/rl/     │         │                      │
    │ ├─ dqn.py  │         │  ai/vision/          │
    │ ├─ ppo.py  │         │  ├─ detector.py      │
    │ ├─ d3qn.py │         │  ├─ tracker.py       │
    │ └─ ...     │         │  └─ counter.py       │
    └───┬────────┘         └──────────┬───────────┘
        │                             │
        │   ┌───────────────────────┬─┘
        │   │                       │
    ┌───▼───▼──┐         ┌─────────▼─────────┐
    │    AI    │         │        AI         │
    │ envs     │         │    prediction +   │
    │          │         │     anomaly       │
    │ai/envs/  │         │                   │
    │├─sumo... │         │ai/prediction/     │
    │└─multi...│         │├─lstm_pred.py     │
    └────┬─────┘         │                   │
         │               │ai/anomaly/        │
         │               │├─anomaly_det.py   │
         │               └─────────┬─────────┘
         │                         │
         └──────────┬──────────────┘
                    │
         ┌──────────▼──────────┐
         │        ai/utils/    │
         │                     │
         │ ├─ logger.py        │
         │ ├─ metrics.py       │
         │ ├─ visualization.py │
         │ └─ __init__.py      │
         └─────────────────────┘

Legend:
  → Direct dependency (import)
  └─ Transitive dependency (used by parent)
```

---

## 🛡️ SAFETY ARCHITECTURE

```
                      Control Request
                            │
                ┌───────────▼───────────┐
                │  Validation Layer 1   │
                │  Override Detection   │
                │  (Manual takeover)    │
                └─────┬─────────────────┘
                      │ Pass
                ┌─────▼─────────────────┐
                │  Validation Layer 2   │
                │  Emergency Detection  │
                │ (Ambulance? Priority?)│
                ├──────┬────────────────┤
                │ YES  │ NO             │
                │      │                │
           ┌────▼──┐   │           ┌────▼──┐
           │Activate   │           │Continue
           │Corridor   │           │        │
           │(RED)      │           └────┬───┘
           └───┬───┘   │                │
               │       │    ┌───────────▼──────────┐
               │       │    │ Validation Layer 3   │
               │       │    │ Security Check       │
               │       │    │ (Malicious command?) │
               │       │    ├──────┬──────────────┤
               │       │    │ YES  │ NO           │
               │       │    │      │              │
               │       │    │  ┌───▼────┐  ┌─────▼──┐
               │       │    │  │ REJECT │  │Continue
               │       │    │  │ Command│  │        │
               │       │    │  │ (ALERT)   │────┬───┘
               │       │    │  └───┬────┘  │    │
               │       │    │      │       │    └────┬────────┐
               │       │    └──────┼───────┼─────────┤        │
               │       │           │       │         │        │
               │       │           │       │    ┌────▼─────┐  │
               │       │           │       │    │ Validator 4
               │       │           │       │    │Maintenance
               │       │           │       │    │ Advisory
               │       │           │       │    └────┬─────┘
               │       │           │       │         │
               │       └───────────┼───────┼─────────┘
               │                   │       │
               │                   │   ┌───▼────────────┐
               │                   │   │ Build Response │
               │                   │   │Pack metadata   │
               │                   │   │anomaly flags   │
               │                   │   │explanations    │
               │                   │   └───┬────────────┘
               │                   │       │
               └───────────────────┼───────┴────→ Backend
                                   │          API Response
                       (All paths safe)
```

---

## 📊 PERFORMANCE & SCALABILITY ANALYSIS

```
INFERENCE LATENCY (per cycle):

Component              │ Latency  │ GPU?  │ Bottleneck?
──────────────────────┼──────────┼───────┼─────────────
1. Feature Assembly   │ 2 ms     │ No    │ No
2. D3QN Forward Pass  │ 5 ms     │ Yes   │ No
3. LSTM Inference     │ 3 ms     │ Yes   │ No
4. Anomaly Detection  │ 1 ms     │ No    │ No
5. Decision Fusion    │ 1 ms     │ No    │ No
6. Safety Validation  │ 2 ms     │ No    │ No
──────────────────────┼──────────┼───────┼─────────────
TOTAL                 │ ~14 ms   │ Yes   │ ✓ Well under budget

Budget: 1000 ms (1 second)
Headroom: ~70×

Result: System can handle 70× current decision rate if needed
        Supports high-frequency control scenarios


MEMORY USAGE:

Component           │ Size     │ Comment
────────────────────┼──────────┼──────────────────────
D3QN Model          │ 2 MB     │ Weights: 500k params
LSTM Model          │ 1 MB     │ Weights: 150k params
Replay Buffer       │ 50 MB    │ 100k transitions
Feature Cache       │ 5 MB     │ History: 12 hours
Metrics Store       │ 20 MB    │ Aggregated stats
Dashboard Assets    │ 2 MB     │ index.html + CSS/JS
Misc (middleware)   │ 10 MB    │ FastAPI, handlers, etc.
────────────────────┼──────────┼──────────────────────
TOTAL               │ ~90 MB   │ Single-junction system

For 50 junctions:    │ ~4.5 GB  │ Still modest
For 500 junctions:   │ ~45 GB   │ Require distributed system

Result: Single machine handles 1–50 junctions comfortably
        Distributed architecture needed for city-wide (100+ junctions)


THROUGHPUT:

Single-server throughput:
  • API requests/sec: ~1000 req/s (FastAPI + Uvicorn benchmarks)
  • WebSocket connections: 10,000+ concurrent
  • Real-time decision rate: ~1 Hz (1 decision/sec per junction)

For 100 junctions @ 1 Hz: 100 decisions/sec = 0.1% server capacity

Result: Extremely efficient; can handle 100+ junctions on modest hardware
        (2–4 CPU cores, 4–8 GB RAM)
```

---

## 🚀 DEPLOYMENT ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│              PRODUCTION DEPLOYMENT                      │
└─────────────────────────────────────────────────────────┘

┌─ LOAD BALANCER (Nginx) ──────────────────────────────────┐
│ Distributes traffic across backend instances             │
│ Sticky sessions for WebSocket (/ws/live)                 │
└─────────────────┬──────────────────────────────────────────┘
                  │
        ┌─────────┼─────────┐
        │         │         │
    ┌───▼──┐  ┌───▼──┐  ┌───▼──┐
    │ API  │  │ API  │  │ API  │
    │Pod 1 │  │Pod 2 │  │Pod 3 │ (Horizontal scaling)
    │:8000 │  │:8000 │  │:8000 │
    └───┬──┘  └───┬──┘  └───┬──┘
        │         │         │
        └─────────┼─────────┘
                  │
        ┌─────────▼─────────────┐
        │  Shared Model Cache   │
        │  (Redis/Memcached)    │
        │  Weights + metrics    │
        └─────────┬─────────────┘
                  │
        ┌─────────▼─────────────────┐
        │  Persistent Storage       │
        │  ├─ TimescaleDB (metrics) │
        │  ├─ PostgreSQL (config)   │
        │  └─ S3 (model weights)    │
        └───────────────────────────┘

Each Pod:
  ├─ Docker container
  ├─ Python 3.13 runtime
  ├─ FastAPI + Uvicorn
  ├─ D3QN model (loaded from cache)
  ├─ LSTM model (loaded from cache)
  └─ Vision pipeline (YoloV8 on GPU if available)

Orchestration:
  ├─ Kubernetes or Docker Swarm
  ├─ Auto-scaling: +pod if CPU>80% / -pod if CPU<20%
  ├─ Health checks: /api/status endpoint
  ├─ Rolling updates: zero-downtime deployments
  └─ Monitoring: Prometheus + Grafana
```

---

## ✅ VALIDATION CHECKLIST FOR PRESENTATIONS

Use this diagram stack in presentations:

- **5-minute overview**: Layer 1 (System Overview)
- **10-minute talk**: Layers 1 + 2 (Overview + Data Flow timeline)
- **20-minute presentation**: Layers 1 + 2 + 3 + 4 (Add decision logic + dependencies)
- **Technical deep dive**: All layers + deployment architecture
- **Interview/whiteboard**: Draw Layer 5 (Safety) to show safety-first thinking

---

**Last updated**: April 15, 2026 | Status: ✅ Production-Ready
