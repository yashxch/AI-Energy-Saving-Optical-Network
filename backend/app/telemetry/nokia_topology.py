import math
from typing import Dict, Iterable, List, Mapping, Set, Tuple

from ..models import Device


class NokiaTopology:
    """Builds an inventory topology from Nokia records without inferred links."""

    @staticmethod
    def _identity(device: Device) -> str:
        raw = device.raw_record or {}
        for key in ("node_location", "nodeName", "NODE", "LOCATION", "ne_name", "NE-NAME"):
            value = raw.get(key)
            if value not in (None, "") and str(value).strip().upper() not in {"UNKNOWN", "N/A", "NA"}:
                return str(value)
        if device.ne_name:
            return device.ne_name
        return device.node_location if device.node_location not in ("", "UNKNOWN") else ""

    @staticmethod
    def _endpoint(raw: Mapping[str, object], *keys: str) -> str:
        for key in keys:
            value = raw.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    def get_topology_state(self, devices: Iterable[Device]) -> dict:
        device_list = list(devices)
        node_names: Set[str] = set()
        explicit_links: Set[Tuple[str, str]] = set()

        for device in device_list:
            node_name = self._identity(device)
            if node_name:
                node_names.add(node_name)
            raw = device.raw_record or {}
            source = self._endpoint(raw, "endpoint_source", "Source", "Source Endpoint", "source_node")
            target = self._endpoint(raw, "endpoint_target", "Target", "Target Endpoint", "target_node")
            for container_name in ("connection", "link", "endpoints"):
                container = raw.get(container_name)
                if isinstance(container, Mapping):
                    source = source or self._endpoint(container, "source", "src", "endpoint_source", "Source")
                    target = target or self._endpoint(container, "target", "dst", "endpoint_target", "Target")
            if source and target and source != target:
                node_names.update((source, target))
                explicit_links.add((source, target))

            for link in raw.get("links", raw.get("connections", [])) if isinstance(raw, Mapping) else []:
                if not isinstance(link, Mapping):
                    continue
                link_source = self._endpoint(link, "source", "src", "endpoint_source", "Source")
                link_target = self._endpoint(link, "target", "dst", "endpoint_target", "Target")
                if link_source and link_target and link_source != link_target:
                    node_names.update((link_source, link_target))
                    explicit_links.add((link_source, link_target))

        ordered_nodes = sorted(node_names)
        count = max(len(ordered_nodes), 1)
        nodes = {}
        for index, name in enumerate(ordered_nodes):
            # Grid placement is visual only; it does not imply connectivity.
            columns = max(1, math.ceil(math.sqrt(count)))
            row, column = divmod(index, columns)
            nodes[name] = {
                "name": name,
                "x": (column - (columns - 1) / 2) * 260,
                "y": (row - (math.ceil(count / columns) - 1) / 2) * 150,
                "z": 0.0,
                "radius": 0.0,
                "azimuth_deg": 0.0,
                "orientation_deg": 0.0,
            }

        links = [
            {
                "src": source,
                "dst": target,
                "distance_km": 0.0,
                "bearing_deg": 0.0,
                "active": True,
            }
            for source, target in sorted(explicit_links)
        ]
        return {
            "pattern": "inventory" if not links else "verified-links",
            "global_rotation_deg": 0.0,
            "total_nodes": len(nodes),
            "total_links": len(links),
            "active_links": len(links),
            "nodes": nodes,
            "links": links,
        }
