"""
Quantum optimizer for optical-network power management.

Builds a QUBO from the project's real simulator devices,
preserves the exact candidate snapshot used for each QPU run,
and decodes IBM/Qiskit measurement results.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from qiskit_optimization import QuadraticProgram
from qiskit_optimization.converters import QuadraticProgramToQubo

from .models import DeviceType, PowerMode


# ============================================================
# CONFIGURATION
# ============================================================

MAX_CANDIDATES = 8
DEFAULT_MAX_ACTIONS = 4
QUBO_PENALTY = 1000


# ============================================================
# QUBO BUILDER
# ============================================================

def build_power_qubo(devices, max_actions=DEFAULT_MAX_ACTIONS):
    """
    Build a QUBO for selecting power-saving actions.

    x_i = 1 -> apply the suggested power-saving action
    x_i = 0 -> keep the current state

    Candidates are derived from the selected telemetry source. Historical
    CSV data may be analyzed, but its results are not device-control actions.
    """

    candidates = []

    for device in devices.values():

        # ----------------------------------------------------
        # TRANSPONDER -> SLEEP
        # ----------------------------------------------------
        if (
            device.type in (DeviceType.TRANSPONDER_800G, DeviceType.TRANSPONDER)
            and device.power_mode == PowerMode.NORMAL
            and device.telemetry.traffic_utilization_pct < 20
        ):
            current_power = device.telemetry.power_consumption_w
            target_power = 45.0

            candidates.append({
                "device_id": device.id,
                "device_type": device.type.value,
                "action": "SLEEP",
                "traffic": device.telemetry.traffic_utilization_pct,
                "power_saving_w": max(
                    0.0,
                    current_power - target_power
                ),
            })

        # ----------------------------------------------------
        # EDFA -> LOW GAIN
        # ----------------------------------------------------
        elif (
            device.type == DeviceType.EDFA
            and device.power_mode == PowerMode.NORMAL
            and device.telemetry.traffic_utilization_pct < 40
        ):
            current_power = device.telemetry.power_consumption_w
            target_power = 95.0

            candidates.append({
                "device_id": device.id,
                "device_type": "EDFA",
                "action": "LOW_GAIN",
                "traffic": device.telemetry.traffic_utilization_pct,
                "power_saving_w": max(
                    0.0,
                    current_power - target_power
                ),
            })

    # --------------------------------------------------------
    # LIMIT VARIABLES FOR FIRST QPU IMPLEMENTATION
    # --------------------------------------------------------

    candidates = sorted(
        candidates,
        key=lambda x: x["power_saving_w"],
        reverse=True
    )[:MAX_CANDIDATES]

    # No candidates -> nothing to optimize
    if not candidates:
        return None, []

    # --------------------------------------------------------
    # CREATE QUADRATIC PROGRAM
    # --------------------------------------------------------

    qp = QuadraticProgram(
        "optical_network_power_optimization"
    )

    # One binary variable per candidate
    for i, candidate in enumerate(candidates):
        qp.binary_var(name=f"x{i}")

    # --------------------------------------------------------
    # OBJECTIVE
    # --------------------------------------------------------
    #
    # Qiskit Optimization minimizes by default.
    #
    # We want to MAXIMIZE power savings:
    #
    #     maximize sum(saving_i * x_i)
    #
    # Therefore we minimize:
    #
    #     -sum(saving_i * x_i)
    #
    # --------------------------------------------------------

    linear = {
        f"x{i}": -candidate["power_saving_w"]
        for i, candidate in enumerate(candidates)
    }

    qp.minimize(linear=linear)

    # --------------------------------------------------------
    # CONSTRAINT
    # --------------------------------------------------------
    #
    # Select at most max_actions devices.
    #
    # Example:
    #
    # x0 + x1 + ... + x7 <= 4
    #
    # --------------------------------------------------------

    qp.linear_constraint(
        linear={
            f"x{i}": 1
            for i in range(len(candidates))
        },
        sense="<=",
        rhs=max_actions,
        name="max_power_actions"
    )

    # --------------------------------------------------------
    # CONVERT CONSTRAINED PROBLEM -> QUBO
    # --------------------------------------------------------

    qubo = QuadraticProgramToQubo(
        penalty=QUBO_PENALTY
    ).convert(qp)

    return qubo, candidates


def analyze_devices_with_local_qaoa(
    devices,
    max_actions=DEFAULT_MAX_ACTIONS,
    beta=None,
    gamma=None,
):
    """Run a local p=1 statevector analysis against the currently selected telemetry."""
    from .qaoa_parameter_optimizer import (
        DEFAULT_FIXED_BETA,
        DEFAULT_FIXED_GAMMA,
        build_qubo_energies,
        simulate_qaoa_state,
    )

    beta = DEFAULT_FIXED_BETA if beta is None else beta
    gamma = DEFAULT_FIXED_GAMMA if gamma is None else gamma
    qubo, candidates = build_power_qubo(devices, max_actions=max_actions)
    if qubo is None:
        return {
            "status": "no_candidates",
            "method": "local_qaoa_statevector",
            "candidate_count": 0,
            "candidates": [],
            "selected_devices": [],
            "num_selected": 0,
            "total_power_saving_w": 0.0,
            "feasible": True,
            "beta": beta,
            "gamma": gamma,
            "message": (
                "No devices meet the configured low-traffic and power-mode "
                "criteria, so there is no eligible QUBO to optimize."
            ),
            "qpu_used": False,
            "execution_performed": False,
        }

    candidate_snapshot = [
        {**candidate, "variable": f"x{index}"}
        for index, candidate in enumerate(candidates)
    ]
    energies = build_qubo_energies(candidates, max_actions=max_actions)
    probabilities = abs(simulate_qaoa_state(energies, beta, gamma)) ** 2
    variable_count = len(probabilities).bit_length() - 1

    best_index = None
    best_probability = -1.0
    for state_index, probability in enumerate(probabilities):
        selected = [
            candidate
            for index, candidate in enumerate(candidates)
            if (state_index >> index) & 1
        ]
        if len(selected) <= max_actions and probability > best_probability:
            best_index = state_index
            best_probability = float(probability)

    if best_index is None:
        return {
            "status": "no_feasible_solution",
            "method": "local_qaoa_statevector",
            "candidate_count": len(candidates),
            "candidates": candidate_snapshot,
            "selected_devices": [],
            "num_selected": 0,
            "total_power_saving_w": 0.0,
            "feasible": False,
            "beta": beta,
            "gamma": gamma,
            "message": "The local QAOA statevector contained no feasible solution.",
            "qpu_used": False,
            "execution_performed": False,
        }

    selected_devices = [
        candidate_snapshot[index]
        for index in range(len(candidate_snapshot))
        if (best_index >> index) & 1
    ]
    total_saving_w = sum(
        candidate["power_saving_w"] for candidate in selected_devices
    )
    return {
        "status": "success",
        "method": "local_qaoa_statevector",
        "candidate_count": len(candidates),
        "candidates": candidate_snapshot,
        "selected_devices": selected_devices,
        "num_selected": len(selected_devices),
        "total_power_saving_w": total_saving_w,
        "feasible": True,
        "highest_probability": best_probability,
        "statevector_qubits": variable_count,
        "beta": beta,
        "gamma": gamma,
        "message": (
            "Local QAOA statevector analysis completed. This result is a "
            "simulation proposal only; no QPU or device controller was used."
        ),
        "qpu_used": False,
        "execution_performed": False,
    }


# ============================================================
# QUANTUM CONNECTIVITY CHECK
# ============================================================

def quantum_optimizer_status():
    """
    Basic Qiskit quantum circuit connectivity check.
    """

    from qiskit import QuantumCircuit

    qc = QuantumCircuit(2)

    # Create a Bell state
    qc.h(0)
    qc.cx(0, 1)

    return {
        "status": "ready",
        "qubits": qc.num_qubits,
        "message": (
            "Qiskit quantum circuit initialized successfully"
        ),
    }


# ============================================================
# CANDIDATE SNAPSHOT
# ============================================================

def create_candidate_snapshot(candidates):
    """
    Preserve the exact candidate information used for a QPU run.

    This is important because simulator telemetry changes over time.
    A QPU result must always be decoded using the candidate list
    that existed when the QUBO was created.
    """

    return [
        {
            "index": i,
            "variable": f"x{i}",
            "device_id": candidate["device_id"],
            "device_type": candidate["device_type"],
            "action": candidate["action"],
            "traffic": candidate["traffic"],
            "power_saving_w": candidate["power_saving_w"],
        }
        for i, candidate in enumerate(candidates)
    ]


# ============================================================
# SAVE QPU RUN SNAPSHOT
# ============================================================

def save_candidate_snapshot(candidates):
    """
    Save the exact candidate list used for a quantum run.

    A unique run ID is generated so multiple QPU experiments
    can be stored independently.
    """

    snapshot = create_candidate_snapshot(candidates)

    run_id = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    snapshot_dir = (
        Path(__file__).resolve().parent / "quantum_runs"
    )

    snapshot_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    snapshot_path = (
        snapshot_dir / f"{run_id}_candidates.json"
    )

    snapshot_data = {
        "run_id": run_id,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "candidate_count": len(snapshot),
        "candidates": snapshot,
    }

    snapshot_path.write_text(
        json.dumps(
            snapshot_data,
            indent=2
        ),
        encoding="utf-8"
    )

    return {
        "run_id": run_id,
        "snapshot_path": str(snapshot_path),
        "candidate_count": len(snapshot),
        "candidates": snapshot,
    }


# ============================================================
# DECODE QPU BITSTRING
# ============================================================

def decode_qpu_bitstring(
    bitstring,
    candidates,
    num_qubo_variables=None,
    max_actions=DEFAULT_MAX_ACTIONS,
    variable_order=None,
    candidate_variable_names=None,
):
    """
    Decode an IBM/Qiskit measurement bitstring.

    Qiskit displays classical measurement bits in reverse order,
    so the measured string is reversed before mapping to QUBO
    variables.

    ``num_qubo_variables`` must come from the QUBO that produced the
    measurement. The candidate variables precede any converter slack bits.
    """

    # Remove spaces if present
    bitstring = bitstring.replace(" ", "")

    slack_count = (
        math.ceil(math.log2(max_actions + 1))
        if num_qubo_variables is None
        else num_qubo_variables - len(candidates)
    )
    if slack_count < 0:
        raise ValueError("QUBO variable count cannot be smaller than candidate count.")
    expected_bits = len(candidates) + slack_count

    if len(bitstring) != expected_bits:
        raise ValueError(
            f"Expected a {expected_bits}-bit QPU result, "
            f"got {len(bitstring)} bits"
        )
    if any(bit not in "01" for bit in bitstring):
        raise ValueError("QPU measurement bitstring must contain only 0 and 1.")

    candidate_variable_names = candidate_variable_names or [
        f"x{index}" for index in range(len(candidates))
    ]
    if len(candidate_variable_names) != len(candidates):
        raise ValueError("Candidate variable mapping must match the candidate count.")
    if len(set(candidate_variable_names)) != len(candidate_variable_names):
        raise ValueError("Candidate variable names must be unique.")

    if variable_order is None:
        variable_order = [
            *candidate_variable_names,
            *(f"slack{index}" for index in range(slack_count)),
        ]
    if len(variable_order) != expected_bits or len(set(variable_order)) != len(variable_order):
        raise ValueError("QUBO variable ordering does not match the measured bit count.")
    if not set(candidate_variable_names).issubset(variable_order):
        raise ValueError("Candidate variables are missing from the QUBO variable ordering.")

    # Qiskit displays count keys as cN...c0. Reversing restores the
    # classical-bit order, which is the measured QUBO variable order.
    variables = bitstring[::-1]
    variable_values = dict(zip(variable_order, variables))

    device_bits = "".join(
        variable_values[name] for name in candidate_variable_names
    )

    selected_devices = []

    for i, bit in enumerate(device_bits):

        if bit == "1":

            selected_devices.append({
                "variable": f"x{i}",
                "device_id": candidates[i]["device_id"],
                "device_type": candidates[i]["device_type"],
                "action": candidates[i]["action"],
                "traffic": candidates[i]["traffic"],
                "power_saving_w": candidates[i]["power_saving_w"],
            })

    # Calculate total estimated instantaneous saving
    total_saving_w = sum(
        device["power_saving_w"]
        for device in selected_devices
    )

    # Current QUBO constraint:
    #
    #     number of selected actions <= 4
    #
    feasible = len(selected_devices) <= max_actions

    return {
        "raw_bitstring": bitstring,
        "variable_bitstring": variables,
        "variable_values": variable_values,
        "device_bitstring": device_bits,
        "selected_devices": selected_devices,
        "num_selected": len(selected_devices),
        "total_power_saving_w": total_saving_w,
        "feasible": feasible,
    }
def run_qaoa_on_ibm_qpu(
    qubo,
    backend_name="ibm_fez",
    shots=128,
    beta=1.16898223,
    gamma=-0.14959845,
    service=None,
):
    """
    Execute the QUBO using QAOA on a real IBM Quantum processor.

    beta and gamma are the current p=1 QAOA parameters.
    """

    from qiskit import transpile
    from qiskit.circuit.library import QAOAAnsatz
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    # --------------------------------------------------------
    # CONNECT TO IBM QUANTUM
    # --------------------------------------------------------

    service = service or QiskitRuntimeService(name="optical-qpu")
    backend = service.backend(backend_name)
    backend_status = backend.status()
    if backend.simulator:
        raise RuntimeError(f"Backend {backend.name} is a simulator, not IBM hardware.")
    if not backend_status.operational:
        raise RuntimeError(
            f"Backend {backend.name} is not operational: "
            f"{backend_status.status_msg}"
        )

    # --------------------------------------------------------
    # BUILD QAOA CIRCUIT
    # --------------------------------------------------------

    ansatz = QAOAAnsatz(
        cost_operator=qubo.to_ising()[0],
        reps=1,
    )

    # Bind p=1 QAOA parameters
    parameters = list(ansatz.parameters)

    if len(parameters) != 2:
        raise RuntimeError(
            f"Expected 2 QAOA parameters for p=1, "
            f"found {len(parameters)}"
        )

    beta_parameter = next(
        (parameter for parameter in parameters if "β" in parameter.name),
        None,
    )
    gamma_parameter = next(
        (parameter for parameter in parameters if "γ" in parameter.name),
        None,
    )
    if beta_parameter is None or gamma_parameter is None:
        raise RuntimeError(
            "Could not identify the QAOA beta and gamma parameters by name."
        )
    parameter_values = {beta_parameter: beta, gamma_parameter: gamma}

    circuit = ansatz.assign_parameters(parameter_values)

    # Add measurements
    circuit.measure_all()

    # --------------------------------------------------------
    # TRANSPILE FOR REAL IBM HARDWARE
    # --------------------------------------------------------

    transpiled_circuit = transpile(
        circuit,
        backend=backend,
        optimization_level=1,
    )

    # --------------------------------------------------------
    # RUN ON REAL QPU
    # --------------------------------------------------------

    sampler = SamplerV2(
        mode=backend
    )

    job = sampler.run(
        [transpiled_circuit],
        shots=shots,
    )

    return {
        "job": job,
        "job_id": job.job_id(),
        "backend": backend.name,
        "shots": shots,
        "num_qubits": transpiled_circuit.num_qubits,
        "depth": transpiled_circuit.depth(),
        "status": str(job.status()),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "beta": beta,
        "gamma": gamma,
    }


def evaluate_qpu_counts(
    counts,
    candidates,
    num_qubo_variables=None,
    max_actions=DEFAULT_MAX_ACTIONS,
    variable_order=None,
    candidate_variable_names=None,
):
    """
    Evaluate all QPU measurement results and return the
    highest-saving feasible state.

    Parameters
    ----------
    counts : dict
        Qiskit measurement counts:
        {"bitstring": number_of_shots}

    candidates : list
        Exact candidate snapshot used to construct the QUBO.

    Returns
    -------
    dict
        Summary of the best feasible sampled solution.
    """

    total_shots = sum(counts.values())
    if total_shots <= 0:
        return {
            "status": "no_feasible_solution",
            "total_shots": 0,
            "feasible_states": 0,
            "best_solution": None,
        }

    feasible_results = []

    for bitstring, shots in counts.items():

        decoded = decode_qpu_bitstring(
            bitstring,
            candidates,
            num_qubo_variables=num_qubo_variables,
            max_actions=max_actions,
            variable_order=variable_order,
            candidate_variable_names=candidate_variable_names,
        )

        if decoded["feasible"]:
            decoded["shots"] = shots
            decoded["probability"] = shots / total_shots

            feasible_results.append(decoded)

    if not feasible_results:
        return {
            "status": "no_feasible_solution",
            "total_shots": total_shots,
            "feasible_states": 0,
            "best_solution": None,
        }

    # Highest saving first.
    # If savings are equal, prefer the state observed
    # more frequently by the QPU.
    feasible_results.sort(
        key=lambda result: (
            result["total_power_saving_w"],
            result["shots"],
        ),
        reverse=True,
    )

    best = feasible_results[0]

    return {
        "status": "success",
        "total_shots": total_shots,
        "feasible_states": len(feasible_results),
        "best_solution": best,
        "top_states": feasible_results[:10],
    }

def _load_qpu_candidate_snapshot(snapshot_path=None):
    """
    Load the exact candidate mapping used to construct the QUBO.

    QPU measurement bits are meaningful only with the candidate list
    that created that QUBO. The live simulator may change after a
    hardware job is submitted, so old QPU results must never be
    decoded from newly generated live candidates.

    Supports both snapshot formats used by this project:
      1. A raw list of candidates
      2. save_candidate_snapshot() format:
         {"run_id": ..., "candidates": [...]}
    """

    if snapshot_path is None:
        snapshot_path = (
            Path(__file__).resolve().parent
            / "quantum_runs"
            / "20260918T225129Z_candidates.json"
        )
    else:
        snapshot_path = Path(snapshot_path)

    if not snapshot_path.exists():
        raise FileNotFoundError(
            f"QPU candidate snapshot not found: {snapshot_path}"
        )

    data = json.loads(
        snapshot_path.read_text(encoding="utf-8")
    )

    if isinstance(data, dict):
        data = data.get("candidates", [])

    if not isinstance(data, list) or not data:
        raise ValueError(
            f"Invalid QPU candidate snapshot: {snapshot_path}"
        )

    normalized = []

    for i, candidate in enumerate(data):
        normalized.append({
            "index": i,
            "variable": candidate.get(
                "variable",
                f"x{i}"
            ),
            "device_id": candidate["device_id"],
            "device_type": candidate["device_type"],
            "action": candidate["action"],
            "traffic": candidate.get(
                "traffic",
                0.0
            ),
            "power_saving_w": float(
                candidate.get(
                    "power_saving_w",
                    0.0
                )
            ),
        })

    return normalized, str(snapshot_path)


def validate_qpu_solution_with_digital_twin(
    qpu_counts,
    candidates=None,
    snapshot_path=None,
    num_qubo_variables=None,
    max_actions=DEFAULT_MAX_ACTIONS,
    variable_order=None,
    candidate_variable_names=None,
):
    """
    Decode a real IBM QPU result using the exact candidate mapping
    used when that QPU job was created, then validate the complete
    selected action set together in the Digital Twin.

    QPU decoding:
        Uses the historical candidate snapshot.

    Safety validation:
        Uses CURRENT simulator telemetry.

    Execution:
        Never performed by this function.
    """

    from .models import ActionType
    from .digital_twin import digital_twin_engine
    from .telemetry import telemetry_provider

    # =========================================================
    # 1. Resolve the historical QPU candidate mapping
    # =========================================================

    try:
        if snapshot_path is not None or candidates is None:
            qpu_candidates, resolved_snapshot = (
                _load_qpu_candidate_snapshot(
                    snapshot_path
                )
            )
        else:
            # Explicit candidates are treated as a historical
            # mapping. They are NOT rebuilt from live telemetry.
            qpu_candidates = []

            for i, candidate in enumerate(candidates):
                qpu_candidates.append({
                    "index": i,
                    "variable": candidate.get(
                        "variable",
                        f"x{i}"
                    ),
                    "device_id": candidate["device_id"],
                    "device_type": candidate["device_type"],
                    "action": candidate["action"],
                    "traffic": candidate.get(
                        "traffic",
                        0.0
                    ),
                    "power_saving_w": float(
                        candidate.get(
                            "power_saving_w",
                            0.0
                        )
                    ),
                })

            resolved_snapshot = "explicit_candidate_list"

    except Exception as exc:
        return {
            "status": "REJECTED",
            "reason": (
                f"Unable to load QPU candidate mapping: {exc}"
            ),
            "qpu_solution": None,
            "digital_twin_validation": None,
            "execution_performed": False,
        }

    # =========================================================
    # 2. Decode the actual IBM QPU measurements
    # =========================================================

    try:
        evaluation = evaluate_qpu_counts(
            qpu_counts,
            qpu_candidates,
            num_qubo_variables=num_qubo_variables,
            max_actions=max_actions,
            variable_order=variable_order,
            candidate_variable_names=candidate_variable_names,
        )
    except Exception as exc:
        return {
            "status": "REJECTED",
            "reason": (
                f"Unable to decode QPU measurement: {exc}"
            ),
            "qpu_solution": None,
            "digital_twin_validation": None,
            "candidate_snapshot": resolved_snapshot,
            "execution_performed": False,
        }

    best_solution = evaluation.get(
        "best_solution"
    )

    if not best_solution:
        return {
            "status": "REJECTED",
            "reason": "No feasible solution found in QPU result.",
            "qpu_solution": None,
            "digital_twin_validation": None,
            "candidate_snapshot": resolved_snapshot,
            "execution_performed": False,
        }

    selected_devices = best_solution.get(
        "selected_devices",
        []
    )

    if not selected_devices:
        return {
            "status": "REJECTED",
            "reason": "QPU returned no selected devices.",
            "qpu_solution": best_solution,
            "digital_twin_validation": None,
            "candidate_snapshot": resolved_snapshot,
            "execution_performed": False,
        }

    # =========================================================
    # 3. Convert QPU decisions into Digital Twin actions
    # =========================================================

    actions = []

    for selected in selected_devices:
        candidate_action = selected.get("action")
        if candidate_action == "SLEEP":
            action_type = ActionType.SLEEP_TRANSPONDER
        elif candidate_action == "LOW_GAIN":
            action_type = ActionType.REDUCE_GAIN
        else:
            continue

        actions.append({
            "device_id": selected["device_id"],
            "action_type": action_type,
        })

    if not actions:
        return {
            "status": "REJECTED",
            "reason": (
                "QPU solution contained no supported "
                "device actions."
            ),
            "qpu_solution": best_solution,
            "digital_twin_validation": None,
            "candidate_snapshot": resolved_snapshot,
            "execution_performed": False,
        }

    # =========================================================
    # 4. Refresh CURRENT simulator telemetry
    #
    # This is deliberately separate from QPU decoding.
    # Historical QPU data identifies WHAT was selected.
    # Current telemetry determines WHETHER it is safe NOW.
    # =========================================================

    if telemetry_provider.source_mode == "simulator":
        telemetry_provider.tick()
    digital_twin_engine.synchronize()

    # =========================================================
    # 5. Validate ALL QPU actions together
    # =========================================================

    validation = (
        digital_twin_engine.validate_quantum_solution(
            actions
        )
    )

    # =========================================================
    # 6. Return recommendation + validation
    #
    # No live device state is modified here.
    # =========================================================

    return {
        "status": validation.get(
            "status",
            "REJECTED"
        ),
        "qpu_solution": best_solution,
        "digital_twin_validation": validation,
        "actions": actions,
        "candidate_snapshot": resolved_snapshot,
        "used_current_telemetry": True,
        "execution_performed": False,
    }
