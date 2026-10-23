"""Multi-instance evaluation of the existing optical-network problem.

The instances in this module are controlled experimental instances generated
from the real candidate snapshot with small deterministic changes to traffic
and estimated saving values. They are not physical network measurements.

This framework evaluates exact enumeration, simulated annealing, and local
p=1 QAOA. It never imports IBM Runtime or submits an IBM Quantum job.
"""

import argparse
import json
import math
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

try:
    from .classical_optimizer import load_candidate_snapshot, solve_exact
    from .qaoa_parameter_optimizer import (
        _apply_mixer,
        build_qubo_energies,
        evaluate_parameters,
    )
    from .simulated_annealing_optimizer import solve_simulated_annealing
except ImportError:
    from classical_optimizer import load_candidate_snapshot, solve_exact
    from qaoa_parameter_optimizer import (
        _apply_mixer,
        build_qubo_energies,
        evaluate_parameters,
    )
    from simulated_annealing_optimizer import solve_simulated_annealing


INSTANCE_COUNT = 5
DEFAULT_SA_SEED = 42
DEFAULT_QAOA_BETA_POINTS = 9
DEFAULT_QAOA_GAMMA_POINTS = 9
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "quantum_runs"
    / "20260918T231615Z_candidates.json"
)
DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parent.parent
    / "quantum_runs"
    / "evaluation_report.json"
)
DEFAULT_DIAGNOSTIC_REPORT_PATH = (
    Path(__file__).resolve().parent.parent
    / "quantum_runs"
    / "qaoa_diagnostic_report.json"
)
DEFAULT_SHOT_SAMPLING_REPORT_PATH = (
    Path(__file__).resolve().parent.parent
    / "quantum_runs"
    / "qaoa_shot_sampling_report.json"
)
DIAGNOSTIC_INSTANCE_IDS = ("instance_04", "instance_05")
SHOT_COUNTS = (128, 512, 1024)
DEFAULT_SHOT_BASE_SEED = 4200


def create_controlled_instances(snapshot_path=DEFAULT_SNAPSHOT_PATH):
    """Create five deterministic variations of the saved 11-candidate list."""
    base_candidates = load_candidate_snapshot(snapshot_path)["candidates"]
    instances = []

    for instance_number in range(1, INSTANCE_COUNT + 1):
        candidates = []
        for candidate_index, candidate in enumerate(base_candidates):
            variation_code = (
                instance_number * (candidate_index + 3) + candidate_index
            ) % 5 - 2
            candidate_copy = dict(candidate)
            candidate_copy["traffic"] = round(
                candidate["traffic"] + 0.15 * variation_code,
                3,
            )
            candidate_copy["power_saving_w"] = round(
                candidate["power_saving_w"]
                + 0.35 * variation_code
                + 0.1 * (instance_number - 3),
                3,
            )
            candidates.append(candidate_copy)

        instances.append({
            "instance_id": f"instance_{instance_number:02d}",
            "candidates": candidates,
        })

    return instances


def _qaoa_statevector(energies, beta, gamma):
    """Build the p=1 state using the Phase 2 statevector formulation."""
    variable_count = int(math.log2(energies.size))
    state = np.full(
        energies.size,
        1 / math.sqrt(energies.size),
        dtype=np.complex128,
    )
    state *= np.exp(-1j * gamma * energies)
    return _apply_mixer(state, beta, variable_count)


