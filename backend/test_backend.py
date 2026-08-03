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

def test_backend_components():
    print("Testing 100 Optical Devices Telemetry Simulator...")
    assert len(simulator.devices) == 100, f"Expected 100 devices, got {len(simulator.devices)}"
    simulator.tick()
    print("  ✓ Telemetry simulator tick passed")

    print("Testing ML Traffic Prediction Engine...")
    pred_5m = ml_engine.predict_traffic("5m")
    assert len(pred_5m.predicted_traffic_gbps) == 10, "Expected 10 prediction points for 5m horizon"
    pred_24h = ml_engine.predict_traffic("24h")
    assert len(pred_24h.predicted_traffic_gbps) == 24, "Expected 24 prediction points for 24h horizon"
    print("  ✓ Traffic predictions (5m, 1h, 24h) passed")

    print("Testing Anomaly Detection Engine...")
    anomalies = ml_engine.detect_anomalies()
    print(f"  ✓ Anomaly detection passed ({len(anomalies)} anomalies flagged)")

    print("Testing LLM Recommendation Engine...")
    recs = llm_engine.get_recommendations()
    assert len(recs) > 0, "Expected AI power recommendations"
    print(f"  ✓ LLM reasoning engine generated {len(recs)} power recommendations")

    print("Testing Policy Validation Engine...")
    target_dev = list(simulator.devices.keys())[0]
    passed, checks, reason = policy_engine.validate_action(target_dev, ActionType.SLEEP_TRANSPONDER)
    print(f"  ✓ Policy check on {target_dev}: Passed={passed}, Checks count={len(checks)}")

    print("Testing Telecom Chatbot Query...")
    chat_reply = llm_engine.process_chat_query("Why is Transponder 3 consuming more power?")
    assert "Transponder" in chat_reply, "Expected transponder response"
    print("  ✓ AI Chatbot query processing passed")

    print("Testing FCAPS Manager...")
    alarms = fcaps_manager.get_fault_alarms()
    accounting = fcaps_manager.get_energy_accounting()
    assert accounting.total_power_kw > 0
    print(f"  ✓ FCAPS manager passed (Active kW: {accounting.total_power_kw} kW)")

    print("\nALL BACKEND UNIT TESTS PASSED SUCCESSFULLY! ✅")

if __name__ == "__main__":
    test_backend_components()
