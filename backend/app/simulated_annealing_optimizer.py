"""Classical simulated-annealing baseline for the QAOA candidate snapshot.

The state contains one binary decision per snapshot candidate. The energy is
the negative total power saving plus a 1000-scale quadratic penalty for every
selection above the existing maximum-action constraint. Lower energy is
better, which is equivalent to maximizing savings among feasible states.
"""

import argparse
import math
import random
import time
from pathlib import Path

try:
    from .classical_optimizer import load_candidate_snapshot
except ImportError:
    from classical_optimizer import load_candidate_snapshot


DEFAULT_MAX_ACTIONS = 4
DEFAULT_PENALTY = 1000.0
DEFAULT_SEED = 42
DEFAULT_INITIAL_TEMPERATURE = 100.0
DEFAULT_COOLING_RATE = 0.995
DEFAULT_ITERATIONS = 1000
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "quantum_runs"
    / "20260918T231615Z_candidates.json"
)


def _energy(state, savings, max_actions, penalty):
    """Return the annealing energy for one binary device-selection state."""
    selected_count = sum(state)
    total_saving = sum(
        saving for selected, saving in zip(state, savings) if selected
    )
    excess_actions = max(0, selected_count - max_actions)
    return -total_saving + penalty * (excess_actions ** 2)


def solve_simulated_annealing(
    snapshot_path=DEFAULT_SNAPSHOT_PATH,
    max_actions=DEFAULT_MAX_ACTIONS,
    seed=DEFAULT_SEED,
    initial_temperature=DEFAULT_INITIAL_TEMPERATURE,
    cooling_rate=DEFAULT_COOLING_RATE,
    iterations=DEFAULT_ITERATIONS,
    penalty=DEFAULT_PENALTY,
):
    """Run deterministic binary-state simulated annealing."""
    if max_actions < 0:
        raise ValueError("max_actions must be non-negative")
    if initial_temperature <= 0:
        raise ValueError("initial_temperature must be positive")
    if not 0 < cooling_rate < 1:
        raise ValueError("cooling_rate must be between 0 and 1")
    if iterations < 1:
        raise ValueError("iterations must be positive")

    snapshot = load_candidate_snapshot(snapshot_path)
    candidates = snapshot["candidates"]
    savings = [candidate["power_saving_w"] for candidate in candidates]
    rng = random.Random(seed)
    state = [rng.randrange(2) for _ in candidates]
    current_energy = _energy(state, savings, max_actions, penalty)
    best_state = state[:]
    best_energy = current_energy

    start = time.perf_counter()
    for iteration in range(iterations):
        index = rng.randrange(len(state))
        state[index] = 1 - state[index]
        proposed_energy = _energy(state, savings, max_actions, penalty)
        energy_delta = proposed_energy - current_energy
        temperature = initial_temperature * (cooling_rate ** iteration)

        if energy_delta <= 0 or rng.random() < math.exp(-energy_delta / temperature):
            current_energy = proposed_energy
        else:
            state[index] = 1 - state[index]

        if current_energy < best_energy:
            best_energy = current_energy
            best_state = state[:]

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
        for candidate, selected in zip(candidates, best_state)
        if selected
    ]
    total_power_saving = sum(
        device["power_saving_w"] for device in selected_devices
    )

    return {
        "status": "success",
        "method": "simulated_annealing",
        "candidate_count": len(candidates),
        "max_actions": max_actions,
        "selected_devices": selected_devices,
        "num_selected": len(selected_devices),
        "total_power_saving_w": total_power_saving,
        "feasible": len(selected_devices) <= max_actions,
        "iterations": iterations,
        "runtime_ms": runtime_ms,
        "seed": seed,
        "initial_temperature": initial_temperature,
        "cooling_rate": cooling_rate,
        "snapshot_path": str(Path(snapshot_path)),
    }


def print_result(result):
    """Print the standalone simulated-annealing summary."""
    print("CLASSICAL SIMULATED ANNEALING")
    print("----------------------------")
    print(f"Candidates: {result['candidate_count']}")
    print(f"Maximum actions: {result['max_actions']}")
    print(f"Iterations: {result['iterations']}")
    print(f"Seed: {result['seed']}")
    print("\nSelected devices:")
    for device in result["selected_devices"]:
        print(f"{device['device_id']} ({device['action']})")
    print(f"\nPower saving: {result['total_power_saving_w']:.1f} W")
    print(f"Feasible: {'YES' if result['feasible'] else 'NO'}")
    print(f"Runtime: {result['runtime_ms']:.3f} ms")


def main():
    parser = argparse.ArgumentParser(
        description="Run the classical simulated-annealing baseline"
    )
    parser.add_argument("snapshot", nargs="?", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--initial-temperature", type=float, default=DEFAULT_INITIAL_TEMPERATURE)
    parser.add_argument("--cooling-rate", type=float, default=DEFAULT_COOLING_RATE)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    args = parser.parse_args()
    print_result(
        solve_simulated_annealing(
            snapshot_path=args.snapshot,
            seed=args.seed,
            initial_temperature=args.initial_temperature,
            cooling_rate=args.cooling_rate,
            iterations=args.iterations,
        )
    )


if __name__ == "__main__":
    main()