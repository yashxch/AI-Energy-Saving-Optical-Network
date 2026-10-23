"""Exact classical baseline for the quantum optimization snapshot.

This module deliberately evaluates the saved candidate snapshot instead of
rebuilding candidates from live telemetry. That keeps the baseline aligned
with the exact decision variables used by the recorded QAOA experiment.
"""

import argparse
import itertools
import json
import time
from pathlib import Path


DEFAULT_MAX_ACTIONS = 4
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "quantum_runs"
    / "20260918T231615Z_candidates.json"
)


def load_candidate_snapshot(snapshot_path):
    """Load and validate the candidate snapshot used by the QAOA run."""
    path = Path(snapshot_path)
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    candidates = snapshot.get("candidates")

    if not isinstance(candidates, list):
        raise ValueError("Snapshot must contain a candidates list")
    if snapshot.get("candidate_count") != len(candidates):
        raise ValueError("Snapshot candidate_count does not match candidates")

    required_fields = {
        "index",
        "variable",
        "device_id",
        "device_type",
        "action",
        "traffic",
        "power_saving_w",
    }
    for position, candidate in enumerate(candidates):
        if not required_fields.issubset(candidate):
            raise ValueError(
                f"Candidate {position} is missing required snapshot fields"
            )
        if candidate["index"] != position or candidate["variable"] != f"x{position}":
            raise ValueError(
                f"Candidate {position} does not preserve the x{position} mapping"
            )

    return snapshot


def solve_exact(snapshot_path=DEFAULT_SNAPSHOT_PATH, max_actions=DEFAULT_MAX_ACTIONS):
    """Enumerate every binary device-selection state and return the optimum."""
    if max_actions < 0:
        raise ValueError("max_actions must be non-negative")

    snapshot = load_candidate_snapshot(snapshot_path)
    candidates = snapshot["candidates"]
    candidate_count = len(candidates)
    search_space_size = 2 ** candidate_count
    feasible_states = 0
    best_selection = ()
    best_saving = 0.0

    start = time.perf_counter()
    for selection in itertools.product((0, 1), repeat=candidate_count):
        selected_count = sum(selection)
        if selected_count > max_actions:
            continue

        feasible_states += 1
        total_saving = sum(
            candidate["power_saving_w"]
            for candidate, selected in zip(candidates, selection)
            if selected
        )
        if total_saving > best_saving:
            best_selection = selection
            best_saving = total_saving

    runtime_ms = (time.perf_counter() - start) * 1000
    selected_devices = [
        {
            "variable": candidate["variable"],
            "device_id": candidate["device_id"],
            "device_type": candidate["device_type"],
            "action": candidate["action"],
            "traffic": candidate["traffic"],
            "power_saving_w": candidate["power_saving_w"],
        }
        for candidate, selected in zip(candidates, best_selection)
        if selected
    ]

    return {
        "status": "success",
        "candidate_count": candidate_count,
        "search_space_size": search_space_size,
        "feasible_states": feasible_states,
        "max_actions": max_actions,
        "best_solution": {
            "selected_devices": selected_devices,
            "num_selected": len(selected_devices),
            "total_power_saving_w": best_saving,
            "feasible": len(selected_devices) <= max_actions,
        },
        "runtime_ms": runtime_ms,
        "snapshot_path": str(Path(snapshot_path)),
    }


def compare_with_qaoa(exact_result, qaoa_result):
    """Compare measured QAOA savings with the exact classical result.

    The QAOA result must be supplied by the caller; this helper never creates
    or submits a quantum result.
    """
    exact_saving = exact_result["best_solution"]["total_power_saving_w"]
    qaoa_saving = qaoa_result["total_power_saving_w"]
    if exact_saving == 0:
        approximation_ratio = None
    else:
        approximation_ratio = qaoa_saving / exact_saving

    return {
        "exact_classical_power_saving_w": exact_saving,
        "qaoa_power_saving_w": qaoa_saving,
        "absolute_saving_difference_w": abs(exact_saving - qaoa_saving),
        "approximation_ratio": approximation_ratio,
        "optimality_gap_w": exact_saving - qaoa_saving,
    }


def print_baseline(result):
    """Print the standalone evaluation summary."""
    solution = result["best_solution"]
    print("EXACT CLASSICAL BASELINE")
    print("------------------------")
    print(f"Candidates: {result['candidate_count']}")
    print(f"Search space: {result['search_space_size']}")
    print(f"Feasible states: {result['feasible_states']}")
    print("Best selected devices:")
    for device in solution["selected_devices"]:
        print(f"{device['device_id']} ({device['action']})")
    print(f"Optimal saving: {solution['total_power_saving_w']:.1f} W")
    print(f"Runtime: {result['runtime_ms']:.3f} ms")


def main():
    parser = argparse.ArgumentParser(description="Run the exact classical baseline")
    parser.add_argument(
        "snapshot",
        nargs="?",
        type=Path,
        default=DEFAULT_SNAPSHOT_PATH,
        help="candidate snapshot JSON path",
    )
    args = parser.parse_args()
    print_baseline(solve_exact(args.snapshot))


if __name__ == "__main__":
    main()