import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.optimization_evaluation import (
    create_controlled_instances,
    diagnose_qaoa_instances,
    evaluate_instances,
    run_shot_sampling_diagnostic,
)


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
            if key not in {"runtime_ms", "parameter_search_runtime_ms"}
        }
    if isinstance(value, list):
        return [_without_runtime(item) for item in value]
    return value


def test_multi_instance_evaluation_is_deterministic_and_isolated():
    first_instances = create_controlled_instances(SNAPSHOT_PATH)
    second_instances = create_controlled_instances(SNAPSHOT_PATH)
    assert len(first_instances) == 5
    assert first_instances == second_instances
    assert all(len(instance["candidates"]) == 11 for instance in first_instances)

    first = evaluate_instances(SNAPSHOT_PATH, sa_iterations=1000)
    second = evaluate_instances(SNAPSHOT_PATH, sa_iterations=1000)

    assert first["instance_count"] == 5
    assert first["candidate_count"] == 11
    assert len(first["instances"]) == 5
    for first_instance, second_instance in zip(first["instances"], second["instances"]):
        for method in ("exact", "simulated_annealing", "local_qaoa"):
            first_method = dict(first_instance[method])
            second_method = dict(second_instance[method])
            first_method.pop("runtime_ms")
            second_method.pop("runtime_ms")
            first_method.pop("parameter_search_runtime_ms", None)
            second_method.pop("parameter_search_runtime_ms", None)
            assert first_method == second_method

    for instance in first["instances"]:
        exact = instance["exact"]
        simulated_annealing = instance["simulated_annealing"]
        local_qaoa = instance["local_qaoa"]
        assert exact["feasible"] is True
        assert simulated_annealing["feasible"] is True
        assert local_qaoa["feasible"] is True
        assert simulated_annealing["candidate_count"] == 11
        assert local_qaoa["candidate_count"] == 11
        exact_saving = exact["saving_w"]
        assert math.isclose(
            simulated_annealing["comparison"]["approximation_ratio"],
            simulated_annealing["saving_w"] / exact_saving,
        )
        assert math.isclose(
            simulated_annealing["comparison"]["optimality_gap_w"],
            exact_saving - simulated_annealing["saving_w"],
        )
        assert math.isclose(
            local_qaoa["comparison"]["approximation_ratio"],
            local_qaoa["saving_w"] / exact_saving,
        )
        assert math.isclose(
            local_qaoa["comparison"]["optimality_gap_w"],
            exact_saving - local_qaoa["saving_w"],
        )
        assert 0.0 <= local_qaoa["beta"] < 2 * math.pi
        assert -math.pi <= local_qaoa["gamma"] < math.pi
        assert math.isfinite(local_qaoa["expected_qubo_energy"])

    assert "qiskit_ibm_runtime" not in sys.modules

    shot_first = run_shot_sampling_diagnostic(SNAPSHOT_PATH)
    shot_second = run_shot_sampling_diagnostic(SNAPSHOT_PATH)
    assert shot_first["hardware_used"] is False
    assert shot_first["shot_counts"] == [128, 512, 1024]
    assert set(shot_first["instances"]) == {
        "instance_01",
        "instance_02",
        "instance_03",
        "instance_04",
        "instance_05",
    }
    assert _without_runtime(shot_first) == _without_runtime(shot_second)

    for instance in shot_first["instances"].values():
        assert instance["candidate_count"] == 11
        assert instance["max_actions"] == 4
        exact_saving = instance["exact"]["saving_w"]
        for shots in shot_first["shot_counts"]:
            result = instance["shot_results"][str(shots)]
            assert result["total_sampled_shots"] == shots
            assert sum(result["observed_bitstring_counts"].values()) == shots
            assert result["feasible_observations"] <= shots
            assert result["selection_source"] == "observed feasible samples only"
            assert len(result["selected_devices"]) <= instance["max_actions"]
            assert math.isclose(
                result["approximation_ratio"],
                result["saving_w"] / exact_saving,
            )
            assert math.isclose(
                result["optimality_gap_w"],
                exact_saving - result["saving_w"],
            )
            if result["selected_bitstring"] is not None:
                assert result["selected_bitstring"] in result["observed_bitstring_counts"]
                assert result["observed_probability"] > 0.0

    assert set(shot_first["aggregates_by_shots"]) == {"128", "512", "1024"}
    assert "qiskit_ibm_runtime" not in sys.modules
    assert "app.digital_twin" not in sys.modules
    assert "app.policy_engine" not in sys.modules

    diagnostic_first = diagnose_qaoa_instances(SNAPSHOT_PATH)
    diagnostic_second = diagnose_qaoa_instances(SNAPSHOT_PATH)
    assert set(diagnostic_first["instances"]) == {"instance_04", "instance_05"}
    assert diagnostic_first["hardware_used"] is False
    assert _without_runtime(diagnostic_first) == _without_runtime(diagnostic_second)

    for instance in diagnostic_first["instances"].values():
        assert instance["candidate_count"] == 11
        assert instance["max_actions"] == 4
        assert instance["feasible_device_states"] == 562
        assert set(instance["grid_resolution"]) == {"9x9", "17x17"}
        assert instance["exact"]["feasible"] is True
        assert instance["state_selection"]["highest_probability_feasible"]["probability"] > 0.0
        assert instance["state_selection"]["highest_saving_feasible_nonzero_probability"]["probability"] > 0.0
        for grid in instance["grid_resolution"].values():
            assert grid["feasible"] is True
            assert 0.0 <= grid["beta"] < 2 * math.pi
            assert -math.pi <= grid["gamma"] < math.pi
            assert math.isfinite(grid["expected_qubo_energy"])

    assert "qiskit_ibm_runtime" not in sys.modules


if __name__ == "__main__":
    test_multi_instance_evaluation_is_deterministic_and_isolated()