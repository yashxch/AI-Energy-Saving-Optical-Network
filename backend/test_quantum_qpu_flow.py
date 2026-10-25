import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from qiskit import QuantumCircuit
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.converters import QuadraticProgramToQubo

from app import main
from app.quantum_optimizer import decode_qpu_bitstring, run_qaoa_on_ibm_qpu


def _candidate(device_id, saving):
    return {
        "device_id": device_id,
        "device_type": "TRANSPONDER_800G",
        "action": "SLEEP",
        "traffic": 10.0,
        "power_saving_w": saving,
    }


def _configure_mock_run(monkeypatch, job, candidates):
    class DummyQubo:
        variables = [
            SimpleNamespace(name="x0"),
            SimpleNamespace(name="x1"),
            SimpleNamespace(name="max_actions@int_slack@0"),
            SimpleNamespace(name="max_actions@int_slack@1"),
        ]

        def get_num_vars(self):
            return 4

    monkeypatch.setattr(main, "quantum_runs", {})
    monkeypatch.setattr(main.telemetry_provider, "_source_mode", "simulator")
    monkeypatch.setattr(main.telemetry_provider, "tick", lambda: None)
    monkeypatch.setattr(
        main.telemetry_provider,
        "get_devices",
        lambda: {item["device_id"]: object() for item in candidates},
    )
    monkeypatch.setattr(
        main,
        "build_power_qubo",
        lambda devices: (DummyQubo(), candidates),
    )
    monkeypatch.setattr(
        main,
        "_preflight_quantum_candidates",
        lambda devices, items: ({item["device_id"] for item in items}, []),
    )
    monkeypatch.setattr(
        main,
        "run_qaoa_on_ibm_qpu",
        lambda qubo, backend_name, shots: {
            "job": job,
            "job_id": "mock-job-123",
            "backend": "ibm_fez",
            "shots": shots,
            "num_qubits": 4,
            "depth": 12,
            "status": "QUEUED",
            "submitted_at": "2026-01-01T00:00:00+00:00",
            "beta": 1.0,
            "gamma": -0.1,
        },
    )


def test_qpu_decoder_maps_measured_bits_to_candidate_variables():
    candidates = [_candidate("device-a", 10), _candidate("device-b", 20)]

    decoded = decode_qpu_bitstring(
        "0010",
        candidates,
        num_qubo_variables=4,
        max_actions=4,
    )

    assert decoded["variable_bitstring"] == "0100"
    assert [item["device_id"] for item in decoded["selected_devices"]] == ["device-b"]
    assert decoded["total_power_saving_w"] == 20
    assert decoded["feasible"] is True


def test_decoder_maps_candidates_by_persisted_qubo_variable_names():
    candidates = [_candidate("device-a", 10), _candidate("device-b", 20)]
    decoded = decode_qpu_bitstring(
        "0010",
        candidates,
        num_qubo_variables=4,
        max_actions=4,
        variable_order=["slack-a", "x1", "x0", "slack-b"],
        candidate_variable_names=["x0", "x1"],
    )

    assert decoded["variable_values"] == {
        "slack-a": "0",
        "x1": "1",
        "x0": "0",
        "slack-b": "0",
    }
    assert [device["device_id"] for device in decoded["selected_devices"]] == ["device-b"]


