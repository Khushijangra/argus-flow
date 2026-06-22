"""
Download OSM network data for a given city or bounding box.
"""
import os
import argparse
import osmnx as ox

def download_osm(city_name: str, output_path: str):
    print(f"Downloading OSM data for: {city_name}")
    # Config osmnx
    ox.settings.use_cache = True
    ox.settings.log_console = True
    
    # Download graph
    # We want drivable roads
    G = ox.graph_from_place(city_name, network_type="drive", simplify=False)
    
    # Save to OSM XML format
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ox.save_graph_xml(G, filepath=output_path)
    print(f"Successfully saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", type=str, required=True, help="City name (e.g. 'Manhattan, New York, USA')")
    parser.add_argument("--output", type=str, required=True, help="Output .osm file path")
    args = parser.parse_args()
    
    download_osm(args.city, args.output)
