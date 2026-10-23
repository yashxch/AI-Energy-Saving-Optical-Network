from app.telemetry.nokia_topology import NokiaTopology
from app.telemetry.normalizer import NokiaTelemetryNormalizer


def test_nokia_topology_uses_inventory_and_explicit_links_only():
    normalizer = NokiaTelemetryNormalizer()
    devices = [
        normalizer.normalize_device(
            {
                "DEVICE-ID": "A",
                "name": "Card A",
                "NODE": "NE-West",
                "Source Endpoint": "NE-West",
                "Target Endpoint": "NE-East",
            },
            "internal-a",
        ),
        normalizer.normalize_device(
            {"DEVICE-ID": "B", "name": "Card B", "NODE": "NE-East"},
            "internal-b",
        ),
    ]

    topology = NokiaTopology().get_topology_state(devices)

    assert set(topology["nodes"]) == {"NE-West", "NE-East"}
    assert topology["links"] == [{
        "src": "NE-West",
        "dst": "NE-East",
        "distance_km": 0.0,
        "bearing_deg": 0.0,
        "active": True,
    }]
    assert topology["pattern"] == "verified-links"


def test_nokia_topology_does_not_invent_links():
    normalizer = NokiaTelemetryNormalizer()
    device = normalizer.normalize_device({"DEVICE-ID": "A", "NODE": "Real NE"}, "internal-a")

    topology = NokiaTopology().get_topology_state([device])

    assert set(topology["nodes"]) == {"Real NE"}
    assert topology["links"] == []
    assert topology["pattern"] == "inventory"
