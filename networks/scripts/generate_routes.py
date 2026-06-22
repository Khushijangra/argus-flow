"""
Generate routes for a SUMO network using randomTrips.py
"""
import os
import argparse
import subprocess
import sys

def generate_routes(net_path: str, output_path: str, end_time: int = 3600, period: float = 1.0):
    print(f"Generating routes for {net_path}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Locate randomTrips.py from SUMO_HOME
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        print("Warning: SUMO_HOME not set. Using 'randomTrips.py' from path, hoping it's accessible.")
        random_trips_cmd = "randomTrips.py"
    else:
        random_trips_cmd = os.path.join(sumo_home, "tools", "randomTrips.py")
        
    cmd = [
        sys.executable, random_trips_cmd,
        "-n", net_path,
        "-r", output_path,
        "-e", str(end_time),
        "-p", str(period),
        "--fringe-factor", "10",
        "--min-distance", "300"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error running randomTrips.py:")
        print(result.stderr)
        raise RuntimeError("randomTrips failed")
        
    print(f"Successfully generated {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", type=str, required=True, help="Input .net.xml file path")
    parser.add_argument("--output", type=str, required=True, help="Output .rou.xml file path")
    parser.add_argument("--end", type=int, default=3600, help="End time of generation")
    parser.add_argument("--period", type=float, default=1.0, help="Arrival rate (seconds per vehicle)")
    args = parser.parse_args()
    
    generate_routes(args.net, args.output, args.end, args.period)
