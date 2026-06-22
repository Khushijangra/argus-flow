"""
Run the full OSM -> SUMO pipeline for a given city.
"""
import os
import argparse
import subprocess
from xml.etree import ElementTree as ET
from xml.dom import minidom

def run_cmd(cmd):
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def generate_sumocfg(net_file, rou_file, poly_file, output_cfg):
    print(f"Generating SUMO config {output_cfg}")
    
    root = ET.Element("configuration")
    
    input_elem = ET.SubElement(root, "input")
    ET.SubElement(input_elem, "net-file", value=os.path.basename(net_file))
    
    rel_rou = os.path.relpath(rou_file, os.path.dirname(output_cfg))
    ET.SubElement(input_elem, "route-files", value=rel_rou.replace('\\', '/'))
    
    if poly_file and os.path.exists(poly_file):
        rel_poly = os.path.relpath(poly_file, os.path.dirname(output_cfg))
        ET.SubElement(input_elem, "additional-files", value=rel_poly.replace('\\', '/'))
        
    time_elem = ET.SubElement(root, "time")
    ET.SubElement(time_elem, "begin", value="0")
    ET.SubElement(time_elem, "end", value="3600")
    
    report_elem = ET.SubElement(root, "report")
    ET.SubElement(report_elem, "verbose", value="true")
    
    os.makedirs(os.path.dirname(output_cfg), exist_ok=True)
    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="    ")
    with open(output_cfg, "w") as f:
        f.write(xmlstr)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", type=str, default="Piedmont, California, USA", help="City name to download")
    parser.add_argument("--name", type=str, default="piedmont", help="Prefix for generated files")
    args = parser.parse_args()
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    osm_file = os.path.join(base_dir, "osm", f"{args.name}.osm")
    net_file = os.path.join(base_dir, "sumo", f"{args.name}.net.xml")
    poly_file = os.path.join(base_dir, "polygons", f"{args.name}.poly.xml")
    rou_file = os.path.join(base_dir, "routes", f"{args.name}.rou.xml")
    cfg_file = os.path.join(base_dir, "sumo", f"{args.name}.sumocfg")
    
    # 1. Download OSM
    run_cmd(["python", os.path.join(base_dir, "scripts", "download_osm.py"), "--city", args.city, "--output", osm_file])
    
    # 2. Build Net
    run_cmd(["python", os.path.join(base_dir, "scripts", "build_sumo_network.py"), "--osm", osm_file, "--output", net_file])
    
    # 3. Build Polygons
    run_cmd(["python", os.path.join(base_dir, "scripts", "build_polygons.py"), "--osm", osm_file, "--net", net_file, "--output", poly_file])
    
    # 4. Generate Routes
    run_cmd(["python", os.path.join(base_dir, "scripts", "generate_routes.py"), "--net", net_file, "--output", rou_file])
    
    # 5. Generate config
    generate_sumocfg(net_file, rou_file, poly_file, cfg_file)
    print("Pipeline completed successfully!")

if __name__ == "__main__":
    main()
