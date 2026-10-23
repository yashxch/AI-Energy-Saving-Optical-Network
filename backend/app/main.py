import sys

# Use the active Python environment instead of forcing a stale local
# quantum environment onto sys.path; that environment can shadow the
# dependencies installed for this project.

import asyncio
import time
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional

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
from .quantum_optimizer import validate_qpu_solution_with_digital_twin
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
    """
    Retrieve the already-completed real NOKIA Quantum result
    and validate it through the Digital Twin and Policy Engine.

    IMPORTANT:
    This endpoint DOES NOT submit a new quantum job.
    It only retrieves the previously completed  QPU job.
    """

    # --------------------------------------------------------
    # Real IBM Quantum job
    # --------------------------------------------------------

    JOB_ID = "damsci82fm4c73f3faa0"

    # --------------------------------------------------------
    # Candidate snapshot used when the QUBO was created
    # --------------------------------------------------------

    SNAPSHOT = (
        Path(__file__).resolve().parent
        / "quantum_runs"
        / "20260918T231615Z_candidates.json"
    )

    try:

        print("\n")
        print("=" * 60)
        print("REAL  QUANTUM VALIDATION")
        print("=" * 60)

        # ----------------------------------------------------
        # Connect to IBM Quantum
        # ----------------------------------------------------

        from qiskit_ibm_runtime import QiskitRuntimeService

        service = QiskitRuntimeService()

        print("NOKIA Quantum connection: OK")

        # ----------------------------------------------------
        # Retrieve previously completed job
        # ----------------------------------------------------

        job = service.job(JOB_ID)

        job_status = str(job.status())

        print("Job ID:", JOB_ID)
        print("Job status:", job_status)

        # ----------------------------------------------------
        # Check job completion
        # ----------------------------------------------------

        normalized_status = job_status.upper()

        if normalized_status not in {
            "DONE",
            "JOBSTATUS.DONE"
        }:

            return JSONResponse(
                status_code=200,
                content={
                    "status": "pending",
                    "job_id": JOB_ID,
                    "qpu_status": job_status,
                    "message": "The IBM Quantum job has not completed yet."
                }
            )

        # ----------------------------------------------------
        # Retrieve REAL QPU measurement result
        # ----------------------------------------------------

        result = job.result()

        counts = result[0].data.meas.get_counts()

        if not counts:
            raise RuntimeError(
                " Quantum returned no measurement counts."
            )

        total_shots = int(sum(counts.values()))

        print("Backend:", job.backend().name)
        print("Total QPU shots:", total_shots)
        print("Distinct measured states:", len(counts))

        # ----------------------------------------------------
        # Validate QPU solution against:
        #
        # 1. Current telemetry
        # 2. Digital Twin
        # 3. Optical Policy Engine
        #
        # ----------------------------------------------------

        validation = validate_qpu_solution_with_digital_twin(
            counts,
            snapshot_path=str(SNAPSHOT)
        )

        # ----------------------------------------------------
        # Build JSON-safe response
        # ----------------------------------------------------

        response = {
            "status": validation.get("status"),

            "message": (
                "Real IBM Quantum result retrieved successfully "
                "and passed through the Digital Twin and Policy Engine."
            ),

            "qpu": {
                "job_id": JOB_ID,
                "backend": str(job.backend().name),
                "shots": total_shots,
                "solution": validation.get("qpu_solution")
            },

            "digital_twin": validation.get(
                "digital_twin_validation"
            ),

            "actions": validation.get(
                "actions",
                []
            ),

            "candidate_snapshot": validation.get(
                "candidate_snapshot"
            ),

            "used_current_telemetry": validation.get(
                "used_current_telemetry",
                True
            ),

            "execution_performed": validation.get(
                "execution_performed",
                False
            )
        }

        # ----------------------------------------------------
        # Guarantee JSON serializability
        # ----------------------------------------------------

        safe_response = json.loads(
            json.dumps(
                response,
                default=str
            )
        )

        print("Validation status:",
              safe_response.get("status"))

        print(
            "Execution performed:",
            safe_response.get("execution_performed")
        )

        print("=" * 60)
        print("QUANTUM VALIDATION COMPLETE")
        print("=" * 60)
        print()

        return JSONResponse(
            status_code=200,
            content=safe_response
        )

    except Exception as e:

        # ----------------------------------------------------
        # IMPORTANT:
        # Return the REAL error instead of generic
        # "Internal Server Error".
        # ----------------------------------------------------

        error_type = type(e).__name__
        error_message = str(e)

        print("\n")
        print("=" * 60)
        print("QUANTUM VALIDATION ERROR")
        print("=" * 60)
        print("Error type:", error_type)
        print("Error:", error_message)
        print("=" * 60)
        print()

        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "error_type": error_type,
                "error": error_message,
                "job_id": JOB_ID,
                "snapshot": str(SNAPSHOT),
                "message": (
                    "Quantum validation failed. "
                    "The actual backend error is shown above."
                )
            }
        )


# ============================================================
# BACKGROUND SIMULATION LOOP
# ============================================================

async def background_simulation_loop():

    while True:

        try:

            # Update optical-network telemetry
            telemetry_provider.tick()

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
    if not telemetry_provider.get_devices():
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

    if not telemetry_provider.get_devices():
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


# ============================================================
# FCAPS
# ============================================================

@app.get(
    "/api/fcaps/alarms",
    response_model=List[FCAPSAlarm]
)
def get_fcaps_alarms():

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

    return fcaps_manager.get_energy_accounting()


@app.get(
    "/api/fcaps/security",
    response_model=List[FCAPSSecurityLog]
)
def get_security_logs():

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