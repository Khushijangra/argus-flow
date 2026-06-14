import time
from typing import Dict, Any, Optional
import backend.dependencies as deps

def _congestion_from_density(density: float) -> str:
    if density < 0.33:
        return "low"
    if density < 0.66:
        return "medium"
    return "high"



def _phase_from_lane(lane: Optional[str]) -> str:
    if lane in ("north", "south"):
        return "NS_GREEN"
    if lane in ("east", "west"):
        return "EW_GREEN"
    return "ALL_RED"



def _active_lane_from_phase(phase: str) -> str:
    if phase == "NS_GREEN":
        return "north_south"
    if phase == "EW_GREEN":
        return "east_west"
    if phase == "YELLOW":
        return "transition"
    return "all_stop"



def _camera_direction_from_phase(phase: str) -> str:
    if phase == "EW_GREEN":
        return "east"
    if phase == "NS_GREEN":
        return "north"
    if phase == "YELLOW":
        return "north"
    return "north"



def _normalize_phase_name(phase: str) -> str:
    p = str(phase or "").strip().upper().replace("-", "_")
    if p.startswith("NS"):
        return "NS_GREEN" if "GREEN" in p else "YELLOW"
    if p.startswith("EW"):
        return "EW_GREEN" if "GREEN" in p else "YELLOW"
    if p in {"YELLOW", "ALL_RED", "ALLRED"}:
        return "ALL_RED" if p in {"ALL_RED", "ALLRED"} else "YELLOW"
    return "NS_GREEN"



def _lane_distribution_from_snapshot(vehicle_count: int, lane_waiting: Dict[str, Any]) -> Dict[str, int]:
    lane_waiting = lane_waiting or {}
    vals = {
        "north": max(0.0, float(lane_waiting.get("north", 0.0) or 0.0)),
        "south": max(0.0, float(lane_waiting.get("south", 0.0) or 0.0)),
        "east": max(0.0, float(lane_waiting.get("east", 0.0) or 0.0)),
        "west": max(0.0, float(lane_waiting.get("west", 0.0) or 0.0)),
    }
    total = sum(vals.values())
    if total <= 0:
        q = max(0, int(vehicle_count))
        split = q // 4
        rem = q - 4 * split
        return {
            "north": split + (1 if rem > 0 else 0),
            "south": split + (1 if rem > 1 else 0),
            "east": split + (1 if rem > 2 else 0),
            "west": split,
        }
    return {
        "north": int(round(vehicle_count * vals["north"] / total)),
        "south": int(round(vehicle_count * vals["south"] / total)),
        "east": int(round(vehicle_count * vals["east"] / total)),
        "west": int(round(vehicle_count * vals["west"] / total)),
    }



def _apply_traffic_snapshot_to_junctions(traffic: Dict[str, Any]) -> None:
    if not isinstance(traffic, dict):
        return
    junctions = traffic.get("junctions", {})
    if not isinstance(junctions, dict) or not junctions:
        return

    for jid, js in junctions.items():
        if jid not in deps._junction_states or not isinstance(js, dict):
            continue
        st = deps._junction_states[jid]
        vehicle_count = int(js.get("vehicle_count", st.get("vehicle_count", 0)) or 0)
        queue_length = float(js.get("queue_length", st.get("queue_length", vehicle_count)) or 0.0)
        waiting_time = float(js.get("waiting_time", js.get("avg_waiting_time", st.get("wait_time", 0.0))) or 0.0)
        density = min(1.0, max(0.0, float(js.get("density", queue_length / 30.0))))
        lane_dist = _lane_distribution_from_snapshot(vehicle_count, js.get("lane_waiting", {}))
        phase = _normalize_phase_name(js.get("phase", st.get("phase", "NS_GREEN")))

        st["vehicle_count"] = max(0, vehicle_count)
        st["queue_length"] = round(max(0.0, queue_length), 2)
        st["wait_time"] = round(max(0.0, waiting_time), 2)
        st["avg_waiting_time"] = st["wait_time"]
        st["density"] = round(density, 3)
        st["congestion_level"] = str(js.get("congestion_level", _congestion_from_density(density)))
        st["lane_distribution"] = lane_dist
        st["queue_n"] = int(lane_dist.get("north", 0))
        st["queue_s"] = int(lane_dist.get("south", 0))
        st["queue_e"] = int(lane_dist.get("east", 0))
        st["queue_w"] = int(lane_dist.get("west", 0))
        st["signal_state"] = phase
        st["phase"] = phase
        st["active_lane"] = _active_lane_from_phase(phase)
        st["camera_direction"] = _camera_direction_from_phase(phase)
        st["ai_reason"] = st.get("ai_reason") or "Telemetry synced from active snapshot"
        hm = st.get("health_metrics") if isinstance(st.get("health_metrics"), dict) else {}
        hm["detection_count"] = max(0, vehicle_count)
        st["health_metrics"] = hm

    _refresh_phase_countdowns()



