"""Save an IBM Quantum Platform account without exposing its API key."""

import argparse
import getpass
import re
import sys


CHANNEL = "ibm_quantum_platform"
ACCOUNT_NAME = "optical-qpu"


def _safe_error(message: str, token: str) -> str:
    if token:
        message = message.replace(token, "[REDACTED]")
    return re.sub(
        r"\b[A-Za-z0-9_-]{32,}\b",
        "[REDACTED]",
        message,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Save a named IBM Quantum Platform credential locally."
    )
    parser.add_argument(
        "--instance",
        required=True,
        help="Exact IBM Quantum Platform instance name or CRN.",
    )
    args = parser.parse_args()

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except ImportError as exc:
        print(f"Dependency error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    try:
        if ACCOUNT_NAME in QiskitRuntimeService.saved_accounts():
            print(
                f"Account '{ACCOUNT_NAME}' already exists. "
                "No credentials were changed; remove or rename that account "
                "explicitly before retrying.",
                file=sys.stderr,
            )
            return 2

        token = getpass.getpass("IBM Quantum API key (input hidden): ").strip()
        if not token:
            print("No API key entered; no credentials were saved.", file=sys.stderr)
            return 2

        try:
            QiskitRuntimeService.save_account(
                channel=CHANNEL,
                token=token,
                instance=args.instance,
                name=ACCOUNT_NAME,
                overwrite=False,
                set_as_default=False,
            )
        except Exception as exc:
            print(
                f"Credential save failed: {type(exc).__name__}: "
                f"{_safe_error(str(exc), token)}",
                file=sys.stderr,
            )
            return 1
        finally:
            token = ""

    except (EOFError, KeyboardInterrupt):
        print("\nCredential setup cancelled; no key was saved.", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Credential setup failed: {type(exc).__name__}.", file=sys.stderr)
        return 1

    print(
        f"Saved IBM account '{ACCOUNT_NAME}' locally "
        f"(channel={CHANNEL}, instance={args.instance})."
    )
    print("The API key was not displayed and was not written to the project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