def test_qpu_submit_poll_returns_only_twin_approved_savings(monkeypatch):
    candidates = [_candidate("device-a", 10), _candidate("device-b", 20)]

    class FakeJob:
        def status(self):
            return "DONE"

        def result(self):
            measurement = SimpleNamespace(get_counts=lambda: {"0010": 128})
            return [SimpleNamespace(data=SimpleNamespace(meas=measurement))]

    _configure_mock_run(monkeypatch, FakeJob(), candidates)
    validation_arguments = {}

    def validate(
        counts,
        candidates,
        num_qubo_variables,
        max_actions,
        variable_order,
        candidate_variable_names,
    ):
        validation_arguments.update(
            num_qubo_variables=num_qubo_variables,
            max_actions=max_actions,
            variable_order=variable_order,
            candidate_variable_names=candidate_variable_names,
        )
        return {
            "status": "APPROVED",
            "digital_twin_validation": {
                "status": "APPROVED",
                "all_actions_approved": True,
                "actions": [{
                    "device_id": "device-b",
                    "result": "APPROVED",
                    "saving_w": 7.5,
                    "policy_checks": [],
                }],
            },
        }

    monkeypatch.setattr(main, "validate_qpu_solution_with_digital_twin", validate)

    client = TestClient(main.app)
    submitted = client.post("/api/quantum/run?shots=128")
    assert submitted.status_code == 200
    submitted_body = submitted.json()
    assert submitted_body["status"] == "queued"
    assert submitted_body["job_id"] == "mock-job-123"
    assert submitted_body["qpu_submitted"] is True

    completed = client.get(f"/api/quantum/run/{submitted_body['run_id']}")

    assert completed.status_code == 200
    result = completed.json()
    assert result["status"] == "completed"
    assert result["execution_method"] == "ibm_qpu"
    assert result["backend"] == "ibm_fez"
    assert result["job_id"] == "mock-job-123"
    assert result["execution_performed"] is False
    assert result["qubo_variables"] == 4
    assert result["num_qubits"] == 4
    assert result["circuit_depth"] == 12
    assert result["total_estimated_power_saving_w"] == 7.5
    assert [item["device_id"] for item in result["recommendations"]] == ["device-b"]
    assert validation_arguments == {
        "num_qubo_variables": 4,
        "max_actions": 4,
        "variable_order": [
            "x0",
            "x1",
            "max_actions@int_slack@0",
            "max_actions@int_slack@1",
        ],
        "candidate_variable_names": ["x0", "x1"],
    }


def test_qpu_run_with_no_candidates_does_not_submit(monkeypatch):
    monkeypatch.setattr(main, "quantum_runs", {})
    monkeypatch.setattr(main.telemetry_provider, "_source_mode", "simulator")
    monkeypatch.setattr(main.telemetry_provider, "tick", lambda: None)
    monkeypatch.setattr(main.telemetry_provider, "get_devices", lambda: {})
    monkeypatch.setattr(main, "build_power_qubo", lambda devices: (None, []))
    monkeypatch.setattr(
        main,
        "run_qaoa_on_ibm_qpu",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("QPU must not be submitted without candidates")
        ),
    )

    client = TestClient(main.app)
    response = client.post("/api/quantum/run")
    legacy_result = client.get("/api/quantum/validate")

    assert response.status_code == 200
    assert response.json()["status"] == "no_candidates"
    assert response.json()["qpu_submitted"] is False
    assert legacy_result.status_code == 410


def test_qpu_result_is_rejected_when_telemetry_source_changes(monkeypatch):
    candidates = [_candidate("device-a", 10), _candidate("device-b", 20)]

    class FakeJob:
        def status(self):
            return "DONE"

        def result(self):
            measurement = SimpleNamespace(get_counts=lambda: {"0010": 128})
            return [SimpleNamespace(data=SimpleNamespace(meas=measurement))]

    _configure_mock_run(monkeypatch, FakeJob(), candidates)
    monkeypatch.setattr(
        main,
        "validate_qpu_solution_with_digital_twin",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Changed-source results must not be validated.")
        ),
    )

    client = TestClient(main.app)
    submitted = client.post("/api/quantum/run")
    run_id = submitted.json()["run_id"]
    monkeypatch.setattr(main.telemetry_provider, "_source_mode", "nokia")
    result = client.get(f"/api/quantum/run/{run_id}").json()

    assert result["status"] == "rejected"
    assert result["source"] == "simulator"
    assert result["current_source"] == "nokia"
    assert result["execution_performed"] is False


