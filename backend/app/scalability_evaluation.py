"""Phase 5A controlled local scalability evaluation.

This experiment uses deterministic prefixes of the existing 11-candidate
controlled population. It measures local exact enumeration, simulated
annealing, and 9x9 local QAOA behavior without IBM Runtime or hardware jobs.
"""

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from .classical_optimizer import solve_exact
    from .optimization_evaluation import (
        DEFAULT_SA_SEED,
        _local_qaoa_result,
        create_controlled_instances,
    )
    from .qaoa_parameter_optimizer import build_qubo_energies
    from .simulated_annealing_optimizer import solve_simulated_annealing
except ImportError:
    from classical_optimizer import solve_exact
    from optimization_evaluation import (
        DEFAULT_SA_SEED,
        _local_qaoa_result,
        create_controlled_instances,
    )
    from qaoa_parameter_optimizer import build_qubo_energies
    from simulated_annealing_optimizer import solve_simulated_annealing


CANDIDATE_SIZES = (4, 6, 8, 10, 11)
MAX_ACTIONS = 4
SA_ITERATIONS = 1000
QAOA_BETA_POINTS = 9
QAOA_GAMMA_POINTS = 9
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "quantum_runs"
    / "20260918T231615Z_candidates.json"
)
DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parent.parent
    / "quantum_runs"
    / "scalability_report.json"
)


def _feasible_state_count(candidate_count, max_actions):
    return sum(
        math.comb(candidate_count, selected)
        for selected in range(min(candidate_count, max_actions) + 1)
    )


def _write_snapshot(path, candidates, size):
    path.write_text(
        json.dumps({
            "run_id": f"scalability_{size}",
            "candidate_count": len(candidates),
            "candidates": candidates,
        }),
        encoding="utf-8",
    )


def _method_result(result, saving_key="saving_w"):
    return {
        "saving_w": result[saving_key],
        "runtime_ms": result["runtime_ms"],
        "selected_devices": result["selected_devices"],
        "feasible": result["feasible"],
    }


