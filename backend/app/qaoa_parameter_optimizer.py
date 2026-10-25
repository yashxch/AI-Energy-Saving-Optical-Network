"""Local, classical parameter search for the existing p=1 QAOA problem.

The production path builds ``QuadraticProgramToQubo(penalty=1000).convert``
and passes ``qubo.to_ising()[0]`` to ``QAOAAnsatz(reps=1)``. This module keeps
that path untouched and evaluates the equivalent diagonal QUBO directly with
a NumPy statevector simulator. The constant shift between QUBO and Ising
forms does not affect the QAOA state or which parameters minimize energy.

The objective is expected QUBO energy, so lower is better. This is a local
deterministic grid search, not a claim of global parameter optimality.
"""

import argparse
import math
import time
from pathlib import Path

import numpy as np

try:
    from .classical_optimizer import load_candidate_snapshot
except ImportError:
    from classical_optimizer import load_candidate_snapshot


DEFAULT_FIXED_BETA = 1.16898223
DEFAULT_FIXED_GAMMA = -0.14959845
DEFAULT_PENALTY = 1000.0
DEFAULT_MAX_ACTIONS = 4
DEFAULT_BETA_POINTS = 9
DEFAULT_GAMMA_POINTS = 9
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "quantum_runs"
    / "20260918T231615Z_candidates.json"
)


def build_qubo_energies(
    candidates,
    max_actions=DEFAULT_MAX_ACTIONS,
    penalty=DEFAULT_PENALTY,
):
    """Build the diagonal energies of the same 14-variable QUBO.

    The existing inequality is ``sum(x_i) <= 4``. Its Qiskit QUBO
    conversion introduces three binary slack variables with weights 1, 2,
    and 4, yielding the penalty ``1000 * (sum(x) + slack - 4)^2``.
    """
    candidate_count = len(candidates)
    slack_count = math.ceil(math.log2(max_actions + 1))
    variable_count = candidate_count + slack_count
    state_count = 2 ** variable_count
    indices = np.arange(state_count, dtype=np.int64)

    device_bits = np.array(
        [(indices >> bit) & 1 for bit in range(candidate_count)],
        dtype=np.float64,
    )
    slack_bits = np.array(
        [(indices >> bit) & 1 for bit in range(candidate_count, variable_count)],
        dtype=np.float64,
    )
    selected_count = device_bits.sum(axis=0)
    slack_value = sum(
        (2 ** offset) * slack_bits[offset]
        for offset in range(slack_count)
    )
    savings = np.array(
        [candidate["power_saving_w"] for candidate in candidates],
        dtype=np.float64,
    )
    objective = -(savings[:, None] * device_bits).sum(axis=0)
    constraint_penalty = penalty * (selected_count + slack_value - max_actions) ** 2

    return objective + constraint_penalty


def _apply_mixer(state, beta, variable_count):
    """Apply the p=1 product mixer exp(-i * beta * sum(X))."""
    cosine = math.cos(beta)
    minus_i_sine = -1j * math.sin(beta)
    for bit in range(variable_count):
        partner = np.arange(state.size) ^ (1 << bit)
        state = cosine * state + minus_i_sine * state[partner]
    return state


def simulate_qaoa_state(energies, beta, gamma):
    """Return the p=1 statevector for one QUBO and parameter pair."""
    variable_count = int(math.log2(energies.size))
    state = np.full(
        energies.size,
        1 / math.sqrt(energies.size),
        dtype=np.complex128,
    )
    state *= np.exp(-1j * gamma * energies)
    return _apply_mixer(state, beta, variable_count)


def evaluate_parameters(energies, beta, gamma):
    """Return expected QUBO energy for one p=1 parameter pair."""
    state = simulate_qaoa_state(energies, beta, gamma)
    probabilities = np.abs(state) ** 2
    return float(np.dot(probabilities, energies).real)


def _grid_values(start, stop, points):
    if points < 2:
        raise ValueError("grid points must be at least 2")
    return np.linspace(start, stop, points, dtype=np.float64)


def optimize_parameters(
    snapshot_path=DEFAULT_SNAPSHOT_PATH,
    beta_points=DEFAULT_BETA_POINTS,
    gamma_points=DEFAULT_GAMMA_POINTS,
    fixed_beta=DEFAULT_FIXED_BETA,
    fixed_gamma=DEFAULT_FIXED_GAMMA,
):
    """Search a reproducible beta/gamma grid and evaluate fixed parameters."""
    snapshot = load_candidate_snapshot(snapshot_path)
    candidates = snapshot["candidates"]
    energies = build_qubo_energies(candidates)
    beta_values = _grid_values(0.0, 2 * math.pi, beta_points)
    gamma_values = _grid_values(-math.pi, math.pi, gamma_points)

    start = time.perf_counter()
    fixed_objective = evaluate_parameters(energies, fixed_beta, fixed_gamma)
    best_parameters = None
    evaluations = 0

    for beta in beta_values:
        for gamma in gamma_values:
            objective = evaluate_parameters(energies, float(beta), float(gamma))
            evaluations += 1
            if best_parameters is None or objective < best_parameters["objective_value"]:
                best_parameters = {
                    "beta": float(beta),
                    "gamma": float(gamma),
                    "objective_value": objective,
                }

    runtime_ms = (time.perf_counter() - start) * 1000
    improvement = fixed_objective - best_parameters["objective_value"]
    return {
        "status": "success",
        "method": "classical_grid_search",
        "objective": "expected QUBO energy (lower is better)",
        "candidate_count": len(candidates),
        "qubo_variables": int(math.log2(energies.size)),
        "grid_size": {
            "beta_points": beta_points,
            "gamma_points": gamma_points,
            "total_evaluations": evaluations,
            "beta_range": [0.0, 2 * math.pi],
            "gamma_range": [-math.pi, math.pi],
        },
        "fixed_parameters": {
            "beta": fixed_beta,
            "gamma": fixed_gamma,
            "objective_value": fixed_objective,
        },
        "optimized_parameters": best_parameters,
        "improvement": improvement,
        "runtime_ms": runtime_ms,
        "snapshot_path": str(Path(snapshot_path)),
    }


def print_result(result):
    """Print the standalone local parameter-search summary."""
    fixed = result["fixed_parameters"]
    optimized = result["optimized_parameters"]
    print("QAOA PARAMETER OPTIMIZATION")
    print("---------------------------")
    print(f"Candidates: {result['candidate_count']}")
    print(f"QUBO variables: {result['qubo_variables']}")
    print("\nCurrent parameters:")
    print(f"beta = {fixed['beta']}")
    print(f"gamma = {fixed['gamma']}")
    print(f"objective = {fixed['objective_value']:.6f}")
    print("\nOptimized parameters:")
    print(f"beta = {optimized['beta']}")
    print(f"gamma = {optimized['gamma']}")
    print(f"objective = {optimized['objective_value']:.6f}")
    print("\nImprovement:")
    print(f"{result['improvement']:.6f} lower expected QUBO energy")
    print("\nRuntime:")
    print(f"{result['runtime_ms']:.3f} ms")


def main():
    parser = argparse.ArgumentParser(description="Run local QAOA parameter search")
    parser.add_argument("snapshot", nargs="?", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--beta-points", type=int, default=DEFAULT_BETA_POINTS)
    parser.add_argument("--gamma-points", type=int, default=DEFAULT_GAMMA_POINTS)
    args = parser.parse_args()
    print_result(
        optimize_parameters(
            args.snapshot,
            beta_points=args.beta_points,
            gamma_points=args.gamma_points,
        )
    )


if __name__ == "__main__":
    main()