def test_qpu_submit_helper_uses_named_hardware_service_without_network(monkeypatch):
    calls = {}
    backend = SimpleNamespace(
        name="ibm_fez",
        simulator=False,
        status=lambda: SimpleNamespace(
            operational=True,
            status_msg="active",
        ),
    )

    class FakeService:
        def __init__(self, name):
            calls["service_name"] = name

        def backend(self, backend_name):
            calls["backend_name"] = backend_name
            return backend

    class FakeJob:
        def job_id(self):
            return "mock-hardware-job"

        def status(self):
            return "QUEUED"

    class FakeSampler:
        def __init__(self, mode):
            calls["sampler_mode"] = mode

        def run(self, circuits, shots):
            calls["shots"] = shots
            calls["circuit"] = circuits[0]
            return FakeJob()

    monkeypatch.setitem(
        sys.modules,
        "qiskit_ibm_runtime",
        SimpleNamespace(
            QiskitRuntimeService=FakeService,
            SamplerV2=FakeSampler,
        ),
    )
    monkeypatch.setattr(
        "qiskit.transpile",
        lambda circuit, backend, optimization_level: circuit,
    )

    problem = QuadraticProgram()
    problem.binary_var("x0")
    problem.minimize(linear={"x0": -1})
    qubo = QuadraticProgramToQubo().convert(problem)

    result = run_qaoa_on_ibm_qpu(qubo, shots=128)

    assert calls["service_name"] == "optical-qpu"
    assert calls["backend_name"] == "ibm_fez"
    assert calls["sampler_mode"] is backend
    assert calls["shots"] == 128
    assert isinstance(calls["circuit"], QuantumCircuit)
    assert result["job_id"] == "mock-hardware-job"
    assert result["backend"] == "ibm_fez"


def test_existing_completed_job_is_retrieved_without_decoding_or_submission(monkeypatch):
    calls = {"job_lookups": [], "submissions": 0}

    class FakeJob:
        def status(self):
            return "DONE"

        def backend(self):
            return SimpleNamespace(name="ibm_fez")

        def result(self):
            measurement = SimpleNamespace(
                get_counts=lambda: {"001": 3, "110": 2}
            )
            return [SimpleNamespace(data=SimpleNamespace(meas=measurement))]

    class FakeService:
        def __init__(self, name):
            assert name == "optical-qpu"

        def job(self, job_id):
            calls["job_lookups"].append(job_id)
            return FakeJob()

    monkeypatch.setitem(
        sys.modules,
        "qiskit_ibm_runtime",
        SimpleNamespace(QiskitRuntimeService=FakeService),
    )
    monkeypatch.setattr(main, "quantum_runs", {})

    client = TestClient(main.app)
    response = client.get("/api/quantum/job/existing-job-987")
    body = response.json()

    assert response.status_code == 200
    assert calls["job_lookups"] == ["existing-job-987"]
    assert calls["submissions"] == 0
    assert body["status"] == "completed"
    assert body["job_status"] == "DONE"
    assert body["backend"] == "ibm_fez"
    assert body["shots"] == 5
    assert body["measurement_counts"] == {"001": 3, "110": 2}
    assert body["metadata_available"] is False
    assert body["decoded_solution"] is None
    assert body["recommendations"] == []
    assert body["execution_performed"] is False


def test_existing_queued_job_is_reported_without_result_lookup(monkeypatch):
    calls = {"result": 0}

    class FakeJob:
        def status(self):
            return "QUEUED"

        def backend(self):
            return SimpleNamespace(name="ibm_fez")

        def result(self):
            calls["result"] += 1
            raise AssertionError("Queued jobs must not request results.")

    class FakeService:
        def __init__(self, name):
            assert name == "optical-qpu"

        def job(self, job_id):
            assert job_id == "queued-job-123"
            return FakeJob()

    monkeypatch.setitem(
        sys.modules,
        "qiskit_ibm_runtime",
        SimpleNamespace(QiskitRuntimeService=FakeService),
    )
    monkeypatch.setattr(main, "quantum_runs", {})

    response = TestClient(main.app).get("/api/quantum/job/queued-job-123")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "queued"
    assert body["job_status"] == "QUEUED"
    assert body["result_retrieved"] is False
    assert body["execution_performed"] is False
    assert calls["result"] == 0


