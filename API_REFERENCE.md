# NEXUS-ATMS API Reference

The communication between the Video Input layer, the RL runtime, and the Digital Twin is managed by the following API contracts.

## Stream-A Inference Service (REST)

**Base URL**: `http://stream-a:8000`

### `POST /process_video`
Ingests a video file, extracts frames, passes them through the VideoMAE backbone, and scores anomaly severity via MULDE.

**Payload:**
```json
{
  "video_path": "data/videos/ua_detrac_accident.mp4",
  "camera_id": "North_Cam_Piedmont"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "anomaly_score": 3.42,
  "severity": 0.83,
  "camera_id": "North_Cam_Piedmont",
  "timestamp": "2026-06-20T14:00:00Z"
}
```

## Hybrid Runtime Event Bus (WebSocket)

**Base URL**: `ws://runtime:8001/ws`

The Runtime Orchestrator acts as a WebSocket server, emitting real-time intersection states to connected Digital Twin frontends.

### Subscription

Clients connect and immediately begin receiving JSON payloads at the conclusion of every SUMO `simulationStep()`.

**Payload Format:**
```json
{
  "type": "intersection_update",
  "data": {
    "J1_North": {
      "active_phase": 2,
      "anomaly_severity": 0.83,
      "queue_lengths": [12.0, 3.0, 0.0, 1.0],
      "wait_times": [45.0, 10.0, 0.0, 5.0]
    },
    "J2_South": {
      "active_phase": 0,
      "anomaly_severity": 0.0,
      "queue_lengths": [2.0, 1.0, 1.0, 0.0],
      "wait_times": [5.0, 2.0, 3.0, 0.0]
    }
  },
  "global_metrics": {
    "throughput": 4120,
    "crashes": 0
  }
}
```

The frontend maps `data.[JID].anomaly_severity` to visual alert markers on the dashboard map, and renders the current traffic light state based on `active_phase`.
