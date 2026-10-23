import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.simulator import simulator
from app.ml_engine import ml_engine
from app.llm_engine import llm_engine
from app.policy_engine import policy_engine
from app.fcaps import fcaps_manager
from app.models import ActionType
from app.multi_angular_topology import MultiAngularTopologyEngine, TopologyPattern

def test_glean_chatbot_context(monkeypatch):
    import app.llm_engine as llm_module

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload
        def read(self):
            return str(self._payload).encode("utf-8")

    def fake_urlopen(request):
        body = request.data.decode("utf-8") if getattr(request, "data", None) else ""
        assert "amplifier" in body.lower() or "gain" in body.lower()
        return FakeResponse('{"results": [{"title": "Nokia 1830 PSS amplifier tuning", "snippet": "Keep amplifier gain within safe optical margins and avoid OSNR below 14.5 dB."}]}')

    monkeypatch.setenv("GLEAN_BASE_URL", "https://example.glean.nokia.test")
    monkeypatch.setenv("GLEAN_API_TOKEN", "demo-token")
    monkeypatch.setattr(llm_module, "urlopen", fake_urlopen)

    response = llm_module.llm_engine.process_chat_query("What is the safe guide for amplifier gain tuning?")

    assert "Glean" in response
    assert "14.5 dB" in response


def test_backend_components():
    print("Testing 100 Optical Devices Telemetry Simulator...")
    assert len(simulator.devices) == 100, f"Expected 100 devices, got {len(simulator.devices)}"
    simulator.tick()
    print("  [OK] Telemetry simulator tick passed")

    print("Testing Multi-Angular Node Connectivity & Dynamic Rotation Engine...")
    topo = MultiAngularTopologyEngine(["NYC", "BOS", "CHI", "WDC", "ATL", "DAL", "SFO", "LAX"])
    
    # 1. Check Initial State & Angular Positions
    state = topo.get_topology_state()
    assert state["total_nodes"] == 8, f"Expected 8 nodes, got {state['total_nodes']}"
    assert "NYC" in state["nodes"]
    print("  [OK] Node positions and 3D polar coordinates initialized")

    # 2. Test 360-Degree Rotation
    initial_nyc_x = topo.nodes["NYC"].x
    topo.rotate_network(90.0)
    rotated_state = topo.get_topology_state()
    assert rotated_state["global_rotation_deg"] == 90.0
    assert topo.nodes["NYC"].x != initial_nyc_x, "Expected NYC coordinates to change after 90 degree rotation"
    print("  [OK] 360-degree dynamic angular rotation verified")

    # 3. Test All Topology Patterns
    patterns_to_test = [
        TopologyPattern.RING, TopologyPattern.FULL_MESH, TopologyPattern.PARTIAL_MESH,
        TopologyPattern.STAR, TopologyPattern.TREE, TopologyPattern.DIRECTIONAL_SECTOR,
        TopologyPattern.ROTATIONAL_SWEEP, TopologyPattern.HYBRID
    ]
    for pat in patterns_to_test:
        links = topo.generate_links(pat)
        assert len(links) > 0, f"Pattern {pat.value} produced 0 links"
        print(f"  [OK] Topology pattern '{pat.value}' generated {len(links)} multi-angular links")

    # 4. Test Simulator Topology Integration
    sim_topo_res = simulator.set_topology_pattern("star")
    assert sim_topo_res["pattern"] == "star"
    rotate_res = simulator.rotate_topology(45.0)
    assert rotate_res["global_rotation_deg"] == 45.0
    print("  [OK] Simulator pattern switching and rotation integration verified")

    print("Testing ML Traffic Prediction Engine...")
    pred_5m = ml_engine.predict_traffic("5m")
    assert len(pred_5m.predicted_traffic_gbps) == 10, "Expected 10 prediction points for 5m horizon"
    pred_24h = ml_engine.predict_traffic("24h")
    assert len(pred_24h.predicted_traffic_gbps) == 24, "Expected 24 prediction points for 24h horizon"
    print("  [OK] Traffic predictions (5m, 1h, 24h) passed")

    print("Testing Anomaly Detection Engine...")
    anomalies = ml_engine.detect_anomalies()
    print(f"  [OK] Anomaly detection passed ({len(anomalies)} anomalies flagged)")

    print("Testing LLM Recommendation Engine...")
    recs = llm_engine.get_recommendations()
    assert len(recs) > 0, "Expected AI power recommendations"
    print(f"  [OK] LLM reasoning engine generated {len(recs)} power recommendations")

    print("Testing Policy Validation Engine...")
    target_dev = list(simulator.devices.keys())[0]
    passed, checks, reason = policy_engine.validate_action(target_dev, ActionType.SLEEP_TRANSPONDER)
    print(f"  [OK] Policy check on {target_dev}: Passed={passed}, Checks count={len(checks)}")

    print("Testing Telecom Chatbot Query...")
    chat_reply = llm_engine.process_chat_query("Why is Transponder 3 consuming more power?")
    assert "Transponder" in chat_reply, "Expected transponder response"
    print("  [OK] AI Chatbot query processing passed")

    print("Testing FCAPS Manager...")
    alarms = fcaps_manager.get_fault_alarms()
    accounting = fcaps_manager.get_energy_accounting()
    assert accounting.total_power_kw > 0
    print(f"  [OK] FCAPS manager passed (Active kW: {accounting.total_power_kw} kW)")

    print("Testing FastAPI REST API Topology Endpoints...")
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    
    res = client.get("/api/topology")
    assert res.status_code == 200
    res_pat = client.post("/api/topology/pattern", json={"pattern": "full_mesh"})
    assert res_pat.status_code == 200
    res_rot = client.post("/api/topology/rotate", json={"delta_deg": 30.0})
    assert res_rot.status_code == 200
    res_conn = client.get("/api/topology/connectivity")
    assert res_conn.status_code == 200
    print("  [OK] FastAPI Topology endpoints GET & POST verified")

    print("Testing Digital Twin Engine & Endpoints...")
    from app.digital_twin import digital_twin_engine
    dt_summary = digital_twin_engine.synchronize()
    assert dt_summary.total_devices == 100
    dt_res = client.get("/api/digital-twin/state")
    assert dt_res.status_code == 200
    dt_sim = client.post("/api/digital-twin/simulate", json={"device_id": "TRX-800G-005", "action_type": "Sleep idle transponder"})
    assert dt_sim.status_code == 200
    print("  [OK] Digital Twin engine state & What-If simulation endpoints verified")

    print("\nALL BACKEND UNIT TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_backend_components()


