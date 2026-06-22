import asyncio
import os
import sys
import time
import requests
from collections import deque, defaultdict
import logging
from logging.handlers import RotatingFileHandler
import yaml
import uvicorn
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import json
import torch

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from control.traffic_env import TrafficEnvironment, IntersectionConfig, APPROACHES
from core.hybrid_state import HybridStateBuilder, RLObservationMapper
from backend.core.network_mapper import mapper
from backend.runtime.event_bus import event_bus
from backend.runtime.checkpoint_manager import CheckpointManager

# -----------------
# 1. OBSERVABILITY & PERSISTENCE
# -----------------
log_dir = os.path.join(PROJECT_ROOT, "data/runtime_logs")
os.makedirs(log_dir, exist_ok=True)

logger = logging.getLogger("HybridRuntime")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(os.path.join(log_dir, "runtime.log"), maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

metrics = {
    "anomaly_events_sec": 0.0,
    "stream_a_latency_ms": 0.0,
    "rl_inference_latency_ms": 0.0,
    "hybrid_update_latency_ms": 0.0,
    "sumo_tick_latency_ms": 0.0,
    "websocket_latency_ms": 0.0,
    "ticks": 0
}

# Digital Twin Rolling History
dt_history = deque(maxlen=1000)

app = FastAPI(title="Hybrid Runtime Metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/health")
def health():
    return {"status": "ok", "components": {"sumo": "ok", "stream_a": "ok", "rl": "ok"}}

@app.get("/metrics")
def get_metrics():
    return metrics

@app.get("/history/replay")
def get_history_replay(limit: int = 100):
    return list(dt_history)[-limit:]

# Global reference to inject manual anomalies from HTTP
manual_anomalies = {}

from pydantic import BaseModel
class InjectPayload(BaseModel):
    anomaly_severity: float

@app.post("/api/inject")
def inject_anomaly(payload: InjectPayload):
    manual_anomalies["North"] = payload.anomaly_severity
    return {"status": "injected", "severity": payload.anomaly_severity}

# -----------------
# HYBRID RUNTIME
# -----------------
class HybridRuntime:
    def __init__(self, config_path="config/runtime.yaml"):
        # 5. CONFIG VALIDATION
        config_full_path = os.path.join(PROJECT_ROOT, config_path)
        if not os.path.exists(config_full_path):
            raise FileNotFoundError(f"Config not found: {config_full_path}")
            
        with open(config_full_path, "r") as f:
            self.config = yaml.safe_load(f)
            
        self.sumo_cfg = os.path.join(PROJECT_ROOT, self.config["sumo"]["config_file"])
        if not os.path.exists(self.sumo_cfg):
            raise FileNotFoundError(f"SUMO network config not found: {self.sumo_cfg}")
            
        self.rl_enabled = self.config["rl"]["enabled"]
        self.stream_a_enabled = self.config["stream_a"]["enabled"]
        self.stream_a_endpoint = self.config["stream_a"]["endpoint"]
        self.window_size = self.config["stream_a"].get("window_size", 5)
        
        # 1. Initialize SUMO
        self._init_sumo()
        
        # 2. Initialize RL Controller via Checkpoint Manager
        if self.rl_enabled:
            ckpt_mgr = CheckpointManager(
                primary_path=os.path.join(PROJECT_ROOT, self.config["rl"]["checkpoint_path"]),
                fallback_path=None
            )
            try:
                self.rl_policy = ckpt_mgr.load_model()
            except Exception as e:
                logger.error(f"Failed to load RL model: {e}")
                self.rl_policy = None
        else:
            self.rl_policy = None
            
        # 3. Initialize NetworkMapper
        mapper_path = os.path.join(PROJECT_ROOT, "backend/core/network_mapper.json")
        if os.path.exists(mapper_path):
            mapper.load_from_file(mapper_path)
            
        self.anomaly_buffers = defaultdict(lambda: deque(maxlen=self.window_size))
        self.running = False
        self.tick_count = 0
        self.anomaly_count = 0

    def _init_sumo(self):
        try:
            env_config = IntersectionConfig()
            env_config.sumo_cfg = self.sumo_cfg
            env_config.use_gui = self.config["sumo"]["gui"]
            self.env = TrafficEnvironment(env_config)
            self.obs, self.info = self.env.reset()
            logger.info("SUMO Environment initialized.")
        except Exception as e:
            logger.error(f"SUMO Init Failed: {e}")
            raise e

    async def poll_stream_a(self, camera_id: str):
        # Override with manual anomaly if present
        approach = camera_id.replace("cam_", "")
        if approach in manual_anomalies and manual_anomalies[approach] > 0:
            score = manual_anomalies[approach]
            # decay manual anomaly slightly over time to allow recovery
            manual_anomalies[approach] = max(0.0, score - 0.02)
            event = {
                "event_id": f"evt_{self.tick_count}",
                "timestamp": time.time(),
                "camera_id": camera_id,
                "normalized_severity": score,
            }
            await event_bus.publish("anomaly.events", event)
            self.anomaly_count += 1
            return score
            
        if not self.stream_a_enabled:
            return 0.0
        t0 = time.time()
        try:
            resp = requests.post(self.stream_a_endpoint, json={"camera_id": camera_id}, timeout=1.0)
            if resp.status_code == 200:
                data = resp.json()
                score = data.get("normalized_severity", 0.0)
                event = {
                    "event_id": f"evt_{self.tick_count}",
                    "timestamp": time.time(),
                    "camera_id": camera_id,
                    "normalized_severity": score,
                }
                await event_bus.publish("anomaly.events", event)
                logger.info(f"Anomaly detected on {camera_id}: {score}")
                self.anomaly_count += 1
                
                metrics["stream_a_latency_ms"] = (time.time() - t0) * 1000
                return score
        except Exception as e:
            logger.warning("Stream-A unavailable. Fault Tolerance triggered. severity=0")
        return 0.0

    async def broadcast_digital_twin(self, info: dict, anomalies: dict, rl_payload: dict = None):
        t0 = time.time()
        dt_payload = {
            "type": "state_update",
            "tick": self.tick_count,
            "junction_id": "J0_0",
            "lat": 0.0,
            "lon": 0.0,
            "traffic": {
                "queue": info.get("queue", {}),
                "wait": info.get("wait", {})
            },
            "anomalies": anomalies,
            "signals": info.get("phase", ""),
            "neighbors": [],
            "rl": rl_payload
        }
        dt_info = mapper.get_intersection("J0_0")
        if dt_info:
            dt_payload["lat"] = dt_info["lat"]
            dt_payload["lon"] = dt_info["lon"]
            dt_payload["junction_id"] = dt_info["junction_id"]
            dt_payload["neighbors"] = dt_info["neighbors"]
            
        await event_bus.publish("traffic.state", dt_payload)
        dt_history.append(dt_payload)
        
        try:
            # Broadcast to all connected websocket clients
            await manager.broadcast(json.dumps(dt_payload))
        except Exception as e:
            logger.warning(f"Websocket broadcast failed. {e}")
            
        metrics["websocket_latency_ms"] = (time.time() - t0) * 1000

    def heuristic_action(self, obs):
        phase_idx = (self.tick_count // 30) % 2
        return phase_idx

    async def run_loop(self):
        self.running = True
        logger.info("Hybrid Runtime Execution Started.")
        
        while self.running:
            self.tick_count += 1
            metrics["ticks"] = self.tick_count
            start_time = time.time()
            self.anomaly_count = 0
            
            # STEP 1: CAMERA -> ANOMALY PIPELINE
            current_anomalies = {}
            for approach in APPROACHES:
                severity = await self.poll_stream_a(f"cam_{approach}")
                self.anomaly_buffers[approach].append(severity)
                max_sev = max(self.anomaly_buffers[approach]) if self.anomaly_buffers[approach] else 0.0
                current_anomalies[approach] = max_sev
                
                try:
                    self.env._anomaly_severity[approach] = max_sev
                    self.env._anomaly_timer[approach] = max_sev * 60.0 
                except Exception as e:
                    logger.error(f"SUMO Exception on applying anomaly: {e}")
                    self._init_sumo()
            
            # Update metrics
            metrics["anomaly_events_sec"] = self.anomaly_count
            
            # STEP 2: HYBRID STATE
            t_hyb = time.time()
            info = self.info
            class _DummyApproach:
                def __init__(self, q, w):
                    self.queue_length = q
                    self.wait_time = w
                    self.occupancy_pct = min(100.0, q * 5.0)
                    self.speed_kmh = max(0.0, 50.0 - q * 2.0)
                    self.flow_veh_h = q * 100.0

            approaches_data = {
                a: _DummyApproach(info["queue"].get(a, 0), info["wait"].get(a, 0)) for a in APPROACHES
            }

            hybrid_state = HybridStateBuilder.build_from_telemetry(
                intersection_id="J0_0",
                approaches=approaches_data,
                phase_index=0,
                phase_name=info.get("phase", "NS_GREEN"),
                anomalies=[{"lane": a, "severity": current_anomalies[a]} for a in APPROACHES]
            )
            metrics["hybrid_update_latency_ms"] = (time.time() - t_hyb) * 1000
            
            # STEP 3: RL DECISION
            t_rl = time.time()
            obs_vec = RLObservationMapper.to_vector(hybrid_state)
            
            rl_payload = {
                "action": None,
                "probabilities": []
            }
            
            try:
                if self.rl_policy is not None:
                    action, _ = self.rl_policy.predict(obs_vec, deterministic=True)
                    action = int(action)
                    
                    # Extract probabilities from the policy
                    obs_tensor = torch.tensor(obs_vec).float().unsqueeze(0).to(self.rl_policy.device)
                    dist = self.rl_policy.policy.get_distribution(obs_tensor)
                    probs = dist.distribution.probs.squeeze(0).cpu().detach().numpy().tolist()
                    
                    rl_payload["action"] = action
                    rl_payload["probabilities"] = probs
                else:
                    action = self.heuristic_action(obs_vec)
                    rl_payload["action"] = action
                    rl_payload["probabilities"] = [0.25, 0.25, 0.25, 0.25]
            except Exception as e:
                logger.error(f"RL model failed. Triggering fallback. {e}")
                action = self.heuristic_action(obs_vec)
                rl_payload["action"] = action
                rl_payload["probabilities"] = [0.25, 0.25, 0.25, 0.25]
                
            metrics["rl_inference_latency_ms"] = (time.time() - t_rl) * 1000
            
            await event_bus.publish("signal.decisions", {"action": action, "tick": self.tick_count})
            logger.info(f"RL Decision: {action}")
            
            # Apply to SUMO
            t_sumo = time.time()
            try:
                self.obs, reward, terminated, truncated, self.info = self.env.step(action)
                if terminated or truncated:
                    self.obs, self.info = self.env.reset()
            except Exception as e:
                logger.error(f"SUMO tick failed. Triggering restart. {e}")
                self._init_sumo()
            metrics["sumo_tick_latency_ms"] = (time.time() - t_sumo) * 1000
            
            # STEP 4: DIGITAL TWIN
            await self.broadcast_digital_twin(self.info, current_anomalies, rl_payload)
            
            elapsed = time.time() - start_time
            sleep_time = self.config["sumo"]["simulation_rate"] - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0.001)

def run_fastapi():
    host = "0.0.0.0"
    port = 8001
    uvicorn.run(app, host=host, port=port)

async def main():
    # Run FastAPI in background
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_fastapi)
    
    runtime = HybridRuntime()
    await runtime.run_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down Hybrid Runtime...")
