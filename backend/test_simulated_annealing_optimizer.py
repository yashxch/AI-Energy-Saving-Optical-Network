import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.simulated_annealing_optimizer import solve_simulated_annealing


SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "app"
    / "quantum_runs"
    / "20260918T231615Z_candidates.json"
)


def test_simulated_annealing_is_deterministic_and_feasible():
    first = solve_simulated_annealing(SNAPSHOT_PATH, seed=42, iterations=1000)
    second = solve_simulated_annealing(SNAPSHOT_PATH, seed=42, iterations=1000)

    assert first["status"] == "success"
    assert first["method"] == "simulated_annealing"
    assert first["candidate_count"] == 11
    assert first["max_actions"] == 4
    assert first["iterations"] == 1000
    assert first["seed"] == 42
    assert first["num_selected"] <= first["max_actions"]
    assert first["feasible"] is True
    assert math.isclose(
        first["total_power_saving_w"],
        sum(device["power_saving_w"] for device in first["selected_devices"]),
    )
    assert first["selected_devices"] == second["selected_devices"]
    assert first["num_selected"] == second["num_selected"]
    assert first["total_power_saving_w"] == second["total_power_saving_w"]
    assert "qiskit_ibm_runtime" not in sys.modules
    assert "app.digital_twin" not in sys.modules
    assert "app.policy_engine" not in sys.modules


if __name__ == "__main__":
    test_simulated_annealing_is_deterministic_and_feasible()