def _local_qaoa_result(
    candidates,
    max_actions=4,
    beta_points=DEFAULT_QAOA_BETA_POINTS,
    gamma_points=DEFAULT_QAOA_GAMMA_POINTS,
):
    """Search QAOA parameters by expected QUBO energy, then decode a state."""
    energies = build_qubo_energies(candidates, max_actions=max_actions)
    beta_values = np.linspace(0.0, 2 * math.pi, beta_points, endpoint=False)
    gamma_values = np.linspace(-math.pi, math.pi, gamma_points, endpoint=False)

    search_start = time.perf_counter()
    best_parameters = None
    for beta in beta_values:
        for gamma in gamma_values:
            objective_value = evaluate_parameters(
                energies,
                float(beta),
                float(gamma),
            )
            if (
                best_parameters is None
                or objective_value < best_parameters["expected_qubo_energy"]
            ):
                best_parameters = {
                    "beta": float(beta),
                    "gamma": float(gamma),
                    "expected_qubo_energy": objective_value,
                }
    parameter_search_runtime_ms = (time.perf_counter() - search_start) * 1000

    state_start = time.perf_counter()
    state = _qaoa_statevector(
        energies,
        best_parameters["beta"],
        best_parameters["gamma"],
    )
    probabilities = np.abs(state) ** 2

    candidate_count = len(candidates)
    feasible_indices = [
        index
        for index in range(energies.size)
        if sum((index >> bit) & 1 for bit in range(candidate_count)) <= max_actions
    ]
    selected_index = max(
        feasible_indices,
        key=lambda index: (probabilities[index], -index),
    )
    selected_devices = [
        {
            "variable": candidate["variable"],
            "device_id": candidate["device_id"],
            "device_type": candidate["device_type"],
            "action": candidate["action"],
            "traffic": candidate["traffic"],
            "power_saving_w": candidate["power_saving_w"],
        }
        for bit, candidate in enumerate(candidates)
        if (selected_index >> bit) & 1
    ]
    total_power_saving = sum(
        device["power_saving_w"] for device in selected_devices
    )

    report = {
        "method": "local_qaoa",
        "selected_devices": selected_devices,
        "num_selected": len(selected_devices),
        "saving_w": total_power_saving,
        "feasible": len(selected_devices) <= max_actions,
        "beta": best_parameters["beta"],
        "gamma": best_parameters["gamma"],
        "expected_qubo_energy": best_parameters["expected_qubo_energy"],
        "runtime_ms": (time.perf_counter() - state_start) * 1000,
        "parameter_search_runtime_ms": parameter_search_runtime_ms,
        "parameter_grid": {
            "beta_points": beta_points,
            "gamma_points": gamma_points,
            "beta_range": [0.0, 2 * math.pi],
            "gamma_range": [-math.pi, math.pi],
        },
    }
    return report


def _method_record(instance_id, result, selected_devices=None):
    """Normalize solver output to the common per-method report shape."""
    if selected_devices is None:
        selected_devices = (
            result["best_solution"]["selected_devices"]
            if "best_solution" in result
            else result["selected_devices"]
        )
    saving_w = (
        result["best_solution"]["total_power_saving_w"]
        if "best_solution" in result
        else result["saving_w"]
        if "saving_w" in result
        else result["total_power_saving_w"]
    )
    feasible = (
        result["best_solution"]["feasible"]
        if "best_solution" in result
        else result["feasible"]
    )
    return {
        "instance_id": instance_id,
        "candidate_count": result["candidate_count"],
        "selected_devices": selected_devices,
        "saving_w": saving_w,
        "feasible": feasible,
        "runtime_ms": result["runtime_ms"],
    }


def _comparison(method_saving, exact_saving):
    return {
        "approximation_ratio": method_saving / exact_saving,
        "optimality_gap_w": exact_saving - method_saving,
    }


def _aggregate(method_results):
    ratios = [result["comparison"]["approximation_ratio"] for result in method_results]
    gaps = [result["comparison"]["optimality_gap_w"] for result in method_results]
    savings = [result["saving_w"] for result in method_results]
    runtimes = [result["runtime_ms"] for result in method_results]
    return {
        "average_power_saving_w": sum(savings) / len(savings),
        "average_approximation_ratio": sum(ratios) / len(ratios),
        "average_optimality_gap_w": sum(gaps) / len(gaps),
        "minimum_approximation_ratio": min(ratios),
        "maximum_approximation_ratio": max(ratios),
        "average_runtime_ms": sum(runtimes) / len(runtimes),
    }


