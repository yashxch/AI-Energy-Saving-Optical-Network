import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.simulator import simulator
from app.digital_twin import digital_twin_engine
from app.policy_engine import policy_engine
from app.models import ActionType, WhatIfSimulationRequest, SimulationResult, PowerMode

def test_digital_twin_component():
    print("==================================================")
    print("Testing Digital Twin Engine & What-If Simulation")
    print("==================================================")

    # 1. Test Digital Twin Scheduled & On-Demand Synchronization
    simulator.tick()
    summary = digital_twin_engine.synchronize()
    assert summary.total_devices == 100, f"Expected 100 twin devices, got {summary.total_devices}"
    assert summary.synchronized_devices > 90, f"Expected >90 synced devices, got {summary.synchronized_devices}"
    print(f"  [OK] Digital Twin state sync passed ({summary.synchronized_devices} devices SYNCED, Sync Status: {summary.sync_status.value})")

    # 1b. Test Cached State & On-Demand Stale Detection
    assert not digital_twin_engine.is_stale(threshold_sec=5.0), "Twin state should not be stale immediately after sync"
    cached_summary = digital_twin_engine.get_state_summary()
    assert cached_summary is not None
    assert cached_summary.total_devices == 100
    
    # Test on-demand sync when stale threshold is 0.0s
    assert digital_twin_engine.is_stale(threshold_sec=0.0) is True
    ondemand_summary = digital_twin_engine.ensure_synced(threshold_sec=0.0)
    assert ondemand_summary is not None
    print(f"  [OK] Digital Twin cached state and on-demand stale refresh passed")

    # 2. Test NetworkX Graph Topology
    topo = digital_twin_engine.get_topology_graph()
    assert topo.total_nodes > 0, "Expected graph nodes"
    assert topo.total_edges > 0, "Expected graph edges"
    print(f"  [OK] NetworkX Graph topology built ({topo.total_nodes} nodes, {topo.total_edges} links)")

    # 3. Test What-If Simulation: Approved Sleep
    dev_id = "TRX-800G-005"
    simulator.devices[dev_id].telemetry.traffic_utilization_pct = 12.0
    simulator.devices[dev_id].telemetry.osnr_db = 26.5
    simulator.devices[dev_id].power_mode = PowerMode.NORMAL
    digital_twin_engine.synchronize()

    req_approved = WhatIfSimulationRequest(device_id=dev_id, action_type=ActionType.SLEEP_TRANSPONDER)
    res_approved = digital_twin_engine.simulate_what_if(req_approved)

    assert res_approved.result == SimulationResult.APPROVED, f"Expected APPROVED, got {res_approved.result}: {res_approved.reason}"
    assert res_approved.power_savings.instantaneous_w > 0, "Expected positive power savings"
    assert res_approved.discarded is True, "Expected temporary simulation state to be discarded"
    print(f"  [OK] What-If Simulation Approved Sleep passed (Savings: {res_approved.power_savings.instantaneous_w} W, Reason: {res_approved.reason[:60]}...)")

    # 4. Test What-If Simulation: Rejected Sleep due to High Traffic
    dev_high_traffic = "TRX-800G-001"
    simulator.devices[dev_high_traffic].telemetry.traffic_utilization_pct = 85.0
    simulator.devices[dev_high_traffic].power_mode = PowerMode.NORMAL
    digital_twin_engine.synchronize()

    req_rejected_traffic = WhatIfSimulationRequest(device_id=dev_high_traffic, action_type=ActionType.SLEEP_TRANSPONDER)
    res_rejected_traffic = digital_twin_engine.simulate_what_if(req_rejected_traffic)

    assert res_rejected_traffic.result == SimulationResult.REJECTED, "Expected REJECTED for high traffic sleep"
    assert "exceeding max" in res_rejected_traffic.reason
    print("  [OK] What-If Simulation REJECTED high traffic sleep passed")

    # 5. Test What-If Simulation: Rejected Sleep due to Degraded OSNR
    dev_low_osnr = "TRX-800G-012"
    simulator.devices[dev_low_osnr].telemetry.traffic_utilization_pct = 10.0
    simulator.devices[dev_low_osnr].telemetry.osnr_db = 13.8  # Below min 14.5 dB
    simulator.devices[dev_low_osnr].power_mode = PowerMode.NORMAL
    digital_twin_engine.synchronize()

    req_rejected_osnr = WhatIfSimulationRequest(device_id=dev_low_osnr, action_type=ActionType.SLEEP_TRANSPONDER)
    res_rejected_osnr = digital_twin_engine.simulate_what_if(req_rejected_osnr)

    assert res_rejected_osnr.result == SimulationResult.REJECTED, "Expected REJECTED for low OSNR"
    assert "violating minimum optical margin" in res_rejected_osnr.reason or "OSNR" in res_rejected_osnr.reason
    print("  [OK] What-If Simulation REJECTED low OSNR passed")

    # 6. Test Demo Scenarios (Scenarios 1-5)
    scenarios = digital_twin_engine.get_demo_scenarios()
    assert len(scenarios) == 5, f"Expected 5 demo scenarios, got {len(scenarios)}"
    
    for sc in scenarios:
        res_sc = digital_twin_engine.run_demo_scenario(sc.scenario_id)
        assert res_sc.result is not None
        print(f"  [OK] Demo {sc.scenario_id} ({sc.title}): Result={res_sc.result.value}")

    # 7. Test FastAPI Digital Twin Endpoints
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    res_state = client.get("/api/digital-twin/state")
    assert res_state.status_code == 200
    assert res_state.json()["total_devices"] == 100

    res_devs = client.get("/api/digital-twin/devices")
    assert res_devs.status_code == 200
    assert len(res_devs.json()) == 100

    res_topo = client.get("/api/digital-twin/topology")
    assert res_topo.status_code == 200

    res_sim = client.post("/api/digital-twin/simulate", json={"device_id": "TRX-800G-005", "action_type": "Sleep idle transponder"})
    assert res_sim.status_code == 200
    assert "result" in res_sim.json()

    res_scenarios = client.get("/api/digital-twin/demo/scenarios")
    assert res_scenarios.status_code == 200

    res_run_demo = client.post("/api/digital-twin/demo/run?scenario_id=SCENARIO-1")
    assert res_run_demo.status_code == 200

    print("\nALL DIGITAL TWIN UNIT & INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_digital_twin_component()