@pytest.mark.parametrize(
    ("job_status", "expected_status"),
    [("CANCELLED", "cancelled"), ("ERROR", "failed")],
)
def test_existing_terminal_job_status_is_preserved(
    monkeypatch,
    job_status,
    expected_status,
):
    class FakeJob:
        def status(self):
            return job_status

        def backend(self):
            return SimpleNamespace(name="ibm_fez")

        def result(self):
            raise AssertionError("Failed or cancelled jobs have no result retrieval.")

    class FakeService:
        def __init__(self, name):
            assert name == "optical-qpu"

        def job(self, job_id):
            assert job_id == "terminal-job-123"
            return FakeJob()

    monkeypatch.setitem(
        sys.modules,
        "qiskit_ibm_runtime",
        SimpleNamespace(QiskitRuntimeService=FakeService),
    )
    monkeypatch.setattr(main, "quantum_runs", {})

    response = TestClient(main.app).get("/api/quantum/job/terminal-job-123")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == expected_status
    assert body["job_status"] == job_status
    assert body["result_retrieved"] is False
    assert body["execution_performed"] is False


def test_missing_existing_job_surfaces_sanitized_error_without_resubmission(monkeypatch):
    class FakeService:
        def __init__(self, name):
            assert name == "optical-qpu"

        def job(self, job_id):
            raise RuntimeError("IBM job not found")

    monkeypatch.setitem(
        sys.modules,
        "qiskit_ibm_runtime",
        SimpleNamespace(QiskitRuntimeService=FakeService),
    )
    monkeypatch.setattr(main, "quantum_runs", {})

    response = TestClient(main.app).get("/api/quantum/job/missing-job-123")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["error_type"] == "RuntimeError"
    assert "IBM job not found" in body["error"]
    assert body["metadata_available"] is False
    assert body["execution_performed"] is False


def test_quantum_run_metadata_survives_backend_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "quantum_run_storage", tmp_path)
    monkeypatch.setattr(main, "quantum_runs", {})
    persisted = {
        "run_id": "0123456789abcdef0123456789abcdef",
        "job_id": "ibm-job-abc123",
        "backend": "ibm_fez",
        "shots": 128,
        "requested_shots": 128,
        "num_qubo_variables": 4,
        "qubo_variable_names": [
            "x0",
            "max_actions@int_slack@0",
            "max_actions@int_slack@1",
            "max_actions@int_slack@2",
        ],
        "candidate_variable_names": ["x0"],
        "measurement_bit_order": "qiskit_counts_msb_to_lsb",
        "qaoa_beta": 1.1,
        "qaoa_gamma": -0.1,
        "max_actions": 4,
        "candidates": [_candidate("device-a", 10)],
        "source": "simulator",
        "data_origin": "simulator",
        "completed_response": None,
    }
    main._persist_quantum_run(persisted["run_id"], persisted)

    class FakeService:
        def __init__(self, name):
            assert name == "optical-qpu"

        def job(self, job_id):
            assert job_id == "ibm-job-abc123"
            return "restored-job-object"

    monkeypatch.setitem(
        sys.modules,
        "qiskit_ibm_runtime",
        SimpleNamespace(QiskitRuntimeService=FakeService),
    )

    restored = main._restore_quantum_run(persisted["run_id"])

    assert restored["job"] == "restored-job-object"
    assert restored["candidates"] == persisted["candidates"]
    assert restored["num_qubo_variables"] == 4
    assert restored["max_actions"] == 4
