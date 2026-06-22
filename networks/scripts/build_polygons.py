"""
Generate SUMO polygons from OSM using polyconvert.
"""
import os
import argparse
import subprocess

def build_polygons(osm_path: str, net_path: str, output_path: str):
    print(f"Generating polygons for {net_path} from {osm_path}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # We want buildings, parks, water bodies.
    # The default polyconvert behavior will read many of these if we provide a typemap.
    # SUMO provides a default typemap in $SUMO_HOME/data/typemap/osmPolyconvert.typ.xml
    # If SUMO_HOME is set, we can use it.
    sumo_home = os.environ.get("SUMO_HOME", "")
    typemap = os.path.join(sumo_home, "data", "typemap", "osmPolyconvert.typ.xml")
    
    cmd = [
        "polyconvert",
        "--net-file", net_path,
        "--osm-files", osm_path,
        "-o", output_path
    ]
    
    if sumo_home and os.path.exists(typemap):
        cmd.extend(["--type-file", typemap])
    else:
        print("Warning: SUMO_HOME not set or typemap not found. Generating without type map.")

    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error running polyconvert:")
        print(result.stderr)
        raise RuntimeError("polyconvert failed")
        
    print(f"Successfully generated {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--osm", type=str, required=True, help="Input .osm file path")
    parser.add_argument("--net", type=str, required=True, help="Input .net.xml file path")
    parser.add_argument("--output", type=str, required=True, help="Output .poly.xml file path")
    args = parser.parse_args()
    
    build_polygons(args.osm, args.net, args.output)
