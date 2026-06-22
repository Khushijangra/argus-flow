import os
import subprocess
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def download_osm():
    print("Downloading OSM data for Piedmont, California...")
    # Standard OSM API expects left,bottom,right,top
    bbox = "-122.245,37.818,-122.225,37.832"
    url = f"https://api.openstreetmap.org/api/0.6/map?bbox={bbox}"
    
    osm_path = PROJECT_ROOT / "data" / "networks" / "piedmont.osm"
    osm_path.parent.mkdir(parents=True, exist_ok=True)
    
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    if response.status_code == 200:
        with open(osm_path, "wb") as f:
            f.write(response.content)
        print(f"OSM data saved to {osm_path}")
    else:
        print(f"Failed to download OSM data. Status: {response.status_code}")
        print(response.text)
        return

    print("Converting OSM to SUMO network...")
    net_path = PROJECT_ROOT / "data" / "networks" / "piedmont.net.xml"
    
    # Run netconvert
    cmd = [
        "netconvert",
        "--osm-files", str(osm_path),
        "-o", str(net_path),
        "--geometry.remove", "true",
        "--roundabouts.guess", "true",
        "--ramps.guess", "true",
        "--junctions.join", "true",
        "--tls.guess-signals", "true",
        "--tls.discard-simple", "true",
        "--tls.join", "true",
        "--tls.default-type", "actuated"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"SUMO network generated at {net_path}")
    except subprocess.CalledProcessError as e:
        print(f"netconvert failed: {e}")
        
if __name__ == "__main__":
    download_osm()
