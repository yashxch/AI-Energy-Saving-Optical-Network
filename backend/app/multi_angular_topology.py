import math
from typing import List, Dict, Tuple, Optional
from enum import Enum

class TopologyPattern(str, Enum):
    RING = "ring"
    FULL_MESH = "full_mesh"
    PARTIAL_MESH = "partial_mesh"
    STAR = "star"
    TREE = "tree"
    DIRECTIONAL_SECTOR = "directional_sector"
    ROTATIONAL_SWEEP = "rotational_sweep"
    HYBRID = "hybrid"

class Node3DPosition:
    def __init__(self, name: str, x: float, y: float, z: float = 0.0, orientation_deg: float = 0.0):
        self.name = name
        self.x = round(float(x), 2)
        self.y = round(float(y), 2)
        self.z = round(float(z), 2)
        self.orientation_deg = round(float(orientation_deg) % 360.0, 2)

    @property
    def radius(self) -> float:
        return round(math.sqrt(self.x**2 + self.y**2 + self.z**2), 2)

    @property
    def azimuth_deg(self) -> float:
        """Polar azimuth angle in 0-360 degrees."""
        angle = math.degrees(math.atan2(self.y, self.x)) % 360.0
        return round(angle, 2)

    def rotate_around_origin(self, delta_deg: float):
        rad = math.radians(delta_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        new_x = self.x * cos_a - self.y * sin_a
        new_y = self.x * sin_a + self.y * cos_a
        self.x = round(new_x, 2)
        self.y = round(new_y, 2)
        self.orientation_deg = round((self.orientation_deg + delta_deg) % 360.0, 2)

    def set_orientation(self, angle_deg: float):
        self.orientation_deg = round(float(angle_deg) % 360.0, 2)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "radius": self.radius,
            "azimuth_deg": self.azimuth_deg,
            "orientation_deg": self.orientation_deg
        }

class MultiAngularLink:
    def __init__(self, src: str, dst: str, distance_km: float, bearing_deg: float, active: bool = True):
        self.src = src
        self.dst = dst
        self.distance_km = round(float(distance_km), 2)
        self.bearing_deg = round(float(bearing_deg) % 360.0, 2)
        self.active = active

    def to_dict(self) -> dict:
        return {
            "src": self.src,
            "dst": self.dst,
            "distance_km": self.distance_km,
            "bearing_deg": self.bearing_deg,
            "active": self.active
        }