def _apply_phase_to_junction(jid: str, phase: str, source: str, duration_s: int = 20) -> None:
    if jid not in deps._junction_states:
        return
    deps._junction_states[jid]["phase"] = phase
    deps._junction_states[jid]["signal_state"] = phase
    deps._junction_states[jid]["active_lane"] = _active_lane_from_phase(phase)
    deps._junction_states[jid]["camera_direction"] = _camera_direction_from_phase(phase)
    deps._junction_states[jid]["phase_remaining"] = max(1, int(duration_s))
    deps._junction_states[jid]["phase_expires_at"] = time.time() + max(1, int(duration_s))
    deps._junction_states[jid]["last_source"] = source



def _refresh_phase_countdowns() -> None:
    now = time.time()
    for st in deps._junction_states.values():
        expires = float(st.get("phase_expires_at", now + 1))
        st["phase_remaining"] = max(0, int(expires - now))





class LiveRuntime:
    """Connect vision, IoT, prediction, anomaly, and RL into one live tick."""

    def __init__(self) -> None:
        self.enabled = LIVE_MODE and not DEMO_MODE
        self.real_data_only = os.getenv("REAL_DATA_ONLY", "true").lower() == "true"
        self.mode = os.getenv("RUN_MODE", "real").strip().lower()
        if self.mode not in ("real", "demo"):
            self.mode = "real"
        self.intersection_id = os.getenv("PRIMARY_INTERSECTION", "J1_1")
        self.video_source = os.getenv("TRAFFIC_VIDEO_SOURCE", "0")
        self.vision_backend = os.getenv("VISION_BACKEND", "yolo")
        self.vision_device = os.getenv("VISION_DEVICE", "cpu")
        self.vision_conf = max(0.25, min(0.4, float(os.getenv("VISION_CONF", "0.35"))))
        self.resize_width = int(os.getenv("VISION_RESIZE_W", "640"))
        self.resize_height = int(os.getenv("VISION_RESIZE_H", "480"))
        self.debug_cv = os.getenv("DEBUG_CV", "false").lower() == "true"
        fail_fast_env = os.getenv("FAIL_FAST_VIDEO")
        if fail_fast_env is None:
            fail_fast_env = os.getenv("FAIL_ON_MISSING_VIDEO", "false")
        self.fail_fast_video = str(fail_fast_env).lower() not in {"0", "false", "no", "off"}
        self.video_init_retries = max(1, int(os.getenv("VIDEO_INIT_RETRIES", "5")))
        self.black_frame_mean_threshold = float(os.getenv("BLACK_FRAME_MEAN_THRESHOLD", "5.0"))
        self.health = "healthy"
        self._lock = asyncio.Lock()
        self._tick = 0

        self.cap = None
        self.detector = None
        self.tracker = None
        self.counter = None
        self.speed = None
        self.incident = None

        self.sensor_sim = None
        self.sensor_fusion = None
        self.mqtt = None

        self.lstm = None
        self.ml_anomaly = None
        self.rl = None
        self.graph_coordinator = None
        self.graph_runtime_enabled = os.getenv("GRAPH_RUNTIME_ENABLED", "false").lower() == "true"

        self.latest_traffic: Dict = {}
        self.latest_incidents: List[Dict] = []
        self.latest_anomaly: Optional[Dict] = None
        self.latest_prediction: Optional[List[float]] = None
        self.latest_frame_jpeg: Optional[bytes] = None
        self.last_error: str = ""
        self.frame_ok = False
        self._last_open_attempt = 0.0
        self._is_file_source = False
        self.startup_validation_error: str = ""
        self.fallback_triggered = False
        self.fallback_reason = ""
        self.latest_markers: List[Dict] = []
        self.latest_heatmap: List[List[float]] = []
        self.latest_roads: List[Dict] = []
        self.latest_cv_summary: Dict = {}
        self.latest_frame_stats: Dict = {}

        self.frame_count = 0
        self.frame_drop_count = 0
        self.reconnect_attempts = 0
        self.consecutive_zero_frames = 0
        self.max_zero_frames_warn = int(os.getenv("ZERO_FRAMES_WARN", "10"))
        self._density_history = collections.deque(maxlen=12)
        self._lane_history = collections.deque(maxlen=12)
        self._tick_ms = collections.deque(maxlen=300)
        self._ws_delay_ms = collections.deque(maxlen=300)

        # CPU-first mapping config around a real city center.
        center_lat = float(os.getenv("MAP_CENTER_LAT", "28.6139"))
        center_lon = float(os.getenv("MAP_CENTER_LON", "77.2090"))
        self.map_center = {"lat": center_lat, "lon": center_lon}
        self._geo_mapper = None
        if RoadGeoMapper:
            self._geo_mapper = RoadGeoMapper(
                city_center_lat=center_lat,
                city_center_lon=center_lon,
                frame_width=int(os.getenv("MAP_FRAME_WIDTH", str(self.resize_width))),
                frame_height=int(os.getenv("MAP_FRAME_HEIGHT", str(self.resize_height))),
                span_lat=float(os.getenv("MAP_SPAN_LAT", "0.012")),
                span_lon=float(os.getenv("MAP_SPAN_LON", "0.016")),
            )

        if not self.enabled:
            return

        # Vision stack
        if VehicleDetector and VehicleTracker and ZoneCounter and SpeedEstimator and IncidentDetector:
            self.detector = VehicleDetector(
                backend=self.vision_backend,
                conf_threshold=self.vision_conf,
                device=self.vision_device,
            )
            self.tracker = VehicleTracker()
            self.counter = ZoneCounter(frame_shape=(self.resize_height, self.resize_width))
            self.speed = SpeedEstimator(fps=float(os.getenv("VISION_FPS", "25")))
            self.incident = IncidentDetector()

            self._open_video_source()

        # IoT stack
        if SensorFusion:
            self.sensor_fusion = SensorFusion()

        sim_fallback = os.getenv("ENABLE_SIMULATION_FALLBACK", "false").lower() == "true"
        if sim_fallback and not self.real_data_only and SensorSimulator and self.sensor_fusion:
            self.sensor_sim = SensorSimulator(
                intersection_ids=[self.intersection_id],
                real_time=False,
                sim_step_s=float(os.getenv("IOT_STEP_SECONDS", "5")),
            )

        if MQTTClient:
            self.mqtt = MQTTClient(
                broker_host=os.getenv("MQTT_HOST", "localhost"),
                broker_port=int(os.getenv("MQTT_PORT", "1883")),
            )

        # Prediction + anomaly
        if LSTMPredictor:
            try:
                self.lstm = LSTMPredictor(
                    device=os.getenv("LSTM_DEVICE", "cpu"),
                    model_path=os.getenv("LSTM_MODEL_PATH", "models/lstm_live.pt"),
                )
            except Exception as exc:
                logger.warning("[LiveRuntime] LSTM init failed (%s). Using no-predict mode.", exc)
                self.lstm = None
        if MLAnomalyDetector:
            self.ml_anomaly = MLAnomalyDetector(device=os.getenv("ANOMALY_DEVICE", "cpu"))
            try:
                self.ml_anomaly.load(ANOMALY_MODEL_DIR)
            except Exception:
                logger.info("[LiveRuntime] ML anomaly models not loaded yet.")

        # RL controller for live phase recommendation
        if RLController:
            self.rl = RLController(
                intersection_id=self.intersection_id,
                device=os.getenv("RL_DEVICE", "cpu"),
            )

        if self.graph_runtime_enabled and MultiAgentCoordinator:
            try:
                coord_ids = [f"J{r}_{c}" for r in range(4) for c in range(4)]
                self.graph_coordinator = MultiAgentCoordinator(
                    intersection_ids=coord_ids,
                    graph_enabled=True,
                    graph_debug=os.getenv("GRAPH_DEBUG", "false").lower() == "true",
                    safety_shield_enabled=os.getenv("GRAPH_SAFETY_SHIELD", "true").lower() == "true",
                    min_action_hold_steps=int(os.getenv("GRAPH_MIN_HOLD_STEPS", "2")),
                    device=os.getenv("RL_DEVICE", "cpu"),
                )
            except Exception as exc:
                logger.warning("[LiveRuntime] graph coordinator init failed: %s", exc)
                self.graph_coordinator = None

    async def tick(self) -> Dict:
        async with self._lock:
            tick_t0 = time.perf_counter()
            self._tick += 1

            snapshot = None
            if self.sensor_sim and self.sensor_fusion:
                readings = self.sensor_sim.tick()
                if self.mqtt:
                    for rd in readings:
                        self.mqtt.publish_reading(rd)
                fused = self.sensor_fusion.ingest(readings)
                snapshot = fused.get(self.intersection_id)

            # Auto-reconnect video source in case camera/file is temporarily unavailable.
            if (
                self.detector
                and (self.cap is None or not self.cap.isOpened())
                and (time.time() - self._last_open_attempt) > 3.0
            ):
                self._open_video_source()

            # Vision updates (if a real frame is available)
            real_detections = []
            if self.cap and self.detector and self.tracker and self.counter and self.speed and self.incident:
                ok, frame = self.cap.read()
                self.frame_count += 1
                self.frame_ok = bool(ok)
                if not ok or frame is None:
                    self.frame_drop_count += 1
                    self.health = "degraded"
                    self._recover_stream_end()
                if ok and frame is not None:
                    frame = self._resize_frame(frame)
                    det = self.detector.detect(frame)
                    conf_scores = [round(float(d.confidence), 3) for d in det]
                    _log_event(
                        "cv",
                        "frame_detections",
                        frame_index=self._tick,
                        detections=len(det),
                        confidences=conf_scores[:20],
                    )
                    tracked = self.tracker.update(det)
                    zone_stats = self.counter.update(tracked)
                    track_speeds = self.speed.estimate(self.tracker.active_tracks())
                    frame_view = self.detector.draw(frame, tracked if tracked else det) if self.debug_cv else frame
                    self.latest_frame_jpeg = self._encode_jpeg(frame_view)
                    real_detections = tracked if tracked else det

                    vehicle_count = len(real_detections)
                    if vehicle_count == 0:
                        self.consecutive_zero_frames += 1
                        if self.consecutive_zero_frames > self.max_zero_frames_warn:
                            self.health = "degraded"
                            _log_event(
                                "cv",
                                "zero_detection_warning",
                                consecutive_zero_frames=self.consecutive_zero_frames,
                                threshold=self.max_zero_frames_warn,
                            )
                    else:
                        self.consecutive_zero_frames = 0

                    self.latest_frame_stats = {
                        "frame": self._tick,
                        "vehicle_count": vehicle_count,
                        "detections": [
                            {
                                "id": int(getattr(d, "track_id", -1)),
                                "label": str(getattr(d, "label", "vehicle")),
                                "confidence": round(float(getattr(d, "confidence", 0.0)), 3),
                                "bbox": list(getattr(d, "bbox", (0, 0, 0, 0))),
                            }
                            for d in real_detections[:80]
                        ],
                    }

                    incidents = self.incident.update(
                        {k: v["queue"] for k, v in zone_stats.items()},
                        track_speeds,
                    )
                    self.latest_incidents = [
                        {
                            "id": i.incident_id,
                            "type": i.incident_type,
                            "severity": i.severity,
                            "zone": i.zone,
                            "description": i.description,
                        }
                        for i in incidents
                    ]

                    if self.sensor_fusion:
                        avg_speed = float(np.mean(list(track_speeds.values()))) if track_speeds else 0.0
                        for ap in ("north", "south", "east", "west"):
                            q = int(zone_stats.get(ap, {}).get("queue", 0))
                            self.sensor_fusion.ingest_vision(self.intersection_id, ap, q, avg_speed)
                        snapshot = self.sensor_fusion.snapshot(self.intersection_id)

            # Build map telemetry from real detections only.
            self._update_map_telemetry(real_detections)

            # In strict real-data mode, do not retain snapshots when camera has no frame.
            if self.real_data_only and not self.frame_ok:
                snapshot = None

            traffic = self._to_traffic_snapshot(snapshot)
            self.latest_traffic = traffic

            # LSTM online prediction
            if self.lstm and snapshot is not None:
                try:
                    self.lstm.add_observation(snapshot)
                    pred = self.lstm.predict()
                    if pred is not None:
                        self.latest_prediction = pred[0].astype(float).tolist()
                except Exception as exc:
                    self.last_error = f"lstm: {exc}"

            # ML anomaly from fused feature vector
            if self.ml_anomaly and snapshot is not None:
                try:
                    vec = self._to_anomaly_vector(snapshot)
                    self.ml_anomaly.add_observation(vec)
                    if not getattr(self.ml_anomaly, "_fitted", False) and self._tick % 120 == 0:
                        self.ml_anomaly.fit(ae_epochs=6)
                    alert = self.ml_anomaly.detect(vec) if getattr(self.ml_anomaly, "_fitted", False) else None
                    if alert:
                        self.latest_anomaly = {
                            "severity": alert.severity,
                            "score": float(alert.anomaly_score),
                            "detectors": alert.detectors_fired,
                            "message": alert.message,
                        }
                except Exception as exc:
                    self.last_error = f"anomaly: {exc}"

            # RL decision from current observation
            if self.rl and snapshot is not None:
                try:
                    obs = snapshot.to_feature_vector()
                    action = self.rl.predict(obs)
                    phase = self._action_to_phase(action)
                    if self.intersection_id in deps._junction_states:
                        deps._junction_states[self.intersection_id]["phase"] = phase
                        deps._junction_states[self.intersection_id]["ai_confidence"] = 0.92
                except Exception as exc:
                    self.last_error = f"rl: {exc}"

            # Optional graph-coordinated inference over all junctions.
            if self.graph_coordinator and deps._junction_states:
                try:
                    graph_snapshots: Dict[str, Dict[str, Any]] = {}
                    for jid, st in deps._junction_states.items():
                        graph_snapshots[jid] = {
                            "queue_length": float(st.get("queue_n", 0) + st.get("queue_s", 0) + st.get("queue_e", 0) + st.get("queue_w", 0)),
                            "waiting_time": float(st.get("wait_time", 0.0)),
                            "current_phase": float(0 if st.get("phase") == "NS_GREEN" else 1),
                            "phase_time": float(st.get("phase_remaining", 0)),
                            "predicted_inflow": float(st.get("vehicle_count", 0.0)),
                            "emergency_flag": bool(st.get("is_corridor", False)),
                            "occupancy": float(st.get("density", 0.0)),
                        }

                    graph_actions = self.graph_coordinator.step(graph_snapshots)
                    for jid, act in graph_actions.items():
                        phase = self._action_to_phase(int(act))
                        _apply_phase_to_junction(jid, phase, source="ai_graph", duration_s=15)
                    _log_event("graph", "coordinator_tick", active=True, junctions=len(graph_actions))
                except Exception as exc:
                    _log_event("graph", "coordinator_fallback", active=False, error=str(exc))

            tick_ms = (time.perf_counter() - tick_t0) * 1000.0
            self._tick_ms.append(tick_ms)

            return traffic

    @staticmethod
    def _encode_jpeg(frame) -> Optional[bytes]:
        cv2 = _optional_cv2()
        if cv2 is None:
            return None
        try:
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok:
                return None
            return buf.tobytes()
        except Exception:
            return None

    def _activate_demo_fallback(self, reason: str) -> None:
        """Disable live runtime and switch to demo mode after repeated camera failures."""
        self.fallback_triggered = True
        self.fallback_reason = reason
        self.enabled = False
        self.health = "degraded"
        self.last_error = reason
        _ensure_demo_mode(reason)

    def _open_video_source(self) -> None:
        self._last_open_attempt = time.time()
        self.reconnect_attempts += 1
        self.startup_validation_error = ""
        try:
            cv2 = _optional_cv2()
            if cv2 is None:
                self.startup_validation_error = "OpenCV unavailable"
                self._activate_demo_fallback(self.startup_validation_error)
                return

            source = int(self.video_source) if str(self.video_source).isdigit() else self.video_source
            self._is_file_source = isinstance(source, str) and os.path.isfile(source)

            last_error = "Video source unavailable"
            for attempt in range(1, self.video_init_retries + 1):
                cap = cv2.VideoCapture(source)
                if not (cap and cap.isOpened()):
                    last_error = "Video source unavailable"
                    logger.warning(
                        "[LiveRuntime] Video source unavailable on attempt %d/%d: %s",
                        attempt,
                        self.video_init_retries,
                        self.video_source,
                    )
                    if cap:
                        cap.release()
                    continue

                ok, first = cap.read()
                if not ok or first is None:
                    last_error = "Video source opened but first frame is invalid"
                    _log_event("video", "first_frame_invalid", source=self.video_source, attempt=attempt)
                    logger.warning(
                        "[LiveRuntime] First frame invalid on attempt %d/%d",
                        attempt,
                        self.video_init_retries,
                    )
                    cap.release()
                    continue

                first = self._resize_frame(first)
                frame_mean = float(np.mean(first))
                _log_event(
                    "video",
                    "first_frame",
                    source=self.video_source,
                    shape=list(first.shape),
                    mean_pixel=round(frame_mean, 2),
                    attempt=attempt,
                )

                if frame_mean <= self.black_frame_mean_threshold:
                    last_error = f"First frame appears black (mean={frame_mean:.2f})"
                    _log_event(
                        "video",
                        "first_frame_black",
                        source=self.video_source,
                        mean=round(frame_mean, 2),
                        attempt=attempt,
                    )
                    logger.warning(
                        "[LiveRuntime] Black first frame on attempt %d/%d (mean=%.2f)",
                        attempt,
                        self.video_init_retries,
                        frame_mean,
                    )
                    if not self._is_file_source:
                        self.cap = cap
                        self.frame_ok = True
                        logger.warning("[LiveRuntime] Accepting dark webcam warm-up frame and staying in live mode")
                        return
                    cap.release()
                    continue

                self.cap = cap
                self.frame_ok = True
                if self._is_file_source:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                logger.info("[LiveRuntime] Video source connected: %s", self.video_source)
                return

            self.cap = None
            self.frame_ok = False
            self.startup_validation_error = last_error
            logger.error("[LiveRuntime] Camera init failed after %d attempts: %s", self.video_init_retries, last_error)

            # Always prefer fallback over startup failure.
            self._activate_demo_fallback(last_error)
            if self.fail_fast_video:
                logger.error("[LiveRuntime] FAIL_FAST_VIDEO=true is set, but fallback is enforced to keep server up.")

        except Exception as exc:
            self.last_error = f"video init: {exc}"
            self.frame_ok = False
            self.startup_validation_error = self.last_error
            logger.exception("[LiveRuntime] Video init exception")
            self._activate_demo_fallback(self.last_error)

    def _recover_stream_end(self) -> None:
        if not self.cap:
            return
        try:
            cv2 = _optional_cv2()
            if cv2 is None:
                self._activate_demo_fallback("OpenCV unavailable")
                return

            if self._is_file_source:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, _ = self.cap.read()
                if ok:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.frame_ok = True
                    _log_event("video", "loop_restart", source=self.video_source)
                    return
            self._open_video_source()
        except Exception as exc:
            self.last_error = f"video recover: {exc}"

    def _resize_frame(self, frame):
        try:
            cv2 = _optional_cv2()
            if cv2 is None:
                return frame

            return cv2.resize(frame, (self.resize_width, self.resize_height))
        except Exception:
            return frame

    def _inject_demo_markers(self) -> List[Dict]:
        # Minimal synthetic traffic when demo mode is enabled and CV is empty.
        n = random.randint(5, 15)
        markers: List[Dict] = []
        heat: List[List[float]] = []
        lane_counts = {"north": 0, "south": 0, "east": 0, "west": 0}
        for i in range(n):
            lat = self.map_center["lat"] + random.uniform(-0.0035, 0.0035)
            lon = self.map_center["lon"] + random.uniform(-0.0045, 0.0045)
            lane = random.choice(list(lane_counts.keys()))
            lane_counts[lane] += 1
            conf = round(random.uniform(0.55, 0.92), 3)
            markers.append(
                {
                    "id": 10000 + i,
                    "lat": lat,
                    "lon": lon,
                    "lane": lane,
                    "label": "demo_vehicle",
                    "confidence": conf,
                    "fallback": True,
                }
            )
            heat.append([lat, lon, min(1.0, 0.45 + conf * 0.55)])

        self.latest_heatmap = heat
        self.latest_roads = self._roads_from_lane_counts(lane_counts)
        self.latest_cv_summary = {
            "vehicle_count": n,
            "density": round(min(1.0, n / 25.0), 3),
            "congestion_level": "medium",
            "per_lane": lane_counts,
            "mode": "synthetic_fallback",
            "degraded": True,
        }
        return markers

    def _update_map_telemetry(self, detections: List) -> None:
        markers: List[Dict] = []
        heatmap: List[List[float]] = []
        lane_counts: Dict[str, int] = {"north": 0, "south": 0, "east": 0, "west": 0}

        if not self._geo_mapper or not detections:
            if self.mode == "demo":
                self.latest_markers = self._inject_demo_markers()
                _log_event("cv", "fallback_traffic_injected", mode=self.mode, markers=len(self.latest_markers))
                return
            self.latest_markers = []
            self.latest_heatmap = []
            self.latest_roads = self._roads_from_lane_counts(lane_counts)
            self.latest_cv_summary = {
                "vehicle_count": 0,
                "density": 0.0,
                "congestion_level": "low",
                "per_lane": lane_counts,
                "mode": "real_cv",
                "degraded": True,
            }
            return

        for d in detections:
            center = getattr(d, "center", None)
            track_id = int(getattr(d, "track_id", -1))
            label = str(getattr(d, "label", "vehicle"))
            conf = float(getattr(d, "confidence", 0.0))

            if not center:
                bbox = getattr(d, "bbox", None)
                if bbox and len(bbox) == 4:
                    center = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
                else:
                    continue

            lat, lon = self._geo_mapper.map_pixel(center[0], center[1])
            lane = self._geo_mapper.lane_name(center[0])
            lane_counts[lane] += 1
            markers.append({
                "id": track_id,
                "lat": lat,
                "lon": lon,
                "lane": lane,
                "label": label,
                "confidence": conf,
            })
            heatmap.append([lat, lon, min(1.0, 0.35 + conf * 0.65)])

        self._lane_history.append(lane_counts.copy())
        smooth_lane = {k: 0 for k in lane_counts}
        if self._lane_history:
            for lane in smooth_lane:
                smooth_lane[lane] = int(round(np.mean([h[lane] for h in self._lane_history])))

        roads = self._roads_from_lane_counts(lane_counts)
        area = float(max(1, self.resize_width * self.resize_height))
        density_raw = min(1.0, (len(markers) / area) * 120000.0)
        self._density_history.append(density_raw)
        density = float(np.mean(self._density_history)) if self._density_history else density_raw
        if density < 0.33:
            cong = "low"
        elif density < 0.66:
            cong = "medium"
        else:
            cong = "high"

        degraded = all(v == 0 for v in smooth_lane.values())
        self.health = "degraded" if degraded or self.consecutive_zero_frames > self.max_zero_frames_warn else "healthy"

        self.latest_markers = markers
        self.latest_heatmap = heatmap
        self.latest_roads = roads
        self.latest_cv_summary = {
            "vehicle_count": len(markers),
            "density": round(density, 3),
            "congestion_level": cong,
            "per_lane": smooth_lane,
            "mode": "real_cv",
            "degraded": degraded,
        }

    def _roads_from_lane_counts(self, lane_counts: Dict[str, int]) -> List[Dict]:
        if self._geo_mapper:
            roads = self._geo_mapper.summarize_roads(lane_counts)
            out = []
            for r in roads:
                out.append({
                    "road_id": r.road_id,
                    "vehicle_count": r.vehicle_count,
                    "density": round(float(r.density), 3),
                    "congestion": r.congestion,
                })
            return out
        return []

    def map_payload(self) -> Dict:
        c = self.map_center
        return {
            "center": c,
            "markers": self.latest_markers,
            "heatmap": self.latest_heatmap,
            "roads": self.latest_roads,
            "cv": self.latest_cv_summary,
        }

    def status(self) -> Dict:
        frame_drop_rate = (self.frame_drop_count / self.frame_count) if self.frame_count else 0.0

        def _stats(values: collections.deque) -> Dict[str, float]:
            if not values:
                return {"min": 0.0, "avg": 0.0, "max": 0.0}
            arr = list(values)
            return {
                "min": round(float(min(arr)), 2),
                "avg": round(float(np.mean(arr)), 2),
                "max": round(float(max(arr)), 2),
            }

        return {
            "enabled": self.enabled,
            "real_data_only": self.real_data_only,
            "mode": self.mode,
            "frame_ok": self.frame_ok,
            "video_source": self.video_source,
            "vision_backend": self.vision_backend,
            "vision_device": self.vision_device,
            "vision_conf": self.vision_conf,
            "resize": {"width": self.resize_width, "height": self.resize_height},
            "intersection_id": self.intersection_id,
            "has_traffic": bool(self.latest_traffic),
            "has_prediction": self.latest_prediction is not None,
            "has_anomaly": self.latest_anomaly is not None,
            "vehicle_markers": len(self.latest_markers),
            "frame_count": self.frame_count,
            "frame_drop_count": self.frame_drop_count,
            "frame_drop_rate": round(frame_drop_rate, 4),
            "reconnect_attempts": self.reconnect_attempts,
            "consecutive_zero_frames": self.consecutive_zero_frames,
            "fps": round(float(getattr(self.detector, "fps", 0.0)), 2) if self.detector else 0.0,
            "latency_ms": _stats(self._tick_ms),
            "ws_delay_ms": _stats(self._ws_delay_ms),
            "system_health": self.health,
            "latest_frame_stats": self.latest_frame_stats,
            "last_error": self.last_error,
        }

    def note_ws_delay(self, delay_ms: float) -> None:
        self._ws_delay_ms.append(float(delay_ms))

    def _to_traffic_snapshot(self, snap) -> Dict:
        if snap is None:
            return {
                "tick": self._tick,
                "hour": time.localtime().tm_hour,
                "mode": "live",
                "queues": {"north": 0.0, "south": 0.0, "east": 0.0, "west": 0.0},
                "waiting_times": {"north": 0.0, "south": 0.0, "east": 0.0, "west": 0.0},
                "total_queue": 0.0,
                "avg_waiting_time": 0.0,
                "throughput": 0.0,
                "phase": deps._junction_states.get(self.intersection_id, {}).get("phase", "NS_GREEN"),
                "time_factor": 1.0,
            }

        queues = {}
        waits = {}
        throughput = 0.0
        for ap in ("north", "south", "east", "west"):
            st = snap.approaches.get(ap)
            q = float(st.queue_length if st else 0.0)
            queues[ap] = q
            waits[ap] = float(q * 3.0)
            throughput += float(st.flow_veh_h if st else 0.0)

        return {
            "tick": self._tick,
            "hour": time.localtime().tm_hour,
            "mode": "live",
            "queues": queues,
            "waiting_times": waits,
            "total_queue": float(sum(queues.values())),
            "avg_waiting_time": float(sum(waits.values()) / 4.0),
            "throughput": float(throughput),
            "phase": deps._junction_states.get(self.intersection_id, {}).get("phase", "NS_GREEN"),
            "time_factor": 1.0,
            "rainfall": float(snap.rainfall_mm_h),
            "visibility_m": float(snap.visibility_m),
            "aqi": float(snap.aqi),
        }

    @staticmethod
    def _action_to_phase(action: int) -> str:
        if action in (0, 1):
            return "NS_GREEN" if action == 0 else "EW_GREEN"
        if action == 2:
            return "YELLOW"
        return "ALL_RED"

    @staticmethod
    def _to_anomaly_vector(snap) -> np.ndarray:
        def _apv(ap: str, key: str, default: float = 0.0) -> float:
            st = snap.approaches.get(ap)
            return float(getattr(st, key, default) if st else default)

        hour = time.localtime().tm_hour + time.localtime().tm_min / 60.0
        return np.array([
            _apv("north", "vehicle_count"), _apv("south", "vehicle_count"),
            _apv("east", "vehicle_count"), _apv("west", "vehicle_count"),
            _apv("north", "speed_kmh"), _apv("south", "speed_kmh"),
            _apv("east", "speed_kmh"), _apv("west", "speed_kmh"),
            _apv("north", "queue_length"), _apv("south", "queue_length"),
            _apv("east", "queue_length"), _apv("west", "queue_length"),
            float(np.mean([_apv("north", "occupancy_pct"), _apv("south", "occupancy_pct"), _apv("east", "occupancy_pct"), _apv("west", "occupancy_pct") ])),
            float(np.sin(2 * np.pi * hour / 24.0)),
            float(np.cos(2 * np.pi * hour / 24.0)),
        ], dtype=np.float32)


live_runtime = LiveRuntime()



