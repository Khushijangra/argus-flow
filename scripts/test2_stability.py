import os
import sys
from pathlib import Path
import time
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from backend.runtime.checkpoint_manager import CheckpointManager
from control.traffic_env import TrafficEnvironment, IntersectionConfig
from core.hybrid_state import HybridStateBuilder, RLObservationMapper

def run_stability_test():
    print("====================================================")
    print("TEST 2: 500-CYCLE STABILITY TEST")
    print("====================================================")
    
    chk_mgr = CheckpointManager(primary_path=PROJECT_ROOT / "models/anomaly_v4/best/best_model.zip")
    model = chk_mgr.load_model()
    
    env = TrafficEnvironment(IntersectionConfig(), render_mode="none")
    env.reset()
    
    crashes = 0
    shape_mismatches = 0
    fatal_exceptions = 0
    
    class DummyApproach:
        def __init__(self):
            self.queue = 5
            self.waiting_time = 10.0
            self.flow_veh_h = 100.0
            
    approaches = {a: DummyApproach() for a in ["north", "south", "east", "west"]}
    
    try:
        for cycle in range(500):
            # Simulate pipeline
            try:
                # 1. Camera -> Stream-A (Simulated here with varying severities)
                severity = np.random.uniform(0.0, 1.0) if np.random.random() < 0.1 else 0.0
                anomalies = [{"lane": "north", "severity": severity}] if severity > 0 else []
                
                # 2. Hybrid State
                hybrid_state = HybridStateBuilder.build_from_telemetry(
                    intersection_id="J0_0",
                    approaches=approaches,
                    phase_index=env._current_phase,
                    phase_name="TEST_PHASE",
                    anomalies=anomalies
                )
                
                # 3. RL Mapper
                obs_vec = RLObservationMapper.to_vector(hybrid_state)
                if obs_vec.shape != (28,):
                    shape_mismatches += 1
                    
                # 4. PPO Agent
                action, _ = model.predict(obs_vec, deterministic=True)
                
                # 5. SUMO (Traffic Env)
                env.step(int(action))
                
                # 6. Digital Twin
                pass # Already simulated by stepping
                
            except Exception as e:
                crashes += 1
                print(f"Cycle {cycle} Crash: {str(e)}")
                
    except Exception as e:
        fatal_exceptions += 1
        print(f"Fatal Exception: {str(e)}")
        
    print("\nMetrics Collected:")
    print(f"Crashes: {crashes}")
    print(f"Shape Mismatches: {shape_mismatches}")
    print(f"Fatal Exceptions: {fatal_exceptions}")
    
    passed = (crashes == 0) and (shape_mismatches == 0) and (fatal_exceptions == 0)
    
    print("\n====================================================")
    print(f"TEST 2 RESULT: {'PASS' if passed else 'FAIL'}")
    print("====================================================")

if __name__ == "__main__":
    run_stability_test()