def evaluate_instances(
    snapshot_path=DEFAULT_SNAPSHOT_PATH,
    sa_seed=DEFAULT_SA_SEED,
    sa_iterations=1000,
    qaoa_beta_points=DEFAULT_QAOA_BETA_POINTS,
    qaoa_gamma_points=DEFAULT_QAOA_GAMMA_POINTS,
):
    """Evaluate all controlled instances without writing a report file."""
    instances = create_controlled_instances(snapshot_path)
    report_instances = []

    with TemporaryDirectory(prefix="optimization-evaluation-") as temp_dir:
        for instance_number, instance in enumerate(instances, start=1):
            instance_path = Path(temp_dir) / f"{instance['instance_id']}.json"
            instance_path.write_text(
                json.dumps({
                    "run_id": instance["instance_id"],
                    "candidate_count": len(instance["candidates"]),
                    "candidates": instance["candidates"],
                }),
                encoding="utf-8",
            )

            sa_raw = solve_simulated_annealing(
                instance_path,
                seed=sa_seed + instance_number - 1,
                iterations=sa_iterations,
            )
            simulated_annealing = _method_record(instance["instance_id"], sa_raw)
            local_qaoa_raw = _local_qaoa_result(
                instance["candidates"],
                beta_points=qaoa_beta_points,
                gamma_points=qaoa_gamma_points,
            )
            local_qaoa = _method_record(
                instance["instance_id"],
                {
                    "candidate_count": len(instance["candidates"]),
                    **local_qaoa_raw,
                },
                selected_devices=local_qaoa_raw["selected_devices"],
            )
            local_qaoa["beta"] = local_qaoa_raw["beta"]
            local_qaoa["gamma"] = local_qaoa_raw["gamma"]
            local_qaoa["expected_qubo_energy"] = local_qaoa_raw["expected_qubo_energy"]
            local_qaoa["parameter_search_runtime_ms"] = local_qaoa_raw["parameter_search_runtime_ms"]
            local_qaoa["parameter_grid"] = local_qaoa_raw["parameter_grid"]

            exact_raw = solve_exact(instance_path)
            exact = _method_record(instance["instance_id"], exact_raw)

            exact_saving = exact["saving_w"]
            simulated_annealing["comparison"] = _comparison(
                simulated_annealing["saving_w"],
                exact_saving,
            )
            local_qaoa["comparison"] = _comparison(
                local_qaoa["saving_w"],
                exact_saving,
            )
            report_instances.append({
                "instance_id": instance["instance_id"],
                "candidate_count": len(instance["candidates"]),
                "max_actions": 4,
                "exact": exact,
                "simulated_annealing": simulated_annealing,
                "local_qaoa": local_qaoa,
            })

    sa_results = [item["simulated_annealing"] for item in report_instances]
    qaoa_results = [item["local_qaoa"] for item in report_instances]
    exact_results = [item["exact"] for item in report_instances]
    report = {
        "status": "success",
        "method": "multi_instance_optimization_evaluation",
        "controlled_experiment_note": (
            "This experiment uses deterministic controlled variations of the "
            "existing 11-candidate snapshot and a local NumPy statevector "
            "simulation of QAOA. These are not physical optical-network "
            "measurements and do not demonstrate quantum advantage. IBM "
            "Quantum hardware is not used in this evaluation."
        ),
        "instance_count": len(report_instances),
        "candidate_count": len(instances[0]["candidates"]),
        "local_qaoa_search": {
            "beta_points": qaoa_beta_points,
            "gamma_points": qaoa_gamma_points,
            "beta_range": [0.0, 2 * math.pi],
            "gamma_range": [-math.pi, math.pi],
            "objective": "expected QUBO energy (lower is better)",
            "method": "local NumPy statevector; not IBM QPU",
        },
        "instances": report_instances,
        "aggregate": {
            "exact_classical": {
                "average_power_saving_w": sum(
                    result["saving_w"] for result in exact_results
                ) / len(exact_results),
            },
            "simulated_annealing": _aggregate(sa_results),
            "local_qaoa": _aggregate(qaoa_results),
        },
    }

    report["aggregate"]["local_qaoa"]["average_parameter_search_runtime_ms"] = sum(
        result["parameter_search_runtime_ms"] for result in qaoa_results
    ) / len(qaoa_results)
    return report


def _diagnostic_basis_state(index, candidates, probabilities, energies):
    """Decode one full statevector basis index using x0..x10 device order."""
    selected_devices = [
        {
            "variable": candidate["variable"],
            "device_id": candidate["device_id"],
            "device_type": candidate["device_type"],
            "action": candidate["action"],
            "traffic": candidate["traffic"],
            "power_saving_w": candidate["power_saving_w"],
        }
        for bit, candidate in enumerate(candidates)
        if (index >> bit) & 1
    ]
    return {
        "bitstring": "".join(
            str((index >> bit) & 1) for bit in range(len(candidates))
        ),
        "full_state_index": index,
        "probability": float(probabilities[index]),
        "qubo_energy": float(energies[index]),
        "saving_w": sum(
            device["power_saving_w"] for device in selected_devices
        ),
        "selected_devices": selected_devices,
    }


