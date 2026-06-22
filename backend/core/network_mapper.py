"""
network_mapper.py
Maintains OSM <-> SUMO <-> Camera mappings.
"""
import json
from typing import Dict, List, Optional

class NetworkMapper:
    def __init__(self):
        # Maps camera ID to alignment info
        self.camera_alignments: Dict[str, dict] = {}
        
        # Maps intersection ID to junction data
        self.intersections: Dict[str, dict] = {}

    def add_camera_alignment(self, camera_id: str, intersection_id: str, osm_node_id: str, sumo_junction_id: str):
        """Register a camera mapping to physical/simulation nodes."""
        self.camera_alignments[camera_id] = {
            "camera_id": camera_id,
            "intersection_id": intersection_id,
            "osm_node_id": osm_node_id,
            "sumo_junction_id": sumo_junction_id
        }

    def get_camera_alignment(self, camera_id: str) -> Optional[dict]:
        return self.camera_alignments.get(camera_id)

    def register_intersection(self, intersection_id: str, lat: float, lon: float, sumo_junction_id: str, neighbors: List[str]):
        """Register Digital Twin payload details for an intersection."""
        self.intersections[intersection_id] = {
            "intersection_id": intersection_id,
            "lat": lat,
            "lon": lon,
            "junction_id": sumo_junction_id,
            "neighbors": neighbors
        }

    def get_intersection(self, intersection_id: str) -> Optional[dict]:
        return self.intersections.get(intersection_id)

    def load_from_file(self, filepath: str):
        """Load mappings from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
            self.camera_alignments = data.get("cameras", {})
            self.intersections = data.get("intersections", {})

    def save_to_file(self, filepath: str):
        """Save mappings to a JSON file."""
        with open(filepath, 'w') as f:
            json.dump({
                "cameras": self.camera_alignments,
                "intersections": self.intersections
            }, f, indent=2)

# Global instance
mapper = NetworkMapper()
