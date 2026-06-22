# Commercial Demo Guide

This guide details how to execute the fully integrated NEXUS-ATMS commercial demonstration.

## Prerequisites
Ensure you have run the [Docker Clean-Machine Test](DEPLOYMENT.md) at least once so the images are built and cached.

## Execution Steps

**1. Launch the cluster**
Simply execute the provided automation script:
```bash
./run_demo.sh
```
This script handles the startup sequence and dynamically injects the UA-DETRAC video feed into the system.

**2. Open the Digital Twin**
Open a browser and navigate to the frontend:
```text
http://localhost:3000
```

## Visual Verification Checklist
During the presentation, ask stakeholders/investors to observe the following UI elements:

- [ ] **Baseline State:** Observe normal traffic flow and routine cyclic signal phase changes. Wait times should be low and anomaly indicators should be hidden/green.
- [ ] **Accident Injection:** At ~10 seconds into the script, `run_demo.sh` will `POST` the `ua_detrac_accident.mp4` video.
- [ ] **Severity Marker:** Watch the intersection UI marker turn Red, indicating a live Stream-A severity score > 0.8.
- [ ] **RL Decision Shift:** Notice that the Phase allocation immediately overrides its standard timing, shifting to clear the affected approach lane to avoid cascading congestion.
- [ ] **Dashboard Metrics:** Point out the live throughput and global congestion metrics automatically updating as the RL agent mitigates the anomaly impact.

## Capturing a Video Artifact
To prepare for asynchronous pitches, it is highly recommended to record the screen while walking through the checklist above. A 60-second clip demonstrating the exact moment the severity marker appears and the phase adjusts provides compelling proof of the system's end-to-end functionality.
