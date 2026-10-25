import sys

# Use the active Python environment instead of forcing a stale local
# quantum environment onto sys.path; that environment can shadow the
# dependencies installed for this project.

import asyncio
import json
import time
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from .models import (
    Device,
    Recommendation,
    TrafficPrediction,
    AnomalyItem,
    FCAPSAlarm,
    FCAPSEnergyAccounting,
    FCAPSSecurityLog,
    ChatRequest,
    ChatResponse,
    ActionExecutionRequest,
    PowerMode,
    TopologyStateModel,
    RotateTopologyRequest,
    SetTopologyPatternRequest,
    DigitalTwinDevice,
    DigitalTwinStateSummary,
    DigitalTwinTopologyGraph,
    WhatIfSimulationRequest,
    WhatIfSimulationResponse,
    SimulationHistoryItem,
    DemoScenarioInfo,
    ActionType,
    NokiaThresholdResult
)

from .simulator import simulator
from .ml_engine import ml_engine
from .llm_engine import llm_engine
from .policy_engine import policy_engine
from .fcaps import fcaps_manager
from .digital_twin import digital_twin_engine
from .quantum_optimizer import (
    analyze_devices_with_local_qaoa,
    build_power_qubo,
    evaluate_qpu_counts,
    QUBO_PENALTY,
    run_qaoa_on_ibm_qpu,
    validate_qpu_solution_with_digital_twin,
)
from .adaptive_baseline import adaptive_baseline_manager
from .telemetry import telemetry_provider
from .thresholds import NokiaThresholdEvaluator


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AI-Based Power Saving in Optical Networks API",
    description=(
        "Nokia 1830 PSS style optical transport network simulation "
        "and AI energy optimization engine."
    ),
    version="1.0.0"
)

adaptive_baseline = adaptive_baseline_manager
nokia_thresholds = NokiaThresholdEvaluator()
quantum_runs = {}
quantum_run_storage = Path(__file__).resolve().parent.parent / ".quantum_runs"


def _persist_quantum_run(run_id, run):
    stored_run = {
        key: value
        for key, value in run.items()
        if key != "job"
    }
    quantum_run_storage.mkdir(parents=True, exist_ok=True)
    target = quantum_run_storage / f"{run_id}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(stored_run), encoding="utf-8")
    temporary.replace(target)


def _restore_quantum_run(run_id):
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        return None
    metadata_path = quantum_run_storage / f"{run_id}.json"
    if not metadata_path.is_file():
        return None

    try:
        stored_run = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Could not read persisted run metadata: {exc}") from exc

    required_fields = {
        "job_id",
        "candidates",
        "num_qubo_variables",
        "qubo_variable_names",
        "candidate_variable_names",
        "measurement_bit_order",
        "qaoa_beta",
        "qaoa_gamma",
        "max_actions",
        "source",
    }
    if not required_fields.issubset(stored_run):
        raise RuntimeError("Persisted run metadata is incomplete.")

    from qiskit_ibm_runtime import QiskitRuntimeService

    service = QiskitRuntimeService(name="optical-qpu")
    stored_run["job"] = service.job(stored_run["job_id"])
    quantum_runs[run_id] = stored_run
    return stored_run


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# QUANTUM OPTIMIZATION
# ============================================================

@app.get("/api/quantum/validate")
def validate_quantum_result():
    raise HTTPException(
        status_code=410,
        detail="This endpoint is retired. Retrieve a known IBM job with GET /api/quantum/job/{job_id}.",
    )

@app.get("/api/quantum/analyze")
def analyze_current_telemetry_with_local_qaoa():
    """Analyze eligible actions from the selected source without using a QPU."""
    result = analyze_devices_with_local_qaoa(telemetry_provider.get_devices())
    status = telemetry_provider.nokia_adapter.get_uploaded_csv_status()
    durations = [
        device.get("observation_duration_seconds", 0.0)
        for device in status.get("devices", {}).values()
    ]
    return {
        **result,
        "source": telemetry_provider.source_mode,
        "data_origin": (
            telemetry_provider.nokia_adapter.data_origin
            if telemetry_provider.source_mode == "nokia"
            else "simulator"
        ),
        "minimum_observation_seconds": telemetry_provider.nokia_adapter.minimum_power_observation_sec,
        "observation_durations_seconds": durations,
        "execution_performed": False,
        "qpu_used": False,
    }


