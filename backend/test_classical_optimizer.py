import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.classical_optimizer import solve_exact


SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "app"
    / "quantum_runs"
    / "20260918T231615Z_candidates.json"
)


def test_exact_classical_baseline():
    result = solve_exact(SNAPSHOT_PATH)
    solution = result["best_solution"]

    assert result["status"] == "success"
    assert result["candidate_count"] == 11
    assert result["search_space_size"] == 2048
    assert result["feasible_states"] == 562
    assert solution["num_selected"] == 4
    assert solution["feasible"] is True
    assert math.isclose(solution["total_power_saving_w"], 1223.1)
    assert [device["device_id"] for device in solution["selected_devices"]] == [
        "TRX-800G-028",
        "TRX-800G-023",
        "TRX-800G-006",
        "TRX-800G-010",
    ]

if __name__ == "__main__":
    test_exact_classical_baseline()
