# REALITY GAP REPORT
## Anomaly-Integrated System (Repo B) Pipeline Audit

This report maps the intended architectural pipeline of the Traffic Incident Intelligence System against the actual, runtime-verified code execution.

**Assessment Criteria:**
- **ACTIVE**: Fully implemented and connected to live runtime.
- **PARTIAL**: Code exists and runs, but uses shortcuts or skips full logic.
- **DISCONNECTED**: Code exists and is fully implemented, but is never imported/executed in the main runtime loop.
- **MOCKED**: Hardcoded or simulated logic standing in for actual implementation.
- **MISSING**: Code does not exist in the repository.

---

### Pipeline Stage 1: Video Feed
*   **Intended Action**: Frontend UI captures video/webcam and streams frames to the backend.
*   **Exists**: Yes (`AIVisionPanel.tsx`).
*   **Imported**: Yes.
*   **Executed**: Yes (in browser).
*   **Output Produced**: Visual rendering in HTML `<video>`.
*   **Output Consumed**: No. The bytes are not sent over HTTP/WS to the backend.
*   **Status**: **MOCKED**
*   **Completeness Score**: 20% (UI exists, transmission missing).

### Pipeline Stage 2: Frame Buffer
*   **Intended Action**: Backend receives frames, queues them, and batches them for VideoMAE.
*   **Exists**: Yes (`backend/services/video_service.py` has stub methods).
*   **Imported**: Yes (in `main.py`).
*   **Executed**: No. Endpoint never receives video stream data.
*   **Output Produced**: None.
*   **Output Consumed**: None.
*   **Status**: **DISCONNECTED**
*   **Completeness Score**: 10% (Placeholder file exists).

### Pipeline Stage 3: VideoMAE Backbone
*   **Intended Action**: Process batched frames through transformer to extract spatial-temporal features.
*   **Exists**: Yes (`argus_stream_extracted/.../videomae.py`).
*   **Imported**: No. The `hybrid_runtime.py` does not import this class.
*   **Executed**: No.
*   **Output Produced**: None (during live run).
*   **Output Consumed**: None.
*   **Status**: **DISCONNECTED**
*   **Completeness Score**: 90% (Model code is production-ready, but orchestration is 0%).

### Pipeline Stage 4: 768-D Embeddings
*   **Intended Action**: VideoMAE outputs high-dimensional embeddings for the anomaly scorer.
*   **Exists**: Yes (Feature extraction script logic).
*   **Imported**: No.
*   **Executed**: No.
*   **Output Produced**: None.
*   **Output Consumed**: None.
*   **Status**: **DISCONNECTED**
*   **Completeness Score**: 100% offline, 0% runtime.

### Pipeline Stage 5: Stream-A (MULDE)
*   **Intended Action**: Multi-scale density estimation computes anomaly probabilities.
*   **Exists**: Yes (`argus_stream_extracted/.../mulde.py`).
*   **Imported**: No.
*   **Executed**: No.
*   **Output Produced**: None.
*   **Output Consumed**: None.
*   **Status**: **DISCONNECTED**
*   **Completeness Score**: 90% (Algorithms are rigorous but orphaned).

### Pipeline Stage 6: Raw Anomaly Score & Severity Normalization
*   **Intended Action**: CV logic converts distances into a normalized 0.0-1.0 severity metric.
*   **Exists**: Yes.
*   **Imported**: No (the real logic).
*   **Executed**: Yes (the fake logic).
*   **Output Produced**: `0.85` severity.
*   **Output Consumed**: Yes.
*   **Status**: **MOCKED**
*   **Completeness Score**: 10%. (The React `ScenarioStudio` blindly triggers a `/api/inject` endpoint with a hardcoded severity of `0.85`, skipping the entire CV pipeline).

### Pipeline Stage 7: Anomaly Event & HybridStateBuilder
*   **Intended Action**: Backend registers the incident and fuses CV state with traffic state.
*   **Exists**: Yes (`hybrid_runtime.py`).
*   **Imported**: Yes.
*   **Executed**: Yes.
*   **Output Produced**: `inject_anomaly()` modifies `self.env._anomaly_severity`.
*   **Output Consumed**: Yes.
*   **Status**: **PARTIAL**
*   **Completeness Score**: 50%. (It successfully alters the environment state, but relies on the mocked API trigger).

### Pipeline Stage 8: RLObservationMapper
*   **Intended Action**: Translates hybrid state into the 28D vector required by PPO.
*   **Exists**: Yes (`control/traffic_env.py` observation builder).
*   **Imported**: Yes.
*   **Executed**: Yes.
*   **Output Produced**: 28D `obs` array containing anomaly flags.
*   **Output Consumed**: Yes (by StableBaselines3).
*   **Status**: **ACTIVE**
*   **Completeness Score**: 100%.

### Pipeline Stage 9: PPO Policy
*   **Intended Action**: RL model selects optimal traffic phase based on congestion + anomaly state.
*   **Exists**: Yes (`best_model.zip`).
*   **Imported**: Yes.
*   **Executed**: Yes.
*   **Output Produced**: Phase integer.
*   **Output Consumed**: Yes.
*   **Status**: **ACTIVE**
*   **Completeness Score**: 100%.

### Pipeline Stage 10: SUMO / Traffic Simulator
*   **Intended Action**: Apply phase, update queues, output new junction state.
*   **Exists**: Yes (`TrafficEnvironment` queue math).
*   **Imported**: Yes.
*   **Executed**: Yes.
*   **Output Produced**: Queue lengths, wait times, throughput.
*   **Output Consumed**: Yes (by the WebSocket).
*   **Status**: **ACTIVE**
*   **Completeness Score**: 100% (for the math environment; though SUMO itself is disabled for the demo).

### Pipeline Stage 11: Digital Twin
*   **Intended Action**: Render exact vehicle positions reflecting the SUMO/RL queues.
*   **Exists**: Yes (`CanvasCityTwin.tsx`).
*   **Imported**: Yes.
*   **Executed**: Yes.
*   **Output Produced**: Canvas animation.
*   **Output Consumed**: Visual display only.
*   **Status**: **MOCKED**
*   **Completeness Score**: 10%. (Animation is a simple `requestAnimationFrame` loop completely decoupled from the RL output. It visually fakes congestion rather than reading `nexusState`).

---

## Final Architecture Conclusion

If the intended identity of **Repo B** is a platform where a **Video Feed directly drives an Anomaly Response RL Model**, the repository is currently failing its core objective.

**The "Reality Gap":**
The entire Computer Vision "brain" (`VideoMAE`, `MULDE`, `Stream-A`) is severed from the nervous system. The React frontend visually fakes the video processing and simply sends a "Play Accident Animation" trigger to the backend. The backend RL model genuinely works and manages queues, but its input is artificial. The visual output (Digital Twin) is also artificial.

Before we delete anything or formalize the repo split, the decision must be made:
Do we invest time bridging the **DISCONNECTED** Computer Vision models into `hybrid_runtime.py` to close the reality gap? Or do we accept the theatrical hackathon presentation as the final state of Repo B?