class MultiAngularTopologyEngine:
    def __init__(self, node_names: Optional[List[str]] = None):
        if node_names is None:
            node_names = ["NYC", "BOS", "CHI", "WDC", "ATL", "DAL", "SFO", "LAX"]
        
        self.nodes: Dict[str, Node3DPosition] = {}
        self.pattern: TopologyPattern = TopologyPattern.HYBRID
        self.global_rotation_deg: float = 0.0
        self._init_node_positions(node_names)

    def _init_node_positions(self, node_names: List[str]):
        """Positions nodes in a multi-angular layout in 2D/3D space."""
        n = len(node_names)
        radius = 500.0  # Base scale distance in km
        for i, name in enumerate(node_names):
            angle_rad = (2 * math.pi * i) / n
            # Vary radial distance slightly for natural geographical layout representation
            r = radius * (0.85 + 0.3 * (i % 3) / 2.0)
            x = r * math.cos(angle_rad)
            y = r * math.sin(angle_rad)
            z = 20.0 * math.sin(i)  # Slight elevation profile
            orientation = (math.degrees(angle_rad) + 90.0) % 360.0
            self.nodes[name] = Node3DPosition(name, x, y, z, orientation)

    def rotate_network(self, delta_deg: float):
        """Rotates the entire network topology by delta_deg degrees around origin."""
        self.global_rotation_deg = round((self.global_rotation_deg + delta_deg) % 360.0, 2)
        for node in self.nodes.values():
            node.rotate_around_origin(delta_deg)

    def rotate_single_node(self, node_name: str, angle_deg: float):
        """Sets the individual angular orientation of a specific node."""
        if node_name in self.nodes:
            self.nodes[node_name].set_orientation(angle_deg)

    def calculate_distance_and_bearing(self, src_name: str, dst_name: str) -> Tuple[float, float]:
        if src_name not in self.nodes or dst_name not in self.nodes:
            return 0.0, 0.0
        src = self.nodes[src_name]
        dst = self.nodes[dst_name]
        dx = dst.x - src.x
        dy = dst.y - src.y
        dz = dst.z - src.z
        dist = math.sqrt(dx**2 + dy**2 + dz**2)
        bearing = math.degrees(math.atan2(dy, dx)) % 360.0
        return dist, bearing

    def generate_links(self, pattern: Optional[TopologyPattern] = None) -> List[MultiAngularLink]:
        if pattern is not None:
            self.pattern = pattern

        node_names = list(self.nodes.keys())
        n = len(node_names)
        links: List[MultiAngularLink] = []
        added_pairs = set()

        def add_link(src: str, dst: str, active: bool = True):
            if src == dst:
                return
            pair = (min(src, dst), max(src, dst))
            if pair in added_pairs:
                return
            added_pairs.add(pair)
            dist, bearing = self.calculate_distance_and_bearing(src, dst)
            links.append(MultiAngularLink(src, dst, dist, bearing, active=active))

        pat = self.pattern

        if pat == TopologyPattern.RING:
            for i in range(n):
                src = node_names[i]
                dst = node_names[(i + 1) % n]
                add_link(src, dst)

        elif pat == TopologyPattern.FULL_MESH:
            for i in range(n):
                for j in range(i + 1, n):
                    add_link(node_names[i], node_names[j])

        elif pat == TopologyPattern.PARTIAL_MESH:
            # Connect ring + 2nd nearest neighbors
            for i in range(n):
                add_link(node_names[i], node_names[(i + 1) % n])
                add_link(node_names[i], node_names[(i + 2) % n])

        elif pat == TopologyPattern.STAR:
            # Hub node is the first node (or CHI/center)
            hub = node_names[2] if len(node_names) > 2 else node_names[0]
            for node in node_names:
                if node != hub:
                    add_link(hub, node)

        elif pat == TopologyPattern.TREE:
            # Binary/Hierarchical tree topology from root node_names[0]
            for i in range(1, n):
                parent_idx = (i - 1) // 2
                add_link(node_names[parent_idx], node_names[i])

        elif pat == TopologyPattern.DIRECTIONAL_SECTOR:
            # 4-degree directional sector switching (0°, 90°, 180°, 270°)
            for i, src in enumerate(node_names):
                for j, dst in enumerate(node_names):
                    if i != j:
                        dist, bearing = self.calculate_distance_and_bearing(src, dst)
                        # Check if bearing aligns within ±25° of main cardinal angles relative to node orientation
                        node_orient = self.nodes[src].orientation_deg
                        rel_angle = (bearing - node_orient) % 360.0
                        # Check cardinal sector alignment
                        cardinal_diff = min(
                            abs(rel_angle - 0), abs(rel_angle - 90), abs(rel_angle - 180),
                            abs(rel_angle - 270), abs(rel_angle - 360)
                        )
                        if cardinal_diff <= 35.0:
                            add_link(src, dst)

        elif pat == TopologyPattern.ROTATIONAL_SWEEP:
            # Links active based on node orientation angle ± 45 degrees sweep beam
            for i, src in enumerate(node_names):
                src_node = self.nodes[src]
                for j, dst in enumerate(node_names):
                    if i != j:
                        dist, bearing = self.calculate_distance_and_bearing(src, dst)
                        diff = abs((bearing - src_node.orientation_deg + 180) % 360 - 180)
                        active = diff <= 45.0
                        if active:
                            add_link(src, dst, active=True)

        elif pat == TopologyPattern.HYBRID:
            # Ring + Star hub + Directional links
            for i in range(n):
                add_link(node_names[i], node_names[(i + 1) % n])
            hub = node_names[2] if len(node_names) > 2 else node_names[0]
            for node in node_names:
                if node != hub:
                    add_link(hub, node)

        return links

    def get_topology_state(self) -> dict:
        links = self.generate_links()
        return {
            "pattern": self.pattern.value,
            "global_rotation_deg": self.global_rotation_deg,
            "total_nodes": len(self.nodes),
            "total_links": len(links),
            "active_links": len([l for l in links if l.active]),
            "nodes": {name: node.to_dict() for name, node in self.nodes.items()},
            "links": [link.to_dict() for link in links]
        }