def _diagnostic_grid_search(candidates, beta_points, gamma_points, max_actions=4):
    """Search one grid and retain statevector data for diagnostic comparisons."""
    energies = build_qubo_energies(candidates, max_actions=max_actions)
    beta_values = np.linspace(0.0, 2 * math.pi, beta_points, endpoint=False)
    gamma_values = np.linspace(-math.pi, math.pi, gamma_points, endpoint=False)
    search_start = time.perf_counter()
    best_parameters = None
    for beta in beta_values:
        for gamma in gamma_values:
            expected_energy = evaluate_parameters(
                energies,
                float(beta),
                float(gamma),
            )
            if (
                best_parameters is None
                or expected_energy < best_parameters["expected_qubo_energy"]
            ):
                best_parameters = {
                    "beta": float(beta),
                    "gamma": float(gamma),
                    "expected_qubo_energy": expected_energy,
                }
    search_runtime_ms = (time.perf_counter() - search_start) * 1000
    probabilities = np.abs(
        _qaoa_statevector(
            energies,
            best_parameters["beta"],
            best_parameters["gamma"],
        )
    ) ** 2
    candidate_count = len(candidates)
    feasible_indices = [
        index
        for index in range(energies.size)
        if sum((index >> bit) & 1 for bit in range(candidate_count)) <= max_actions
    ]
    highest_probability_index = max(
        feasible_indices,
        key=lambda index: (probabilities[index], -index),
    )
    return {
        "beta": best_parameters["beta"],
        "gamma": best_parameters["gamma"],
        "expected_qubo_energy": best_parameters["expected_qubo_energy"],
        "parameter_search_runtime_ms": search_runtime_ms,
        "beta_points": beta_points,
        "gamma_points": gamma_points,
        "beta_range": [0.0, 2 * math.pi],
        "gamma_range": [-math.pi, math.pi],
        "probabilities": probabilities,
        "energies": energies,
        "feasible_indices": feasible_indices,
        "highest_probability_index": highest_probability_index,
    }


def _diagnostic_solution_record(
    index,
    candidates,
    probabilities,
    energies,
    exact_saving,
):
    record = _diagnostic_basis_state(index, candidates, probabilities, energies)
    record["feasible"] = len(record["selected_devices"]) <= 4
    record["approximation_ratio"] = record["saving_w"] / exact_saving
    record["optimality_gap_w"] = exact_saving - record["saving_w"]
    return record


def _diagnostic_candidate_structure(candidates):
    return [
        {
            "index": candidate["index"],
            "device_id": candidate["device_id"],
            "action": candidate["action"],
            "traffic": candidate["traffic"],
            "power_saving_w": candidate["power_saving_w"],
            "qubo_linear_contribution": -candidate["power_saving_w"],
        }
        for candidate in candidates
    ]


