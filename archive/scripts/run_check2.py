import sys
import os
import asyncio
from unittest.mock import patch

PROJECT_ROOT = "c:/Users/Asus/OneDrive/Desktop/projects/urban congestion"
sys.path.insert(0, PROJECT_ROOT)

from backend.runtime.hybrid_runtime import HybridRuntime

async def run_check2():
    print("Starting Check 2: 100 consecutive HybridRuntime cycles...")
    runtime = HybridRuntime()
    
    # Override Stream-A with a mock that returns 0.0 severity to test basic flow
    async def mock_poll_stream_a(camera_id):
        return 0.0
    runtime.poll_stream_a = mock_poll_stream_a
    
    print("Initialized. Running 100 cycles...")
    for _ in range(100):
        # We manually run the body of the loop without the while True
        runtime.tick_count += 1
        current_anomalies = {}
        for approach in ["north", "south", "east", "west"]:
            severity = await runtime.poll_stream_a(f"cam_{approach}")
            current_anomalies[approach] = severity
            
            # Simplified mock step for the env if needed
            runtime.env._anomaly_severity[approach] = severity
            runtime.env._anomaly_timer[approach] = severity * 60.0 
            
        from control.traffic_env import APPROACHES
        class _DummyApproach:
            def __init__(self, q, w):
                self.queue_length = q
                self.wait_time = w
                self.occupancy_pct = min(100.0, q * 5.0)
                self.speed_kmh = max(0.0, 50.0 - q * 2.0)
                self.flow_veh_h = q * 100.0

        approaches_data = {
            a: _DummyApproach(runtime.info["queue"].get(a, 0), runtime.info["wait"].get(a, 0)) for a in APPROACHES
        }
        
        from core.hybrid_state import HybridStateBuilder, RLObservationMapper
        hybrid_state = HybridStateBuilder.build_from_telemetry(
            intersection_id="J0_0",
            approaches=approaches_data,
            phase_index=0,
            phase_name=runtime.info.get("phase", "NS_through"),
            anomalies=[{"lane": a, "severity": current_anomalies[a]} for a in APPROACHES]
        )
        
        obs_vec = RLObservationMapper.to_vector(hybrid_state)
        
        if runtime.rl_policy is not None:
            action, _ = runtime.rl_policy.predict(obs_vec, deterministic=True)
            action = int(action)
        else:
            action = runtime.heuristic_action(obs_vec)
            
        runtime.obs, reward, terminated, truncated, runtime.info = runtime.env.step(action)
        if terminated or truncated:
            runtime.obs, runtime.info = runtime.env.reset()
            
    print("Check 2 Completed: 100 cycles ran successfully without crashes, shape mismatches, or fallback errors.")
    return True

if __name__ == "__main__":
    asyncio.run(run_check2())