def evaluate_scalability(
    snapshot_path=DEFAULT_SNAPSHOT_PATH,
    candidate_sizes=CANDIDATE_SIZES,
    sa_seed=DEFAULT_SA_SEED,
):
    """Evaluate deterministic candidate prefixes at controlled sizes."""
    source = create_controlled_instances(snapshot_path)[0]["candidates"]
    previous_binary_states = None
    instances = []

    with TemporaryDirectory(prefix="scalability-evaluation-") as temp_dir:
        for size in candidate_sizes:
            candidates = source[:size]
            instance_path = Path(temp_dir) / f"scalability_{size}.json"
            _write_snapshot(instance_path, candidates, size)

            sa_raw = solve_simulated_annealing(
                instance_path,
                max_actions=MAX_ACTIONS,
                seed=sa_seed,
                iterations=SA_ITERATIONS,
            )
            qaoa_raw = _local_qaoa_result(
                candidates,
                max_actions=MAX_ACTIONS,
                beta_points=QAOA_BETA_POINTS,
                gamma_points=QAOA_GAMMA_POINTS,
            )

            # The exact solver is only used to establish the post hoc baseline.
            exact_raw = solve_exact(instance_path, max_actions=MAX_ACTIONS)
            exact_solution = exact_raw["best_solution"]
            exact_saving = exact_solution["total_power_saving_w"]

            energies = build_qubo_energies(candidates, max_actions=MAX_ACTIONS)
            total_logical_qubits = int(math.log2(energies.size))
            slack_variables = total_logical_qubits - size
            binary_states = 2 ** size
            feasible_states = _feasible_state_count(size, MAX_ACTIONS)

            exact = {
                "saving_w": exact_saving,
                "exact_runtime_ms": exact_raw["runtime_ms"],
                "runtime_ms": exact_raw["runtime_ms"],
                "selected_devices": exact_solution["selected_devices"],
                "feasible": exact_solution["feasible"],
            }
            simulated_annealing = _method_result(sa_raw, "total_power_saving_w")
            simulated_annealing["sa_runtime_ms"] = simulated_annealing.pop("runtime_ms")
            local_qaoa = {
                "saving_w": qaoa_raw["saving_w"],
                "qaoa_parameter_search_runtime_ms": qaoa_raw["parameter_search_runtime_ms"],
                "qaoa_statevector_runtime_ms": qaoa_raw["runtime_ms"],
                "qaoa_total_runtime_ms": (
                    qaoa_raw["parameter_search_runtime_ms"]
                    + qaoa_raw["runtime_ms"]
                ),
                "selected_devices": qaoa_raw["selected_devices"],
                "feasible": qaoa_raw["feasible"],
                "beta": qaoa_raw["beta"],
                "gamma": qaoa_raw["gamma"],
                "parameter_combinations_evaluated": (
                    QAOA_BETA_POINTS * QAOA_GAMMA_POINTS
                ),
                "expected_qubo_energy": qaoa_raw["expected_qubo_energy"],
            }
            for method in (simulated_annealing, local_qaoa):
                method["approximation_ratio"] = method["saving_w"] / exact_saving
                method["optimality_gap_w"] = exact_saving - method["saving_w"]

            binary_growth = None
            if previous_binary_states is not None:
                binary_growth = {
                    "factor": binary_states / previous_binary_states,
                    "additional_states": binary_states - previous_binary_states,
                }
            previous_binary_states = binary_states

            instances.append({
                "candidate_count": size,
                "total_binary_states": binary_states,
                "feasible_states": feasible_states,
                "binary_state_growth_vs_previous": binary_growth,
                "qubo": {
                    "decision_variables": size,
                    "slack_variables": slack_variables,
                    "total_logical_qubits": total_logical_qubits,
                },
                "exact": exact,
                "simulated_annealing": simulated_annealing,
                "local_qaoa": local_qaoa,
            })

    return {
        "experiment": "Phase 5A controlled scalability evaluation",
        "hardware_used": False,
        "parameter_grid": "9x9",
        "max_actions": MAX_ACTIONS,
        "instances": instances,
        "methodology_note": (
            "This is a controlled local scalability experiment using the "
            "existing simulated optical-network candidate population. It does "
            "not represent physical network measurements and does not demonstrate "
            "quantum advantage. Local QAOA results use a NumPy/statevector "
            "simulation and must not be interpreted as IBM Quantum hardware results."
        ),
        "limitations": [
            "All instances are deterministic candidate prefixes from one controlled population.",
            "Runtime values are local experimental measurements and vary by machine load.",
            "Local QAOA uses a 9x9 parameter search and is not an IBM hardware measurement.",
        ],
    }


def write_report(report, report_path=DEFAULT_REPORT_PATH):
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def print_report(report):
    print("PHASE 5A CONTROLLED SCALABILITY EVALUATION")
    print("Candidates | Binary States | Feasible States | Logical Qubits | Exact ms | SA ms | QAOA Search ms | QAOA Statevector ms | QAOA Ratio")
    for instance in report["instances"]:
        print(
            f"{instance['candidate_count']} | "
            f"{instance['total_binary_states']} | "
            f"{instance['feasible_states']} | "
            f"{instance['qubo']['total_logical_qubits']} | "
            f"{instance['exact']['exact_runtime_ms']:.3f} | "
            f"{instance['simulated_annealing']['sa_runtime_ms']:.3f} | "
            f"{instance['local_qaoa']['qaoa_parameter_search_runtime_ms']:.3f} | "
            f"{instance['local_qaoa']['qaoa_statevector_runtime_ms']:.3f} | "
            f"{instance['local_qaoa']['approximation_ratio']:.6f}"
        )
    print("\nCandidates | Exact W | SA W | QAOA W | SA Ratio | QAOA Ratio")
    for instance in report["instances"]:
        print(
            f"{instance['candidate_count']} | "
            f"{instance['exact']['saving_w']:.1f} | "
            f"{instance['simulated_annealing']['saving_w']:.1f} | "
            f"{instance['local_qaoa']['saving_w']:.1f} | "
            f"{instance['simulated_annealing']['approximation_ratio']:.6f} | "
            f"{instance['local_qaoa']['approximation_ratio']:.6f}"
        )


def main():
    parser = argparse.ArgumentParser(description="Run Phase 5A scalability evaluation")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()
    report = evaluate_scalability()
    write_report(report, args.report)
    print_report(report)


if __name__ == "__main__":
    main()