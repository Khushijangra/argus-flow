# END-TO-END EXECUTION AUDIT REPORT

## 1. RUNTIME LOGS
```text
[PHASE 1 (Video)] Loaded uploaded_1776265305.mp4
[PHASE 1 (Video)] FPS: 50.0, Total Frames: 600.0
[PHASE 1 (Video)] Window Generated: 16 frames of shape (720, 1280, 3)
[PHASE 2 (VideoMAE)] VideoMAEFeatureExtractor initialized successfully.
[PHASE 2 (VideoMAE)] Embeddings generated, shape: (1, 768)
[PHASE 3 (Stream-A)] best_clip.pt loaded.
[PHASE 3 (Stream-A)] FAILED: Stream-A Scoring Failed | Exception: ValueError: X has 16 features, but GaussianMixture is expecting 768 features as input.
[PHASE 4 (Inference Server)] FAILED: Inference Server Endpoint Failed | Exception: RuntimeError: Server returned 503: {"detail":"Model not loaded"}
[PHASE 5 (Hybrid State)] HybridState built successfully.
[PHASE 5 (Hybrid State)] State: {
  "$schema": "nexus-hybrid-state-v1",
  "intersection_id": "J0_0",
  "timestamp_ms": 1781949497670,
  "traffic": {
    "north": {
      "queue_length": 10,
      "wait_time_s": 20,
      "occupancy_pct": 50.0,
      "speed_kmh": 30.0,
      "arrival_rate": 0.027777777777777776
    },
    "south": {
      "queue_length": 10,
      "wait_time_s": 20,
      "occupancy_pct": 50.0,
      "speed_kmh": 30.0,
      "arrival_rate": 0.027777777777777776
    },
    "east": {
      "queue_length": 10,
      "wait_time_s": 20,
      "occupancy_pct": 50.0,
      "speed_kmh": 30.0,
      "arrival_rate": 0.027777777777777776
    },
    "west": {
      "queue_length": 10,
      "wait_time_s": 20,
      "occupancy_pct": 50.0,
      "speed_kmh": 30.0,
      "arrival_rate": 0.027777777777777776
    }
  },
  "signals": {
    "current_phase": "NS_GREEN",
    "phase_index": 0,
    "elapsed_s": 0.0,
    "pedestrian_request_active": false
  },
  "anomalies": [
    {
      "lane": "north",
      "severity": 0.85
    }
  ],
  "environment": {
    "emergency_active": false,
    "weather": {
      "rainfall_mm_h": 0.0,
      "visibility_m": 1000.0
    }
  },
  "network_topology": {
    "neighbors": {
      "north": null,
      "south": null,
      "east": null,
      "west": null
    }
  }
}
[PHASE 6 (RL Observation)] Observation vector generated. Shape: (28,)
[PHASE 6 (RL Observation)] Anomaly index 4 (North lane anomaly): 0.8500000238418579
[PHASE 6 (RL Observation)] Full Vector: [0.33333334 0.11111111 0.5        0.02777778 0.85       0.33333334
 0.11111111 0.5        0.02777778 0.         0.33333334 0.11111111
 0.5        0.02777778 0.         0.33333334 0.11111111 0.5
 0.02777778 0.         1.         0.         0.         0.
 0.         0.41548228 0.         0.        ]
[PHASE 7 (PPO)] PPO Inference successful. Selected Action: 2
[PHASE 8 (SUMO)] SUMO stepped successfully.
[PHASE 8 (SUMO)] Previous Phase: EW_through -> New Phase: EW_through
[PHASE 9 (Digital Twin)] Websocket payload built successfully.
[PHASE 9 (Digital Twin)] {
  "tick": 1,
  "junction_id": "J0_0",
  "lat": 37.824,
  "lon": -122.231,
  "traffic": {
    "queue": {},
    "wait": {}
  },
  "anomalies": {
    "north": 0.85
  },
  "signals": "NS_GREEN",
  "neighbors": []
}
[PHASE 11 (Failure Testing)] Stream-A Fallback tested. Returned severity: 0.0 (Expected 0.0)
[PHASE 11 (Failure Testing)] RL Fallback tested. Heuristic returned action: 0
```

## 2. LATENCY AUDIT
```text
PHASE 1 (Video): 142.03 ms
PHASE 2 (VideoMAE): 46761.13 ms
PHASE 3 (Stream-A): 282.17 ms
PHASE 4 (Inference Server): 702.55 ms
PHASE 5 (Hybrid State): 3.14 ms
PHASE 6 (RL Observation): 0.47 ms
PHASE 7 (PPO): 9743.69 ms
PHASE 8 (SUMO): 1.81 ms
PHASE 9 (Digital Twin): 0.06 ms
PHASE 11 (Failure Testing): 2075.05 ms
```

## 3. ACTUAL FAILURES ENCOUNTERED

- [PHASE 3 (Stream-A)] FAILED: Stream-A Scoring Failed | Exception: ValueError: X has 16 features, but GaussianMixture is expecting 768 features as input.
- [PHASE 4 (Inference Server)] FAILED: Inference Server Endpoint Failed | Exception: RuntimeError: Server returned 503: {"detail":"Model not loaded"}


## 4. ACTUAL INTEGRATION GAPS FOUND

- Integration Gap in PHASE 3 (Stream-A): Stream-A Scoring Failed
- Integration Gap in PHASE 4 (Inference Server): Inference Server Endpoint Failed


## 5. EXACT FILES REQUIRING MODIFICATION

- scripts/inference_server.py