def diagnose_qaoa_instances(
    snapshot_path=DEFAULT_SNAPSHOT_PATH,
    grid_sizes=((9, 9), (17, 17)),
):
    """Run diagnostics only for instance_04 and instance_05."""
    instances = {
        instance["instance_id"]: instance
        for instance in create_controlled_instances(snapshot_path)
        if instance["instance_id"] in DIAGNOSTIC_INSTANCE_IDS
    }
    diagnostic_instances = {}

    with TemporaryDirectory(prefix="qaoa-diagnostic-") as temp_dir:
        for instance_id in DIAGNOSTIC_INSTANCE_IDS:
            instance = instances[instance_id]
            instance_path = Path(temp_dir) / f"{instance_id}.json"
            instance_path.write_text(
                json.dumps({
                    "run_id": instance_id,
                    "candidate_count": len(instance["candidates"]),
                    "candidates": instance["candidates"],
                }),
                encoding="utf-8",
            )
            grid_results = {}
            for beta_points, gamma_points in grid_sizes:
                grid_key = f"{beta_points}x{gamma_points}"
                grid_results[grid_key] = _diagnostic_grid_search(
                    instance["candidates"],
                    beta_points,
                    gamma_points,
                )

            exact_raw = solve_exact(instance_path)
            exact = _method_record(instance_id, exact_raw)
            exact_saving = exact["saving_w"]
            serialized_grids = {}
            for grid_key, grid in grid_results.items():
                selected = _diagnostic_solution_record(
                    grid["highest_probability_index"],
                    instance["candidates"],
                    grid["probabilities"],
                    grid["energies"],
                    exact_saving,
                )
                serialized_grids[grid_key] = {
                    "beta": grid["beta"],
                    "gamma": grid["gamma"],
                    "expected_qubo_energy": grid["expected_qubo_energy"],
                    "selected_state": selected,
                    "parameter_search_runtime_ms": grid["parameter_search_runtime_ms"],
                    "feasible": selected["feasible"],
                }

            baseline_grid = grid_results["9x9"]
            baseline_feasible_indices = baseline_grid["feasible_indices"]
            positive_probability_indices = [
                index
                for index in baseline_feasible_indices
                if baseline_grid["probabilities"][index] > 0.0
            ]
            highest_probability_state = _diagnostic_solution_record(
                baseline_grid["highest_probability_index"],
                instance["candidates"],
                baseline_grid["probabilities"],
                baseline_grid["energies"],
                exact_saving,
            )
            highest_saving_index = max(
                positive_probability_indices,
                key=lambda index: (
                    _diagnostic_basis_state(
                        index,
                        instance["candidates"],
                        baseline_grid["probabilities"],
                        baseline_grid["energies"],
                    )["saving_w"],
                    baseline_grid["probabilities"][index],
                    -index,
                ),
            )
            highest_saving_state = _diagnostic_solution_record(
                highest_saving_index,
                instance["candidates"],
                baseline_grid["probabilities"],
                baseline_grid["energies"],
                exact_saving,
            )
            minimum_energy_index = min(
                positive_probability_indices,
                key=lambda index: (
                    baseline_grid["energies"][index],
                    -baseline_grid["probabilities"][index],
                    index,
                ),
            )
            minimum_energy_state = _diagnostic_solution_record(
                minimum_energy_index,
                instance["candidates"],
                baseline_grid["probabilities"],
                baseline_grid["energies"],
                exact_saving,
            )
            diagnostic_instances[instance_id] = {
                "candidate_count": len(instance["candidates"]),
                "max_actions": 4,
                "feasible_device_states": exact_raw["feasible_states"],
                "feasible_basis_states": len(baseline_feasible_indices),
                "candidate_structure": _diagnostic_candidate_structure(
                    instance["candidates"]
                ),
                "exact": exact,
                "grid_resolution": serialized_grids,
                "state_selection": {
                    "parameters_from_grid": "9x9",
                    "highest_probability_feasible": highest_probability_state,
                    "highest_saving_feasible_nonzero_probability": highest_saving_state,
                },
                "expected_energy_vs_best_sample": {
                    "expected_qubo_energy": baseline_grid["expected_qubo_energy"],
                    "minimum_qubo_energy_feasible_nonzero_probability": minimum_energy_state["qubo_energy"],
                    "minimum_energy_state_probability": minimum_energy_state["probability"],
                    "minimum_energy_state_saving_w": minimum_energy_state["saving_w"],
                    "highest_probability_feasible_probability": highest_probability_state["probability"],
                    "highest_probability_feasible_saving_w": highest_probability_state["saving_w"],
                },
            }

    instance_04 = diagnostic_instances["instance_04"]
    instance_05 = diagnostic_instances["instance_05"]
    conclusions = {
        "grid_resolution_effect": (
            "For instance_04, the 9x9 grid selected beta={:.6f}, gamma={:.6f} "
            "with {:.1f} W, while 17x17 selected beta={:.6f}, gamma={:.6f} "
            "with {:.1f} W. For instance_05, the corresponding savings were "
            "{:.1f} W and {:.1f} W."
        ).format(
            instance_04["grid_resolution"]["9x9"]["beta"],
            instance_04["grid_resolution"]["9x9"]["gamma"],
            instance_04["grid_resolution"]["9x9"]["selected_state"]["saving_w"],
            instance_04["grid_resolution"]["17x17"]["beta"],
            instance_04["grid_resolution"]["17x17"]["gamma"],
            instance_04["grid_resolution"]["17x17"]["selected_state"]["saving_w"],
            instance_05["grid_resolution"]["9x9"]["selected_state"]["saving_w"],
            instance_05["grid_resolution"]["17x17"]["selected_state"]["saving_w"],
        ),
        "state_selection_effect": (
            "Using the 9x9 parameters, the highest-probability feasible and "
            "highest-saving feasible non-zero-probability states had savings "
            "of {:.1f} W and {:.1f} W for instance_04, and {:.1f} W and {:.1f} W "
            "for instance_05."
        ).format(
            instance_04["state_selection"]["highest_probability_feasible"]["saving_w"],
            instance_04["state_selection"]["highest_saving_feasible_nonzero_probability"]["saving_w"],
            instance_05["state_selection"]["highest_probability_feasible"]["saving_w"],
            instance_05["state_selection"]["highest_saving_feasible_nonzero_probability"]["saving_w"],
        ),
        "primary_observation": (
            "The diagnostic numerically separates parameter-grid effects from "
            "state-selection effects using expected QUBO energy, statevector "
            "probabilities, and feasible-state savings; it makes no hardware "
            "performance or advantage claim."
        ),
    }
    return {
        "experiment": "Phase 4.2 QAOA diagnostic",
        "hardware_used": False,
        "note": (
            "This is a local statevector diagnostic experiment. It does not "
            "use IBM Quantum hardware and does not demonstrate quantum advantage."
        ),
        "instances": diagnostic_instances,
        "conclusion": conclusions,
    }


