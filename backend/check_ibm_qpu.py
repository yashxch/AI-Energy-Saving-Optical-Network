"""Check IBM Quantum hardware access without submitting a job."""

import re
import sys


ACCOUNT_NAME = "optical-qpu"
CHANNEL = "ibm_quantum_platform"
INSTANCE = "open-instance"


def _safe_error(message: str) -> str:
    return re.sub(
        r"\b[A-Za-z0-9_-]{32,}\b",
        "[REDACTED]",
        message,
    )


def _report_failure(status: str, exc: Exception) -> int:
    print(f"RESULT: {status}")
    print(f"Error type: {type(exc).__name__}")
    print(f"Error: {_safe_error(str(exc))}")
    return 1


def main() -> int:
    print("Python executable:", sys.executable)
    try:
        import qiskit
        import qiskit_ibm_runtime
        from qiskit_ibm_runtime import QiskitRuntimeService
    except ImportError as exc:
        return _report_failure("ENVIRONMENT_OR_DEPENDENCY_ERROR", exc)

    print("Qiskit version:", qiskit.__version__)
    print("IBM Runtime version:", qiskit_ibm_runtime.__version__)

    try:
        saved = QiskitRuntimeService.saved_accounts()
    except Exception as exc:
        return _report_failure("ENVIRONMENT_OR_DEPENDENCY_ERROR", exc)

    if ACCOUNT_NAME not in saved:
        print(f"RESULT: ENVIRONMENT_OK_CREDENTIALS_MISSING")
        print(f"No saved IBM account named '{ACCOUNT_NAME}' was found.")
        return 2

    account = saved[ACCOUNT_NAME]
    account_channel = account.get("channel")
    account_instance = account.get("instance")
    token_present = bool(account.get("token"))
    print("Saved account alias:", ACCOUNT_NAME)
    print("Saved channel:", account_channel or "not recorded")
    print("Saved instance:", account_instance or "not recorded")
    print("Credential present:", token_present)

    if not token_present:
        print("RESULT: ENVIRONMENT_OK_CREDENTIALS_MISSING")
        print("The named account has no saved token.")
        return 2

    if account_channel != CHANNEL:
        print("RESULT: ENVIRONMENT_OK_AUTHENTICATION_FAILED")
        print(
            f"The account channel is {account_channel!r}; "
            f"expected {CHANNEL!r}."
        )
        return 1

    if account_instance != INSTANCE:
        print("RESULT: ENVIRONMENT_OK_NO_ACCESSIBLE_HARDWARE")
        print(
            f"The saved instance is {account_instance!r}; "
            f"expected confirmed instance {INSTANCE!r}."
        )
        return 1

    try:
        service = QiskitRuntimeService(
            name=ACCOUNT_NAME,
            channel=CHANNEL,
            instance=INSTANCE,
        )
        backends = service.backends(instance=INSTANCE)
    except Exception as exc:
        error_name = type(exc).__name__.lower()
        if any(word in error_name for word in ("auth", "unauthor", "forbidden")):
            status = "ENVIRONMENT_OK_AUTHENTICATION_FAILED"
        else:
            status = "ENVIRONMENT_OK_NO_ACCESSIBLE_HARDWARE"
        return _report_failure(status, exc)

    print(f"Instance '{INSTANCE}' responded; backends returned: {len(backends)}")
    operational_hardware = []
    for backend in backends:
        try:
            is_simulator = bool(backend.simulator)
            status = backend.status()
            qubits = backend.num_qubits
            print(
                f"Backend: {backend.name}; "
                f"type={'simulator' if is_simulator else 'hardware'}; "
                f"operational={status.operational}; "
                f"status={status.status_msg}; "
                f"pending_jobs={status.pending_jobs}; "
                f"qubits={qubits}"
            )
            if not is_simulator and status.operational:
                operational_hardware.append((backend, qubits))
        except Exception as exc:
            print(
                f"Backend status check failed for {backend.name}: "
                f"{type(exc).__name__}: {_safe_error(str(exc))}"
            )

    if not operational_hardware:
        print("RESULT: ENVIRONMENT_OK_NO_ACCESSIBLE_HARDWARE")
        print("No operational hardware backend was confirmed.")
        return 1

    selected, qubits = max(operational_hardware, key=lambda item: item[1])
    print(
        f"Recommended operational hardware backend: {selected.name} "
        f"({qubits} qubits). No job was submitted."
    )
    print("RESULT: ENVIRONMENT_OK_CREDENTIALS_OK_HARDWARE_ACCESS_CONFIRMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
