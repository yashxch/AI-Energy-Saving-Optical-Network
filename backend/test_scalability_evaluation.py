import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.scalability_evaluation import evaluate_scalability


SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "app"
    / "quantum_runs"
    / "20260918T231615Z_candidates.json"
)


def _without_runtime(value):
    if isinstance(value, dict):
        return {
            key: _without_runtime(item)
            for key, item in value.items()
            if not key.endswith("runtime_ms")
        }
    if isinstance(value, list):
        return [_without_runtime(item) for item in value]
    return value


def test_scalability_evaluation_is_deterministic_and_valid():
    first = evaluate_scalability(SNAPSHOT_PATH)
    second = evaluate_scalability(SNAPSHOT_PATH)

    assert first["hardware_used"] is False
    assert [item["candidate_count"] for item in first["instances"]] == [4, 6, 8, 10, 11]
    assert _without_runtime(first) == _without_runtime(second)

    for instance in first["instances"]:
        candidate_count = instance["candidate_count"]
        assert instance["total_binary_states"] == 2 ** candidate_count
        assert instance["feasible_states"] == sum(
            math.comb(candidate_count, selected)
            for selected in range(min(candidate_count, 4) + 1)
        )
        assert instance["qubo"]["decision_variables"] == candidate_count
        assert instance["qubo"]["slack_variables"] == 3
        assert instance["qubo"]["total_logical_qubits"] == candidate_count + 3

        exact = instance["exact"]
        simulated_annealing = instance["simulated_annealing"]
        local_qaoa = instance["local_qaoa"]
        assert exact["feasible"] is True
        assert simulated_annealing["feasible"] is True
        assert local_qaoa["feasible"] is True
        assert len(exact["selected_devices"]) <= 4
        assert len(simulated_annealing["selected_devices"]) <= 4
        assert len(local_qaoa["selected_devices"]) <= 4
        assert math.isclose(
            simulated_annealing["approximation_ratio"],
            simulated_annealing["saving_w"] / exact["saving_w"],
        )
        assert math.isclose(
            local_qaoa["approximation_ratio"],
            local_qaoa["saving_w"] / exact["saving_w"],
        )
        assert math.isclose(
            simulated_annealing["optimality_gap_w"],
            exact["saving_w"] - simulated_annealing["saving_w"],
        )
        assert math.isclose(
            local_qaoa["optimality_gap_w"],
            exact["saving_w"] - local_qaoa["saving_w"],
        )
        assert local_qaoa["parameter_combinations_evaluated"] == 81

    assert "qiskit_ibm_runtime" not in sys.modules
    assert "app.digital_twin" not in sys.modules
    assert "app.policy_engine" not in sys.modules


if __name__ == "__main__":
    test_scalability_evaluation_is_deterministic_and_valid()