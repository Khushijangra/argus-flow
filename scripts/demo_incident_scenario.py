import time
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import threading
import requests

app = FastAPI(title="Mock Stream-A for Demo")

class AnomalyRequest(BaseModel):
    camera_id: str

# Global state for demo
SCENARIO_STATE = {
    "start_time": time.time(),
    "anomaly_active": False
}

@app.post("/api/v1/anomaly/detect")
def detect_anomaly(req: AnomalyRequest):
    elapsed = time.time() - SCENARIO_STATE["start_time"]
    
    # Inject synthetic accident / anomaly event on North camera after 10 seconds
    if elapsed > 10 and elapsed < 40 and req.camera_id == "cam_north":
        SCENARIO_STATE["anomaly_active"] = True
        return {
            "anomaly_score": 0.95,
            "normalized_severity": 1.0,
            "confidence": 0.99
        }
        
    SCENARIO_STATE["anomaly_active"] = False
    return {
        "anomaly_score": 0.1,
        "normalized_severity": 0.0,
        "confidence": 0.8
    }

def monitor_runtime():
    """Polls the Hybrid Runtime's /history/replay endpoint to verify behavior."""
    print("Demo Scenario Monitor Started.")
    while True:
        try:
            time.sleep(2)
            resp = requests.get("http://localhost:8001/history/replay?limit=1", timeout=1)
            if resp.status_code == 200:
                history = resp.json()
                if history:
                    latest = history[0]
                    anomalies = latest.get("anomalies", {})
                    phase = latest.get("signals", "")
                    print(f"Tick {latest['tick']} | Anomalies: {anomalies} | Phase: {phase}")
                    
                    if SCENARIO_STATE["anomaly_active"]:
                        print(">> Synthetic Accident Active: Verifying RL Policy change and Digital Twin reflection...")
                        if anomalies.get("north", 0.0) > 0.8:
                            print("   [OK] Anomaly successfully entered HybridState and Digital Twin.")
        except requests.exceptions.ConnectionError:
            pass # Wait for runtime to start

if __name__ == "__main__":
    print("====================================================")
    print("NEXUS-ATMS Demo: Incident Scenario Injection")
    print("====================================================")
    print("Starting Mock Stream-A Service on port 8000...")
    
    # Start monitor thread
    t = threading.Thread(target=monitor_runtime, daemon=True)
    t.start()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