@app.get("/api/quantum/job/{job_id}")
def retrieve_existing_quantum_job(job_id: str):
    """Retrieve an existing IBM job without submitting a replacement."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", job_id):
        raise HTTPException(status_code=422, detail="Invalid IBM job ID format.")

    for run_id, run in quantum_runs.items():
        if run["job_id"] == job_id:
            return get_quantum_optimization_run(run_id)

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService

        service = QiskitRuntimeService(name="optical-qpu")
        job = service.job(job_id)
        raw_status = job.status()
        job_status = getattr(
            raw_status,
            "name",
            str(raw_status).split(".")[-1],
        ).upper()
        backend = job.backend()
        backend_name = getattr(backend, "name", str(backend))
        created_at = getattr(job, "creation_date", None)
        if callable(created_at):
            created_at = created_at()
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        elif created_at is not None:
            created_at = str(created_at)
    except Exception as exc:
        return {
            "job_id": job_id,
            "execution_method": "ibm_qpu",
            "status": "error",
            "metadata_available": False,
            "result_retrieved": False,
            "error_type": type(exc).__name__,
            "error": _quantum_error_message(exc),
            "message": "Could not retrieve this IBM job. No replacement job was submitted.",
            "execution_performed": False,
        }

    if job_status in {"DONE", "COMPLETED"}:
        try:
            result = job.result()
            counts = result[0].data.meas.get_counts()
            shot_count = sum(counts.values())
            response = {
                "job_id": job_id,
                "execution_method": "ibm_qpu",
                "backend": backend_name,
                "job_status": job_status,
                "status": "completed",
                "submitted_at": created_at,
                "metadata_available": False,
                "result_retrieved": True,
                "shots": shot_count,
                "measurement_counts": counts,
                "decoded_solution": None,
                "recommendations": [],
                "selected_action_count": None,
                "total_estimated_power_saving_w": None,
                "validation_status": None,
                "message": (
                    "IBM returned a completed measurement result, but this job's "
                    "candidate/QUBO metadata was not persisted. Measurements are "
                    "shown without decoding or recommendations."
                ),
                "execution_performed": False,
            }
        except Exception as exc:
            response = {
                "job_id": job_id,
                "execution_method": "ibm_qpu",
                "backend": backend_name,
                "job_status": job_status,
                "status": "error",
                "submitted_at": created_at,
                "metadata_available": False,
                "result_retrieved": False,
                "error_type": type(exc).__name__,
                "error": _quantum_error_message(exc),
                "message": "IBM reports completion, but the measurement result could not be retrieved.",
                "execution_performed": False,
            }
        return response

    if job_status in {"ERROR", "FAILED"}:
        status = "failed"
    elif job_status in {"CANCELLED", "CANCELED"}:
        status = "cancelled"
    elif job_status == "RUNNING":
        status = "running"
    else:
        status = "queued"

    return {
        "job_id": job_id,
        "execution_method": "ibm_qpu",
        "backend": backend_name,
        "job_status": job_status,
        "status": status,
        "submitted_at": created_at,
        "metadata_available": False,
        "result_retrieved": False,
        "message": (
            f"Existing IBM job status: {job_status}. "
            "No replacement job was submitted."
        ),
        "execution_performed": False,
    }


def _quantum_error_message(exc: Exception) -> str:
    return re.sub(
        r"(?i)(token|api[-_ ]?key|authorization)(\s*[:=]\s*)[^,\s]+",
        r"\1\2[REDACTED]",
        str(exc),
    )


def _preflight_quantum_candidates(devices, candidates):
    from .models import DeviceType

    allowed_ids = set()
    rejections = []
    digital_twin_engine.synchronize()

    for candidate in candidates:
        device = devices.get(candidate["device_id"])
        if (
            candidate["action"] == "SLEEP"
            and device is not None
            and device.type == DeviceType.TRANSPONDER_800G
        ):
            action_type = ActionType.SLEEP_TRANSPONDER
        elif (
            candidate["action"] == "LOW_GAIN"
            and device is not None
            and device.type == DeviceType.EDFA
        ):
            action_type = ActionType.REDUCE_GAIN
        else:
            rejections.append({
                "device_id": candidate["device_id"],
                "reason": "No supported Digital Twin action is defined for this candidate.",
            })
            continue

        validation = digital_twin_engine.validate_quantum_solution([{
            "device_id": candidate["device_id"],
            "action_type": action_type,
        }])
        action_result = (validation.get("actions") or [{}])[0]
        if action_result.get("result") == "APPROVED":
            allowed_ids.add(candidate["device_id"])
        else:
            rejections.append({
                "device_id": candidate["device_id"],
                "reason": action_result.get("reason", validation.get("reason")),
            })

    return allowed_ids, rejections


@app.post("/api/quantum/run")
def start_quantum_optimization(
    shots: int = Query(default=128, ge=32, le=1024),
):
    source = telemetry_provider.source_mode
    data_origin = (
        telemetry_provider.nokia_adapter.data_origin
        if source == "nokia"
        else "simulator"
    )
    if source == "nokia" and telemetry_provider.nokia_adapter.is_historical_csv:
        return {
            "status": "no_candidates",
            "execution_method": "ibm_qpu",
            "source": source,
            "data_origin": data_origin,
            "eligible_candidate_count": 0,
            "qpu_submitted": False,
            "message": (
                "Historical project CSV telemetry is not eligible for QPU power "
                "recommendations. It does not establish the required current "
                "900-second observation or supported device power modes."
            ),
            "rejections": [],
            "execution_performed": False,
        }

    if source == "simulator":
        telemetry_provider.tick()
    devices = telemetry_provider.get_devices()
    qubo, candidates = build_power_qubo(devices)
    if qubo is None:
        return {
            "status": "no_candidates",
            "execution_method": "ibm_qpu",
            "source": source,
            "data_origin": data_origin,
            "eligible_candidate_count": 0,
            "qpu_submitted": False,
            "message": "No devices satisfy the current QUBO eligibility rules.",
            "rejections": [],
            "execution_performed": False,
        }

    allowed_ids, rejections = _preflight_quantum_candidates(devices, candidates)
    candidate_devices = {
        device_id: device
        for device_id, device in devices.items()
        if device_id in allowed_ids
    }
    qubo, candidates = build_power_qubo(candidate_devices)
    if qubo is None:
        return {
            "status": "no_candidates",
            "execution_method": "ibm_qpu",
            "source": source,
            "data_origin": data_origin,
            "eligible_candidate_count": 0,
            "qpu_submitted": False,
            "message": "No candidates passed current Digital Twin and Policy Engine pre-validation.",
            "rejections": rejections,
            "execution_performed": False,
        }

    try:
        submission = run_qaoa_on_ibm_qpu(
            qubo,
            backend_name="ibm_fez",
            shots=shots,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "execution_method": "ibm_qpu",
            "source": source,
            "data_origin": data_origin,
            "eligible_candidate_count": len(candidates),
            "qpu_submitted": False,
            "error_type": type(exc).__name__,
            "error": _quantum_error_message(exc),
            "message": "IBM QPU submission failed; no local result was substituted.",
            "rejections": rejections,
            "execution_performed": False,
        }

    run_id = uuid.uuid4().hex
    qubo_variable_names = [variable.name for variable in qubo.variables]
    candidate_variable_names = [
        f"x{index}" for index in range(len(candidates))
    ]
    quantum_run = {
        "run_id": run_id,
        "job": submission["job"],
        "job_id": submission["job_id"],
        "backend": submission["backend"],
        "shots": submission["shots"],
        "requested_shots": shots,
        "num_qubo_variables": qubo.get_num_vars(),
        "qubo_variable_names": qubo_variable_names,
        "candidate_variable_names": candidate_variable_names,
        "measurement_bit_order": "qiskit_counts_msb_to_lsb",
        "qaoa_beta": submission["beta"],
        "qaoa_gamma": submission["gamma"],
        "qaoa_reps": 1,
        "qubo_penalty": QUBO_PENALTY,
        "max_actions": 4,
        "candidates": candidates,
        "rejections": rejections,
        "source": source,
        "data_origin": data_origin,
        "submitted_at": submission["submitted_at"],
        "num_qubits": submission["num_qubits"],
        "circuit_depth": submission["depth"],
        "completed_response": None,
    }
    quantum_runs[run_id] = quantum_run
    metadata_persisted = True
    persistence_error = None
    try:
        _persist_quantum_run(run_id, quantum_run)
    except OSError as exc:
        metadata_persisted = False
        persistence_error = _quantum_error_message(exc)
    return {
        "run_id": run_id,
        "job_id": submission["job_id"],
        "execution_method": "ibm_qpu",
        "backend": submission["backend"],
        "job_status": submission["status"],
        "status": "queued",
        "qpu_submitted": True,
        "source": source,
        "data_origin": data_origin,
        "submitted_at": submission["submitted_at"],
        "eligible_candidate_count": len(candidates),
        "qubo_variables": qubo.get_num_vars(),
        "qubo_variable_names": qubo_variable_names,
        "candidate_variable_names": candidate_variable_names,
        "measurement_bit_order": "qiskit_counts_msb_to_lsb",
        "qaoa_beta": submission["beta"],
        "qaoa_gamma": submission["gamma"],
        "max_actions": 4,
        "requested_shots": shots,
        "shots": shots,
        "metadata_available": True,
        "metadata_persisted": metadata_persisted,
        "num_qubits": submission["num_qubits"],
        "circuit_depth": submission["depth"],
        "message": (
            "QAOA circuit submitted to IBM hardware. Poll this run for its result."
            if metadata_persisted
            else (
                "QAOA circuit was submitted, but run metadata could not be persisted. "
                f"Restart recovery will not be available: {persistence_error}"
            )
        ),
        "execution_performed": False,
    }


@app.get("/api/quantum/run/{run_id}")
def get_quantum_optimization_run(run_id: str):
    run = quantum_runs.get(run_id)
    if run is None:
        try:
            run = _restore_quantum_run(run_id)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=_quantum_error_message(exc),
            ) from exc
        if run is None:
            raise HTTPException(
                status_code=404,
                detail="Quantum run metadata was not found in memory or persistent storage.",
            )
    if run["completed_response"] is not None:
        return run["completed_response"]

    try:
        raw_status = run["job"].status()
        job_status = getattr(raw_status, "name", str(raw_status).split(".")[-1]).upper()
    except Exception as exc:
        return {
            "run_id": run_id,
            "job_id": run["job_id"],
            "execution_method": "ibm_qpu",
            "backend": run["backend"],
            "status": "error",
            "qpu_submitted": True,
            "source": run["source"],
            "data_origin": run["data_origin"],
            "qubo_variables": run["num_qubo_variables"],
            "num_qubits": run["num_qubits"],
            "circuit_depth": run["circuit_depth"],
            "error_type": type(exc).__name__,
            "error": _quantum_error_message(exc),
            "message": "Could not retrieve the IBM job status.",
            "execution_performed": False,
        }

    if job_status not in {"DONE", "COMPLETED"}:
        if job_status in {"ERROR", "FAILED", "CANCELLED", "CANCELED"}:
            terminal_status = (
                "cancelled"
                if job_status in {"CANCELLED", "CANCELED"}
                else "failed"
            )
            return {
                "run_id": run_id,
                "job_id": run["job_id"],
                "execution_method": "ibm_qpu",
                "backend": run["backend"],
                "job_status": job_status,
                "status": terminal_status,
                "qpu_submitted": True,
                "source": run["source"],
                "data_origin": run["data_origin"],
                "qubo_variables": run["num_qubo_variables"],
                "num_qubits": run["num_qubits"],
                "circuit_depth": run["circuit_depth"],
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "message": f"IBM job ended with status {job_status}.",
                "execution_performed": False,
            }
        return {
            "run_id": run_id,
            "job_id": run["job_id"],
            "execution_method": "ibm_qpu",
            "backend": run["backend"],
            "job_status": job_status,
            "status": "running" if job_status == "RUNNING" else "queued",
            "qpu_submitted": True,
            "source": run["source"],
            "data_origin": run["data_origin"],
            "qubo_variables": run["num_qubo_variables"],
            "num_qubits": run["num_qubits"],
            "circuit_depth": run["circuit_depth"],
            "submitted_at": run["submitted_at"],
            "eligible_candidate_count": len(run["candidates"]),
            "requested_shots": run["requested_shots"],
            "message": f"IBM job is {job_status.lower()}.",
            "execution_performed": False,
        }

    try:
        sampler_result = run["job"].result()
        counts = sampler_result[0].data.meas.get_counts()
        evaluation = evaluate_qpu_counts(
            counts,
            run["candidates"],
            num_qubo_variables=run["num_qubo_variables"],
            max_actions=run["max_actions"],
            variable_order=run["qubo_variable_names"],
            candidate_variable_names=run["candidate_variable_names"],
        )
    except Exception as exc:
        response = {
            "run_id": run_id,
            "job_id": run["job_id"],
            "execution_method": "ibm_qpu",
            "backend": run["backend"],
            "job_status": job_status,
            "status": "failed",
            "qpu_submitted": True,
            "metadata_available": True,
            "result_retrieved": False,
            "qubo_variables": run["num_qubo_variables"],
            "num_qubits": run["num_qubits"],
            "circuit_depth": run["circuit_depth"],
            "submitted_at": run["submitted_at"],
            "error_type": type(exc).__name__,
            "error": _quantum_error_message(exc),
            "message": "IBM job result retrieval or decoding failed; no local result was substituted.",
            "execution_performed": False,
        }
        run["completed_response"] = response
        return response

    best_solution = evaluation.get("best_solution")
    if telemetry_provider.source_mode != run["source"]:
        response = {
            "run_id": run_id,
            "job_id": run["job_id"],
            "execution_method": "ibm_qpu",
            "backend": run["backend"],
            "job_status": job_status,
            "status": "rejected",
            "qpu_submitted": True,
            "source": run["source"],
            "data_origin": run["data_origin"],
            "qubo_variables": run["num_qubo_variables"],
            "num_qubits": run["num_qubits"],
            "circuit_depth": run["circuit_depth"],
            "current_source": telemetry_provider.source_mode,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "message": "Telemetry source changed while the QPU job was running; the proposal was not validated.",
            "qpu_solution": best_solution,
            "execution_performed": False,
        }
        run["completed_response"] = response
        return response

    if best_solution is None or not best_solution["selected_devices"]:
        response = {
            "run_id": run_id,
            "job_id": run["job_id"],
            "execution_method": "ibm_qpu",
            "backend": run["backend"],
            "job_status": job_status,
            "status": "rejected",
            "qpu_submitted": True,
            "source": run["source"],
            "data_origin": run["data_origin"],
            "qubo_variables": run["num_qubo_variables"],
            "num_qubits": run["num_qubits"],
            "circuit_depth": run["circuit_depth"],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "message": "The completed QPU result contained no feasible selected actions.",
            "qpu_solution": best_solution,
            "rejections": run["rejections"],
            "execution_performed": False,
        }
        run["completed_response"] = response
        return response

    validation = validate_qpu_solution_with_digital_twin(
        counts,
        candidates=run["candidates"],
        num_qubo_variables=run["num_qubo_variables"],
        max_actions=run["max_actions"],
        variable_order=run["qubo_variable_names"],
        candidate_variable_names=run["candidate_variable_names"],
    )
    twin_result = validation.get("digital_twin_validation") or {}
    validation_by_id = {
        action["device_id"]: action
        for action in twin_result.get("actions", [])
    }
    recommendations = []
    for selected in best_solution["selected_devices"]:
        validated = validation_by_id.get(selected["device_id"], {})
        if validated.get("result") != "APPROVED":
            continue
        recommendations.append({
            **selected,
            "estimated_power_saving_w": validated.get("saving_w", 0.0),
            "validation_status": validated.get("result"),
            "policy_checks": validated.get("policy_checks", []),
        })

    response_status = (
        "completed"
        if twin_result.get("all_actions_approved")
        and len(recommendations) == len(best_solution["selected_devices"])
        else "rejected"
    )
    response = {
        "run_id": run_id,
        "job_id": run["job_id"],
        "execution_method": "ibm_qpu",
        "backend": run["backend"],
        "job_status": job_status,
        "status": response_status,
        "qpu_submitted": True,
        "metadata_available": True,
        "result_retrieved": True,
        "source": run["source"],
        "data_origin": run["data_origin"],
        "qubo_variables": run["num_qubo_variables"],
        "qubo_variable_names": run["qubo_variable_names"],
        "candidate_variable_names": run["candidate_variable_names"],
        "measurement_bit_order": run["measurement_bit_order"],
        "qaoa_beta": run["qaoa_beta"],
        "qaoa_gamma": run["qaoa_gamma"],
        "num_qubits": run["num_qubits"],
        "circuit_depth": run["circuit_depth"],
        "submitted_at": run["submitted_at"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "shots": evaluation["total_shots"],
        "requested_shots": run["requested_shots"],
        "eligible_candidate_count": len(run["candidates"]),
        "max_actions": run["max_actions"],
        "selected_action_count": best_solution["num_selected"],
        "qpu_solution": best_solution,
        "recommendations": recommendations,
        "rejections": run["rejections"] + [
            action for action in twin_result.get("actions", [])
            if action.get("result") != "APPROVED"
        ],
        "digital_twin": twin_result,
        "validation_status": twin_result.get("status", validation.get("status")),
        "total_estimated_power_saving_w": round(
            sum(item["estimated_power_saving_w"] for item in recommendations),
            1,
        ),
        "message": (
            "IBM QPU result retrieved and validated. Recommendations are advisory; "
            "no network action was executed."
        ),
        "execution_performed": False,
    }
    run["completed_response"] = response
    try:
        _persist_quantum_run(run_id, run)
    except OSError as exc:
        response["metadata_persisted"] = False
        response["metadata_persistence_error"] = _quantum_error_message(exc)
    return response


# ============================================================
# BACKGROUND SIMULATION LOOP
# ============================================================

async def background_simulation_loop():

    while True:

        try:

            # Update optical-network telemetry
            telemetry_provider.tick()
            if (
                telemetry_provider.source_mode == "nokia"
                and telemetry_provider.nokia_adapter.is_historical_csv
            ):
                await asyncio.sleep(1.0)
                continue

            # Learn per-device normal behaviour before downstream detection.
            for device_id, device in telemetry_provider.get_devices().items():
                adaptive_baseline.update_device(device_id, device.telemetry)

            # Synchronize Digital Twin
            digital_twin_engine.synchronize()

        except Exception as e:

            print(
                f"Simulation tick error: {e}"
            )

        await asyncio.sleep(1.0)


@app.on_event("startup")
async def startup_event():

    asyncio.create_task(
        background_simulation_loop()
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def read_root():

    return {
        "status": "online",
        "system": (
            "AI-Based Power Saving in Optical Networks Simulator"
        ),
        "device_count": len(telemetry_provider.get_devices()),
        "version": "1.0.0"
    }


# ============================================================
# DEVICE ENDPOINTS
# ============================================================

@app.get(
    "/api/devices",
    response_model=List[Device]
)
def get_devices():

    return list(
        telemetry_provider.get_devices().values()
    )


@app.get(
    "/api/devices/{device_id}",
    response_model=Device
)
def get_device(device_id: str):

    dev = telemetry_provider.get_device(
        device_id
    )

    if not dev:

        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    return dev


@app.get("/api/adaptive-thresholds")
def get_adaptive_thresholds():
    """Return learned thresholds, classifications, and candidate signals."""
    return adaptive_baseline.all_snapshots(simulator.devices)


@app.get("/api/adaptive-thresholds/{device_id}")
def get_device_adaptive_thresholds(device_id: str):
    dev = telemetry_provider.get_device(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return adaptive_baseline.device_snapshot(
        device_id, dev.telemetry
    )


# ============================================================
# MACHINE LEARNING
# ============================================================

@app.get(
    "/api/predictions",
    response_model=TrafficPrediction
)
def get_traffic_prediction(
    horizon: str = "5m"
):

    if horizon not in [
        "5m",
        "1h",
        "24h"
    ]:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid horizon. "
                "Choose '5m', '1h', or '24h'"
            )
        )

    # Never expose simulator/model output while a selected source has no
    # telemetry. The UI uses the empty prediction to render a true blank state.
    if (
        not telemetry_provider.get_devices()
        or (
            telemetry_provider.source_mode == "nokia"
            and telemetry_provider.nokia_adapter.is_historical_csv
        )
    ):
        return TrafficPrediction(
            horizon=horizon,
            timestamps=[],
            predicted_traffic_gbps=[],
            upper_bound_gbps=[],
            lower_bound_gbps=[],
            confidence_score=0.0,
        )

    return ml_engine.predict_traffic(horizon)


@app.get(
    "/api/anomalies",
    response_model=List[AnomalyItem]
)
def get_anomalies():

    if (
        not telemetry_provider.get_devices()
        or (
            telemetry_provider.source_mode == "nokia"
            and telemetry_provider.nokia_adapter.is_historical_csv
        )
    ):
        return []

    return ml_engine.detect_anomalies()


@app.get("/api/telemetry/nokia/thresholds", response_model=List[NokiaThresholdResult])
def get_nokia_thresholds():
    """Return source-gated Nokia threshold findings with completeness metadata."""
    if telemetry_provider.source_mode != "nokia":
        return []
    return nokia_thresholds.evaluate_devices(telemetry_provider.get_devices().values())


# ============================================================
# LLM RECOMMENDATIONS
# ============================================================

@app.get(
    "/api/recommendations",
    response_model=List[Recommendation]
)
def get_recommendations():

    return llm_engine.get_recommendations()


# ============================================================
# ACTION EXECUTION
# ============================================================

@app.post(
    "/api/actions/execute"
)
def execute_action(
    req: ActionExecutionRequest
):

    recs = llm_engine.get_recommendations()

    target_rec = next(
        (
            r for r in recs
            if r.id == req.recommendation_id
        ),
        None
    )

    if not target_rec:

        raise HTTPException(
            status_code=404,
            detail=(
                "Recommendation not found or expired"
            )
        )

    # --------------------------------------------------------
    # Policy validation
    # --------------------------------------------------------

    if not target_rec.validation_passed:

        fcaps_manager.log_security_event(
            user="ai_agent_policy",
            event=(
                f"BLOCKED Execution on "
                f"{target_rec.device_id}: "
                f"{target_rec.rejection_reason}"
            ),
            ip="127.0.0.1",
            status="DENIED"
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Action REJECTED by Optical Policy Engine: "
                f"{target_rec.rejection_reason}"
            )
        )

    # --------------------------------------------------------
    # Apply power-mode change
    # --------------------------------------------------------

    dev_id = target_rec.device_id
    if telemetry_provider.source_mode == "nokia":
        fcaps_manager.log_security_event(
            user="operator_admin",
            event=(
                f"BLOCKED read-only Nokia telemetry action "
                f"{target_rec.action_type.value} on {target_rec.device_name} "
                f"({dev_id})"
            ),
            ip="127.0.0.1",
            status="DENIED"
        )
        raise HTTPException(
            status_code=403,
            detail="Telemetry source is read-only; hardware execution is disabled."
        )

    changed = True

    if "Sleep" in target_rec.action_type.value:

        changed = telemetry_provider.set_device_power_mode(
            dev_id,
            PowerMode.SLEEP
        )

    elif "Reduce" in target_rec.action_type.value:

        changed = telemetry_provider.set_device_power_mode(
            dev_id,
            PowerMode.LOW_GAIN
        )

    elif (
        "Wake" in target_rec.action_type.value
        or
        "Restore" in target_rec.action_type.value
    ):

        changed = telemetry_provider.set_device_power_mode(
            dev_id,
            PowerMode.NORMAL
        )

    # --------------------------------------------------------
    # FCAPS security logging
    # --------------------------------------------------------

    fcaps_manager.log_security_event(
        user="operator_admin",
        event=(
            f"EXECUTED Power Optimization "
            f"{target_rec.action_type.value} "
            f"on {target_rec.device_name} "
            f"({dev_id})"
        ),
        ip="127.0.0.1",
        status="SUCCESS"
    )

    updated_device = telemetry_provider.get_device(dev_id)
    return {
        "status": "success",
        "message": (
            f"Successfully executed "
            f"'{target_rec.action_type.value}' "
            f"on {target_rec.device_name} "
            f"({dev_id}). "
            f"Power reduction in effect."
        ),
        "device_id": dev_id,
        "new_power_mode": (
            updated_device.power_mode.value if updated_device else None
        )
    }


# ============================================================
# FAULT MANAGEMENT
# ============================================================

@app.post(
    "/api/faults/inject"
)
def inject_fault(
    device_id: str,
    fault_type: str
):

    if not telemetry_provider.get_device(device_id):

        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    if not telemetry_provider.inject_fault(device_id, fault_type):
        raise HTTPException(status_code=403, detail="Fault injection is available only in simulator telemetry mode.")

    return {
        "status": "injected",
        "device_id": device_id,
        "fault_type": fault_type
    }


@app.post(
    "/api/faults/clear"
)
def clear_fault(
    device_id: str
):

    if not telemetry_provider.get_device(device_id):

        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    if not telemetry_provider.clear_fault(device_id):
        raise HTTPException(status_code=403, detail="Fault clearing is available only in simulator telemetry mode.")

    return {
        "status": "cleared",
        "device_id": device_id
    }


@app.get("/api/telemetry/source")
def get_telemetry_source():
    return _telemetry_source_status()


def _telemetry_source_status() -> dict:
    is_nokia = telemetry_provider.source_mode == "nokia"
    ingestion_status = telemetry_provider.nokia_adapter.get_uploaded_csv_status()
    return {
        "source": telemetry_provider.source_mode,
        "device_count": len(telemetry_provider.get_devices()),
        "nokia_execution_enabled": telemetry_provider.nokia_adapter.nokia_execution_enabled,
        "refresh_status": (
            telemetry_provider.nokia_adapter.last_refresh_status if is_nokia else "connected"
        ),
        "last_refresh_error": (
            telemetry_provider.nokia_adapter.last_refresh_error if is_nokia else None
        ),
        "data_origin": telemetry_provider.nokia_adapter.data_origin if is_nokia else "simulator",
        "csv_ingestion_status": ingestion_status if is_nokia else None,
    }


@app.post("/api/telemetry/source")
def set_telemetry_source(source: str):
    try:
        selected = telemetry_provider.set_source_mode(source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "success", **_telemetry_source_status()}


@app.post("/api/telemetry/refresh")
def refresh_telemetry():
    telemetry_provider.refresh()
    status = _telemetry_source_status()
    return {"status": status["refresh_status"], **status}


@app.get("/api/telemetry/nokia/csv-ingest-status")
def get_nokia_csv_ingest_status():
    return telemetry_provider.nokia_adapter.get_uploaded_csv_status()


# ============================================================
# FCAPS
# ============================================================

@app.get(
    "/api/fcaps/alarms",
    response_model=List[FCAPSAlarm]
)
def get_fcaps_alarms():

    if (
        telemetry_provider.source_mode == "nokia"
        and telemetry_provider.nokia_adapter.is_historical_csv
    ):
        return []
    return fcaps_manager.get_fault_alarms()


@app.post(
    "/api/fcaps/alarms/ack"
)
def acknowledge_alarm(
    alarm_id: str
):

    fcaps_manager.acknowledge_alarm(
        alarm_id
    )

    return {
        "status": "acknowledged",
        "alarm_id": alarm_id
    }


@app.get(
    "/api/fcaps/accounting",
    response_model=FCAPSEnergyAccounting
)
def get_energy_accounting():

    if (
        telemetry_provider.source_mode == "nokia"
        and telemetry_provider.nokia_adapter.is_historical_csv
    ):
        raise HTTPException(
            status_code=409,
            detail="Energy savings are not measured or estimated from historical project CSV files.",
        )
    return fcaps_manager.get_energy_accounting()


@app.get(
    "/api/fcaps/security",
    response_model=List[FCAPSSecurityLog]
)
def get_security_logs():

    if (
        telemetry_provider.source_mode == "nokia"
        and telemetry_provider.nokia_adapter.is_historical_csv
    ):
        return []
    return fcaps_manager.security_logs


# ============================================================
# CHATBOT
# ============================================================

@app.post(
    "/api/chatbot"
)
def process_chatbot_query(
    req: ChatRequest
):

    response_text = (
        llm_engine.process_chat_query(
            req.prompt
        )
    )

    return {
        "response": response_text
    }


# ============================================================
# TOPOLOGY
# ============================================================

@app.get(
    "/api/topology",
    response_model=TopologyStateModel
)
def get_topology():
    return telemetry_provider.get_topology_state()


@app.post(
    "/api/topology/pattern"
)
def set_topology_pattern(
    req: SetTopologyPatternRequest
):
    if telemetry_provider.source_mode != "simulator":
        raise HTTPException(status_code=409, detail="Topology patterns are available only for simulator telemetry.")

    try:

        res = simulator.set_topology_pattern(
            req.pattern
        )

        return {
            "status": "success",
            "topology": res
        }

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@app.post(
    "/api/topology/rotate"
)
def rotate_topology(
    req: RotateTopologyRequest
):
    if telemetry_provider.source_mode != "simulator":
        raise HTTPException(status_code=409, detail="Topology rotation is available only for simulator telemetry.")

    res = simulator.rotate_topology(
        req.delta_deg,
        req.node_name
    )

    return {
        "status": "success",
        "topology": res
    }


@app.get(
    "/api/topology/connectivity"
)
def get_topology_connectivity():

    state = (
        simulator
        .topology_engine
        .get_topology_state()
    )

    nodes = list(
        state["nodes"].keys()
    )

    matrix = {}

    for src in nodes:

        matrix[src] = {}

        for dst in nodes:

            if src == dst:

                matrix[src][dst] = {
                    "connected": False,
                    "distance_km": 0.0,
                    "bearing_deg": 0.0
                }

            else:

                dist, bearing = (
                    simulator
                    .topology_engine
                    .calculate_distance_and_bearing(
                        src,
                        dst
                    )
                )

                connected = any(
                    (
                        (
                            l["src"] == src
                            and
                            l["dst"] == dst
                        )
                        or
                        (
                            l["src"] == dst
                            and
                            l["dst"] == src
                        )
                    )
                    for l in state["links"]
                    if l["active"]
                )

                matrix[src][dst] = {
                    "connected": connected,
                    "distance_km": dist,
                    "bearing_deg": bearing
                }

    return {
        "pattern": state["pattern"],
        "global_rotation_deg": (
            state["global_rotation_deg"]
        ),
        "connectivity_matrix": matrix
    }


# ============================================================
# DIGITAL TWIN
# ============================================================

@app.get(
    "/api/digital-twin/state",
    response_model=DigitalTwinStateSummary
)
def get_digital_twin_state():

    return (
        digital_twin_engine
        .get_state_summary()
    )


@app.get(
    "/api/digital-twin/devices",
    response_model=List[DigitalTwinDevice]
)
def get_digital_twin_devices():

    return (
        digital_twin_engine
        .get_devices()
    )


@app.get(
    "/api/digital-twin/devices/{device_id}",
    response_model=DigitalTwinDevice
)
def get_digital_twin_device(
    device_id: str
):

    dev = (
        digital_twin_engine
        .get_device(device_id)
    )

    if not dev:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Digital Twin device "
                f"'{device_id}' not found"
            )
        )

    return dev


@app.get(
    "/api/digital-twin/topology",
    response_model=DigitalTwinTopologyGraph
)
def get_digital_twin_topology():

    return (
        digital_twin_engine
        .get_topology_graph()
    )


@app.post(
    "/api/digital-twin/simulate",
    response_model=WhatIfSimulationResponse
)
def simulate_what_if_scenario(
    req: WhatIfSimulationRequest
):

    return (
        digital_twin_engine
        .simulate_what_if(req)
    )


@app.post(
    "/api/digital-twin/validate",
    response_model=WhatIfSimulationResponse
)
def validate_action_via_digital_twin(
    req: WhatIfSimulationRequest
):

    return (
        digital_twin_engine
        .simulate_what_if(req)
    )


@app.get(
    "/api/digital-twin/simulations",
    response_model=List[SimulationHistoryItem]
)
def get_simulation_history():

    return (
        digital_twin_engine
        .simulation_history
    )


@app.post(
    "/api/digital-twin/execute"
)
def execute_digital_twin_action(
    req: WhatIfSimulationRequest
):
    if telemetry_provider.source_mode == "nokia":
        raise HTTPException(
            status_code=403,
            detail=(
                "Nokia telemetry is read-only. What-If and quantum analyses are "
                "simulations and cannot execute actions on a device."
            ),
        )

    res = (
        digital_twin_engine
        .execute_simulation(
            req.device_id,
            req.action_type
        )
    )

    # --------------------------------------------------------
    # Error
    # --------------------------------------------------------

    if res.get("status") == "error":

        raise HTTPException(
            status_code=404,
            detail=res.get("message")
        )

    # --------------------------------------------------------
    # Policy block
    # --------------------------------------------------------

    elif res.get("status") == "blocked":

        fcaps_manager.log_security_event(
            user="ai_digital_twin_validator",
            event=(
                f"BLOCKED Execution on "
                f"{req.device_id}: "
                f"{res.get('message')}"
            ),
            ip="127.0.0.1",
            status="DENIED"
        )

        raise HTTPException(
            status_code=400,
            detail=res.get("message")
        )

    # --------------------------------------------------------
    # Successful execution
    # --------------------------------------------------------

    fcaps_manager.log_security_event(
        user="digital_twin_controller",
        event=(
            f"EXECUTED Action "
            f"{req.action_type.value} "
            f"on {req.device_id}"
        ),
        ip="127.0.0.1",
        status="SUCCESS"
    )

    return res


# ============================================================
# DIGITAL TWIN HEALTH
# ============================================================

@app.get(
    "/api/digital-twin/health"
)
def get_digital_twin_health():

    summary = (
        digital_twin_engine
        .get_state_summary()
    )

    return {
        "status": "online",
        "engine": (
            "Digital Twin NetworkX "
            "What-If Simulator"
        ),
        "sync_status": (
            summary.sync_status.value
        ),
        "network_health": (
            summary.network_health
        ),
        "synchronized_devices": (
            summary.synchronized_devices
        ),
        "stale_devices": (
            summary.stale_devices
        ),
        "offline_devices": (
            summary.offline_devices
        ),
        "last_sync": (
            summary.last_sync_timestamp
        )
    }


# ============================================================
# DIGITAL TWIN DEMO SCENARIOS
# ============================================================

@app.get(
    "/api/digital-twin/demo/scenarios",
    response_model=List[DemoScenarioInfo]
)
def get_demo_scenarios():

    return (
        digital_twin_engine
        .get_demo_scenarios()
    )


@app.post(
    "/api/digital-twin/demo/run",
    response_model=WhatIfSimulationResponse
)
def run_demo_scenario(
    scenario_id: str
):

    return (
        digital_twin_engine
        .run_demo_scenario(
            scenario_id
        )
    )