def write_diagnostic_report(report, report_path=DEFAULT_DIAGNOSTIC_REPORT_PATH):
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def print_diagnostic_report(report):
    print("\nQAOA DIAGNOSTIC: INSTANCE_04 AND INSTANCE_05")
    print("Instance | Grid | Beta | Gamma | Selected Saving | Ratio | Gap | Search Runtime")
    for instance_id, instance in report["instances"].items():
        for grid, result in instance["grid_resolution"].items():
            selected = result["selected_state"]
            print(
                f"{instance_id} | {grid} | {result['beta']:.6f} | "
                f"{result['gamma']:.6f} | {selected['saving_w']:.1f} | "
                f"{selected['approximation_ratio']:.6f} | "
                f"{selected['optimality_gap_w']:.1f} | "
                f"{result['parameter_search_runtime_ms']:.3f} ms"
            )
    print("\nInstance | Selection Rule | Saving | Ratio | Gap | Probability")
    for instance_id, instance in report["instances"].items():
        for label, result in (
            ("highest-probability feasible", instance["state_selection"]["highest_probability_feasible"]),
            ("highest-saving feasible nonzero", instance["state_selection"]["highest_saving_feasible_nonzero_probability"]),
        ):
            print(
                f"{instance_id} | {label} | {result['saving_w']:.1f} | "
                f"{result['approximation_ratio']:.6f} | "
                f"{result['optimality_gap_w']:.1f} | {result['probability']:.8f}"
            )


def _sample_local_qaoa_distribution(
    candidates,
    beta,
    gamma,
    shots,
    seed,
    max_actions=4,
):
    """Sample exactly ``shots`` outcomes and select only observed feasible states."""
    energies = build_qubo_energies(candidates, max_actions=max_actions)
    probabilities = np.abs(_qaoa_statevector(energies, beta, gamma)) ** 2
    rng = np.random.default_rng(seed)
    samples = rng.choice(len(probabilities), size=shots, p=probabilities)
    observed_counts = {}
    for sample in samples:
        state_index = int(sample)
        observed_counts[state_index] = observed_counts.get(state_index, 0) + 1

    device_observed_counts = {}
    device_representative_indices = {}
    for state_index, count in observed_counts.items():
        device_bitstring = "".join(
            str((state_index >> bit) & 1) for bit in range(len(candidates))
        )
        device_observed_counts[device_bitstring] = (
            device_observed_counts.get(device_bitstring, 0) + count
        )
        device_representative_indices.setdefault(device_bitstring, state_index)

    feasible_bitstrings = [
        bitstring
        for bitstring in device_observed_counts
        if bitstring.count("1") <= max_actions
    ]
    feasible_observations = sum(
        device_observed_counts[bitstring] for bitstring in feasible_bitstrings
    )
    result = {
        "shots": shots,
        "seed": seed,
        "total_sampled_shots": shots,
        "feasible_observations": feasible_observations,
        "feasible_shot_percentage": feasible_observations / shots * 100,
        "unique_observed_bitstrings": len(device_observed_counts),
        "selection_source": "observed feasible samples only",
        "observed_bitstring_counts": {
            bitstring: device_observed_counts[bitstring]
            for bitstring in sorted(device_observed_counts)
        },
    }

    if not feasible_bitstrings:
        result.update({
            "best_observed_saving_w": 0.0,
            "saving_w": 0.0,
            "approximation_ratio": 0.0,
            "optimality_gap_w": None,
            "selected_devices": [],
            "selected_bitstring": None,
            "observed_probability": 0.0,
            "no_feasible_solution_observed": True,
        })
        return result

    selected_bitstring = max(
        feasible_bitstrings,
        key=lambda bitstring: (
            sum(
                candidate["power_saving_w"]
                for bit, candidate in enumerate(candidates)
                if bitstring[bit] == "1"
            ),
            device_observed_counts[bitstring],
            -device_representative_indices[bitstring],
        ),
    )
    selected_index = device_representative_indices[selected_bitstring]
    selected_state = _diagnostic_basis_state(
        selected_index,
        candidates,
        probabilities,
        energies,
    )
    result.update({
        "best_observed_saving_w": selected_state["saving_w"],
        "saving_w": selected_state["saving_w"],
        "selected_devices": selected_state["selected_devices"],
        "selected_bitstring": selected_bitstring,
        "observed_probability": device_observed_counts[selected_bitstring] / shots,
        "no_feasible_solution_observed": False,
    })
    return result


