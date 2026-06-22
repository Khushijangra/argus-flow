"""
Convert OSM network to SUMO .net.xml
"""
import os
import argparse
import subprocess

def build_sumo_network(osm_path: str, output_path: str):
    print(f"Converting {osm_path} to {output_path}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    cmd = [
        "netconvert",
        "--osm-files", osm_path,
        "-o", output_path,
        "--geometry.remove",
        "--roundabouts.guess",
        "--tls.guess-signals",
        "--junctions.join"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error running netconvert:")
        print(result.stderr)
        raise RuntimeError("netconvert failed")
        
    print(f"Successfully generated {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--osm", type=str, required=True, help="Input .osm file path")
    parser.add_argument("--output", type=str, required=True, help="Output .net.xml file path")
    args = parser.parse_args()
    
    build_sumo_network(args.osm, args.output)
