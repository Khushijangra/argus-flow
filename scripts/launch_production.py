import os
import sys
import subprocess
import time
import signal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def launch_production():
    print("====================================================")
    print("LAUNCHING NEXUS-ATMS PRODUCTION SERVICES")
    print("====================================================")
    
    processes = []
    
    # 1. Stream-A Server
    stream_a_path = PROJECT_ROOT / "scripts" / "inference_server.py"
    if stream_a_path.exists():
        print("[1] Starting Stream-A Server...")
        p_stream_a = subprocess.Popen(
            [sys.executable, str(stream_a_path)],
            cwd=str(stream_a_path.parent)
        )
        processes.append(("Stream-A Server", p_stream_a))
    else:
        print("[!] Stream-A Server not found at path.")
        
    time.sleep(2) # Give it a moment to bind
    
    # 2. Hybrid Runtime & SUMO & FastAPI
    runtime_path = PROJECT_ROOT / "backend" / "runtime" / "hybrid_runtime.py"
    if runtime_path.exists():
        print("[2] Starting Hybrid Runtime (SUMO + FastAPI + RL)...")
        p_runtime = subprocess.Popen(
            [sys.executable, str(runtime_path)],
            cwd=str(PROJECT_ROOT)
        )
        processes.append(("Hybrid Runtime", p_runtime))
    else:
        print("[!] Hybrid Runtime not found at path.")
        
    print("\nAll production services started. Press Ctrl+C to gracefully shutdown.\n")
    
    try:
        # Wait indefinitely until interrupted
        while True:
            time.sleep(1)
            # Check if any process died unexpectedly
            for name, p in processes:
                if p.poll() is not None:
                    print(f"[!] Warning: {name} exited unexpectedly with code {p.returncode}")
                    processes.remove((name, p))
            if not processes:
                print("All processes exited. Stopping.")
                break
    except KeyboardInterrupt:
        print("\nShutdown signal received. Shutting down gracefully...")
        
    # Graceful shutdown
    for name, p in processes:
        print(f"Terminating {name}...")
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"{name} did not terminate. Killing...")
            p.kill()
            
    print("====================================================")
    print("SHUTDOWN COMPLETE")
    print("====================================================")

if __name__ == "__main__":
    launch_production()