def _add_posthoc_sampling_metrics(result, exact_saving):
    """Calculate exact-relative metrics only after sampled selection is complete."""
    result["approximation_ratio"] = result["saving_w"] / exact_saving
    result["optimality_gap_w"] = exact_saving - result["saving_w"]
    result["exact_optimum_match"] = math.isclose(
        result["saving_w"],
        exact_saving,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    return result


def _shot_aggregate(results):
    ratios = [result["approximation_ratio"] for result in results]
    gaps = [result["optimality_gap_w"] for result in results]
    savings = [result["saving_w"] for result in results]
    return {
        "average_saving_w": sum(savings) / len(savings),
        "average_approximation_ratio": sum(ratios) / len(ratios),
        "average_optimality_gap_w": sum(gaps) / len(gaps),
        "minimum_approximation_ratio": min(ratios),
        "maximum_approximation_ratio": max(ratios),
        "feasible_instances": sum(
            not result["no_feasible_solution_observed"] for result in results
        ),
        "exact_optimum_matches": sum(
            result["exact_optimum_match"] for result in results
        ),
    }


def run_shot_sampling_diagnostic(
    snapshot_path=DEFAULT_SNAPSHOT_PATH,
    shot_counts=SHOT_COUNTS,
    base_seed=DEFAULT_SHOT_BASE_SEED,
):
    """Run finite-shot sampling for all five controlled instances."""
    instances = create_controlled_instances(snapshot_path)
    report_instances = {}
    results_by_shots = {str(shots): [] for shots in shot_counts}

    with TemporaryDirectory(prefix="qaoa-shot-sampling-") as temp_dir:
        for instance_index, instance in enumerate(instances, start=1):
            instance_id = instance["instance_id"]
            instance_path = Path(temp_dir) / f"{instance_id}.json"
            instance_path.write_text(
                json.dumps({
                    "run_id": instance_id,
                    "candidate_count": len(instance["candidates"]),
                    "candidates": instance["candidates"],
                }),
                encoding="utf-8",
            )

            qaoa_parameters = _local_qaoa_result(instance["candidates"])
            sampled_results = {}
            for shots in shot_counts:
                seed = base_seed + instance_index + shots
                sampled_results[str(shots)] = _sample_local_qaoa_distribution(
                    instance["candidates"],
                    qaoa_parameters["beta"],
                    qaoa_parameters["gamma"],
                    shots,
                    seed,
                )

            # Exact enumeration is deliberately performed after sampling and
            # only supplies the evaluation denominator and post hoc gap.
            exact_raw = solve_exact(instance_path)
            exact = _method_record(instance_id, exact_raw)
            exact_saving = exact["saving_w"]
            for shots_key, sampled in sampled_results.items():
                _add_posthoc_sampling_metrics(sampled, exact_saving)
                results_by_shots[shots_key].append(sampled)

            report_instances[instance_id] = {
                "candidate_count": len(instance["candidates"]),
                "max_actions": 4,
                "beta": qaoa_parameters["beta"],
                "gamma": qaoa_parameters["gamma"],
                "expected_qubo_energy": qaoa_parameters["expected_qubo_energy"],
                "parameter_search_runtime_ms": qaoa_parameters["parameter_search_runtime_ms"],
                "exact": exact,
                "shot_results": sampled_results,
            }

    aggregates = {
        shots_key: _shot_aggregate(results)
        for shots_key, results in results_by_shots.items()
    }
    improvements = {}
    for previous_shots, current_shots in ((128, 512), (512, 1024)):
        previous = aggregates[str(previous_shots)]
        current = aggregates[str(current_shots)]
        improvements[f"{previous_shots}_to_{current_shots}"] = {
            "average_saving_change_w": current["average_saving_w"] - previous["average_saving_w"],
            "average_approximation_ratio_change": (
                current["average_approximation_ratio"]
                - previous["average_approximation_ratio"]
            ),
            "average_optimality_gap_change_w": (
                current["average_optimality_gap_w"]
                - previous["average_optimality_gap_w"]
            ),
        }

    return {
        "experiment": "Phase 4.3 finite-shot local QAOA sampling diagnostic",
        "hardware_used": False,
        "instances": report_instances,
        "aggregates_by_shots": aggregates,
        "shot_count_improvements": improvements,
        "methodology_note": (
            "This is a local statevector probability-sampling experiment. It "
            "does not execute on IBM Quantum hardware and does not demonstrate "
            "quantum advantage. Finite-shot sampling approximates the measurement "
            "process of a quantum processor."
        ),
        "limitations": [
            "The instances are controlled deterministic variations, not physical measurements.",
            "The local statevector distribution is sampled classically; no IBM hardware noise is modeled.",
            "Observed feasible solutions depend on the deterministic finite-shot seeds and shot counts.",
        ],
        "base_seed": base_seed,
        "shot_counts": list(shot_counts),
    }


def write_shot_sampling_report(
    report,
    report_path=DEFAULT_SHOT_SAMPLING_REPORT_PATH,
):
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def print_shot_sampling_report(report):
    print("\nLOCAL QAOA FINITE-SHOT SAMPLING")
    print("Instance | Shots | Best Observed W | Ratio | Gap | Feasible Shots | Selected Devices")
    for instance_id, instance in report["instances"].items():
        for shots in report["shot_counts"]:
            result = instance["shot_results"][str(shots)]
            selected_ids = ", ".join(
                device["device_id"] for device in result["selected_devices"]
            ) or "NONE"
            print(
                f"{instance_id} | {shots} | {result['saving_w']:.1f} | "
                f"{result['approximation_ratio']:.6f} | "
                f"{result['optimality_gap_w']:.1f} | "
                f"{result['feasible_observations']} | {selected_ids}"
            )
    print("\nShots | Avg Saving | Avg Ratio | Avg Gap | Feasible Instances | Exact Optimum Matches")
    for shots in report["shot_counts"]:
        aggregate = report["aggregates_by_shots"][str(shots)]
        print(
            f"{shots} | {aggregate['average_saving_w']:.3f} | "
            f"{aggregate['average_approximation_ratio']:.6f} | "
            f"{aggregate['average_optimality_gap_w']:.3f} | "
            f"{aggregate['feasible_instances']} | "
            f"{aggregate['exact_optimum_matches']}"
        )


def write_report(report, report_path=DEFAULT_REPORT_PATH):
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def print_report(report):
    print("MULTI-INSTANCE OPTIMIZATION EVALUATION")
    print("--------------------------------------")
    print("Instance | Exact W | SA W | Local QAOA W | QAOA Ratio | QAOA Gap | Beta | Gamma")
    for instance in report["instances"]:
        qaoa = instance["local_qaoa"]
        print(
            f"{instance['instance_id']} | "
            f"{instance['exact']['saving_w']:.1f} | "
            f"{instance['simulated_annealing']['saving_w']:.1f} | "
            f"{qaoa['saving_w']:.1f} | "
            f"{qaoa['comparison']['approximation_ratio']:.6f} | "
            f"{qaoa['comparison']['optimality_gap_w']:.1f} | "
            f"{qaoa['beta']:.6f} | "
            f"{qaoa['gamma']:.6f}"
        )
    exact_average = report["aggregate"]["exact_classical"]["average_power_saving_w"]
    sa_aggregate = report["aggregate"]["simulated_annealing"]
    qaoa_aggregate = report["aggregate"]["local_qaoa"]
    print("\nAverage power saving:")
    print(f"Exact: {exact_average:.3f} W")
    print(f"SA: {sa_aggregate['average_power_saving_w']:.3f} W")
    print(f"LOCAL QAOA: {qaoa_aggregate['average_power_saving_w']:.3f} W")
    print("\nAverage approximation ratio:")
    print(f"SA: {sa_aggregate['average_approximation_ratio']:.6f}")
    print(f"LOCAL QAOA: {qaoa_aggregate['average_approximation_ratio']:.6f}")
    print("\nAverage optimality gap:")
    print(f"SA: {sa_aggregate['average_optimality_gap_w']:.3f} W")
    print(f"LOCAL QAOA: {qaoa_aggregate['average_optimality_gap_w']:.3f} W")
    print("\nLOCAL QAOA ratio range:")
    print(
        f"{qaoa_aggregate['minimum_approximation_ratio']:.6f}"
        f" - {qaoa_aggregate['maximum_approximation_ratio']:.6f}"
    )
    print("\nAverage runtime:")
    print(f"SA: {sa_aggregate['average_runtime_ms']:.3f} ms")
    print(f"LOCAL QAOA statevector: {qaoa_aggregate['average_runtime_ms']:.3f} ms")
    print(
        "LOCAL QAOA parameter search: "
        f"{qaoa_aggregate['average_parameter_search_runtime_ms']:.3f} ms"
    )


def main():
    parser = argparse.ArgumentParser(description="Run the multi-instance evaluation")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument(
        "--diagnostic-report",
        type=Path,
        default=DEFAULT_DIAGNOSTIC_REPORT_PATH,
    )
    parser.add_argument(
        "--shot-sampling-report",
        type=Path,
        default=DEFAULT_SHOT_SAMPLING_REPORT_PATH,
    )
    args = parser.parse_args()
    report = evaluate_instances()
    write_report(report, args.report)
    print_report(report)
    diagnostic_report = diagnose_qaoa_instances()
    write_diagnostic_report(diagnostic_report, args.diagnostic_report)
    print_diagnostic_report(diagnostic_report)
    shot_sampling_report = run_shot_sampling_diagnostic()
    write_shot_sampling_report(shot_sampling_report, args.shot_sampling_report)
    print_shot_sampling_report(shot_sampling_report)


if __name__ == "__main__":
    main()