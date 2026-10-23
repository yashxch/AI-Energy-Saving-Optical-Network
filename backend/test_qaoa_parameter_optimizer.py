import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.qaoa_parameter_optimizer import (
    DEFAULT_FIXED_BETA,
    DEFAULT_FIXED_GAMMA,
    optimize_parameters,
)


SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "app"
    / "quantum_runs"
    / "20260918T231615Z_candidates.json"
)


def test_local_parameter_search_is_deterministic_and_valid():
    first = optimize_parameters(SNAPSHOT_PATH, beta_points=5, gamma_points=5)
    second = optimize_parameters(SNAPSHOT_PATH, beta_points=5, gamma_points=5)

    assert first["status"] == "success"
    assert first["method"] == "classical_grid_search"
    assert first["candidate_count"] == 11
    assert first["qubo_variables"] == 14
    assert first["grid_size"]["total_evaluations"] == 25
    assert first["fixed_parameters"]["beta"] == DEFAULT_FIXED_BETA
    assert first["fixed_parameters"]["gamma"] == DEFAULT_FIXED_GAMMA
    assert math.isfinite(first["fixed_parameters"]["objective_value"])

    optimized = first["optimized_parameters"]
    assert 0.0 <= optimized["beta"] <= 2 * math.pi
    assert -math.pi <= optimized["gamma"] <= math.pi
    assert math.isfinite(optimized["objective_value"])
    assert first["improvement"] >= 0.0
    assert first["fixed_parameters"] == second["fixed_parameters"]
    assert first["optimized_parameters"] == second["optimized_parameters"]
    assert first["improvement"] == second["improvement"]
    assert "qiskit_ibm_runtime" not in sys.modules


if __name__ == "__main__":
    test_local_parameter_search_is_deterministic_and_valid()