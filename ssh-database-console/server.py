import asyncio
import csv
import io
import ipaddress
import logging
import re
import secrets
import shlex
from pathlib import Path
from urllib.parse import urlsplit

import paramiko
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse


app = FastAPI(title="Standalone SSH Database Console")
HTML_FILE = Path(__file__).with_name("index.html")
logger = logging.getLogger(__name__)
DATABASES = {
    "snml": ("./usr/Systems/OTNE_1/.snmlrc", "snml_alias"),
}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(HTML_FILE)


def validate_origin(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    request_host = websocket.headers.get("host")
    if not origin or not request_host:
        return False
    parsed_origin = urlsplit(origin)
    return (
        parsed_origin.scheme in {"http", "https"}
        and parsed_origin.netloc.lower() == request_host.lower()
        and parsed_origin.path in {"", "/"}
        and not parsed_origin.query
        and not parsed_origin.fragment
    )


def parse_connection_request(payload: object) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Invalid connection request.")

    host = payload.get("host")
    password = payload.get("password")
    if not isinstance(host, str):
        raise ValueError("Enter a valid IP address.")
    try:
        address = ipaddress.ip_address(host.strip())
    except ValueError as exc:
        raise ValueError("Enter a valid IPv4 or IPv6 address.") from exc
    if address.is_unspecified or address.is_multicast:
        raise ValueError("This IP address cannot be used as an SSH destination.")
    if not isinstance(password, str) or not password or len(password) > 1024:
        raise ValueError("Enter a password of up to 1024 characters.")

    return str(address), password


def startup_command(database: str) -> str:
    rc_file, alias = DATABASES[database]
    shell_command = f"cd / && . {rc_file} && exec sqlplus /@{alias}"
    return f"docker exec -it database bash -lc {shlex.quote(shell_command)}"


def build_lookup_script(payload: object) -> tuple[int, str, str, str]:
    if not isinstance(payload, dict):
        raise ValueError("Invalid SNML lookup request.")
    step = payload.get("step")
    if not isinstance(step, int) or step not in {1, 2, 3, 4, 5}:
        raise ValueError("Unknown SNML lookup step.")

    def required_text(key: str, label: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError(f"Enter a valid {label}.")
        if re.search(r"[\x00-\x1f\x7f]", value):
            raise ValueError(f"{label.capitalize()} cannot contain control characters.")
        return value.strip()

    def sql_literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    if step == 1:
        userlabel = required_text("userlabel", "user label")
        query = (
            "SELECT neid, userlabel FROM ason_ne "
            f"WHERE userlabel LIKE {sql_literal('%' + userlabel)}"
        )
    elif step == 2:
        nename = required_text("nename", "NE name")
        query = (
            "SELECT connectid, portconnid, userlabel FROM ason_connec "
            f"WHERE userlabel LIKE {sql_literal('%' + nename + '%')}"
        )
    elif step == 3:
        connectids = payload.get("connectids")
        if not isinstance(connectids, list) or not connectids or len(connectids) > 500:
            raise ValueError("No CONNECTID values were supplied.")
        values = [required_text_value(value, "CONNECTID") for value in connectids]
        query = (
            "SELECT routeid, connectid FROM rouphc "
            f"WHERE connectid IN ({', '.join(sql_literal(value) for value in values)})"
        )
    elif step == 4:
        connectids = payload.get("connectids")
        if not isinstance(connectids, list) or not connectids or len(connectids) > 500:
            raise ValueError("No CONNECTID values were supplied.")
        values = [required_text_value(value, "CONNECTID") for value in connectids]
        query = (
            "SELECT trailid, routeid, connectid FROM trail "
            f"WHERE connectid IN ({', '.join(sql_literal(value) for value in values)})"
        )
    else:
        trailids = payload.get("trailids")
        if not isinstance(trailids, list) or not trailids or len(trailids) > 500:
            raise ValueError("No TRAILID values were supplied.")
        values = [required_text_value(value, "TRAILID") for value in trailids]
        query = (
            "SELECT lcid, trailid FROM lc "
            f"WHERE trailid IN ({', '.join(sql_literal(value) for value in values)})"
        )

    query += ";"
    token = secrets.token_hex(16)
    script = (
        "SET ECHO OFF\n"
        "SET MARKUP CSV ON DELIMITER , QUOTE ON\n"
        "SET FEEDBACK OFF\n"
        "SET PAGESIZE 50000\n"
        f"PROMPT __SNML_LOOKUP_BEGIN_{token}__\n"
        f"{query}\n"
        "SET MARKUP CSV OFF\n"
        "SET FEEDBACK ON\n"
        "SET ECHO ON\n"
        "SET PAGESIZE 14\n"
        f"PROMPT __SNML_LOOKUP_END_{token}__\n"
    )
    return step, token, query, script


def required_text_value(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"Invalid {label} value.")
    if re.search(r"[\x00-\x1f\x7f]", value):
        raise ValueError(f"Invalid {label} value.")
    return value.strip()


async def run_lookup_task(websocket: WebSocket, channel: paramiko.Channel, payload: object) -> None:
    try:
        step, token, query, script = build_lookup_script(payload)
    except ValueError as exc:
        await websocket.send_json({"type": "lookup_error", "message": str(exc)})
        return

    start_marker = f"__SNML_LOOKUP_BEGIN_{token}__"
    end_marker = f"__SNML_LOOKUP_END_{token}__"
    echoed_lines = {
        line.strip()
        for line in script.splitlines()
        if line.strip() and not line.lstrip().upper().startswith("PROMPT ")
    }
    await asyncio.to_thread(channel.sendall, script.encode("utf-8"))
    await websocket.send_json({"type": "lookup_started", "step": step, "query": query})
    logger.info("SNML lookup step %d query sent to SQL*Plus", step)
    buffer = ""
    captured: list[str] = []
    capturing = False

    async def process_line(line: str) -> bool:
        nonlocal capturing
        clean_line = re.sub(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", line).strip()
        if start_marker in clean_line:
            capturing = True
        elif end_marker in clean_line:
            output = "".join(captured)
            if re.search(r"^\s*(?:ORA|SP2)-\d{4,5}\b", output, re.MULTILINE):
                logger.warning("SNML lookup step %d returned a SQL*Plus error", step)
                await websocket.send_json(
                    {
                        "type": "lookup_error",
                        "step": step,
                        "query": query,
                        "message": output.strip(),
                        "output": output,
                    }
                )
            else:
                records = list(csv.reader(io.StringIO(output)))
                records = [row for row in records if any(value.strip() for value in row)]
                columns = [value.strip().upper() for value in records[0]] if records else []
                rows = [
                    {column: row[index].strip() if index < len(row) else "" for index, column in enumerate(columns)}
                    for row in records[1:]
                ]
                logger.info("SNML lookup step %d completed: %d row(s) captured", step, len(rows))
                await websocket.send_json(
                    {"type": "lookup_result", "step": step, "query": query, "output": output, "rows": rows}
                )
            return True
        elif capturing and clean_line.startswith("PROMPT __SNML_LOOKUP_"):
            return False
        elif capturing and clean_line in echoed_lines:
            return False
        elif capturing:
            captured.append(line + "\n")
        return False

    while True:
        try:
            event = await asyncio.wait_for(websocket.receive_json(), timeout=0.03)
        except asyncio.TimeoutError:
            event = None
        except WebSocketDisconnect:
            return

        if isinstance(event, dict) and event.get("type") == "close":
            return

        while channel.recv_ready():
            chunk = channel.recv(65536).decode("utf-8", errors="replace")
            await websocket.send_json({"type": "lookup_output", "step": step, "data": chunk})
            buffer += chunk.replace("\r\n", "\n").replace("\r", "\n")
            if len(buffer) > 2_000_000:
                await websocket.send_json(
                    {"type": "lookup_error", "step": step, "message": "Lookup output exceeded the 2 MB limit."}
                )
                logger.warning("SNML lookup step %d failed: output exceeded 2 MB", step)
                return

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if await process_line(line):
                    return

            if end_marker in buffer and await process_line(buffer):
                return


@app.websocket("/terminal")
async def terminal(websocket: WebSocket) -> None:
    if not validate_origin(websocket):
        await websocket.close(code=1008, reason="Origin is not allowed.")
        return

    await websocket.accept()
    ssh_client: paramiko.SSHClient | None = None
    channel: paramiko.Channel | None = None
    payload = None
    try:
        try:
            payload = await asyncio.wait_for(websocket.receive_json(), timeout=30)
            host, password = parse_connection_request(payload)
        except asyncio.TimeoutError:
            await websocket.send_json({"type": "error", "message": "Connection details timed out."})
            return
        except ValueError as exc:
            if isinstance(payload, dict):
                payload.clear()
            await websocket.send_json({"type": "error", "message": str(exc)})
            return

        ssh_client = paramiko.SSHClient()
        ssh_client.load_system_host_keys()
        ssh_client.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            await asyncio.to_thread(
                ssh_client.connect,
                hostname=host,
                port=22,
                username="root",
                password=password,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
        finally:
            password = ""
            if isinstance(payload, dict):
                payload.clear()

        channel = await asyncio.to_thread(
            ssh_client.invoke_shell,
            term="xterm-256color",
            width=120,
            height=36,
        )
        await websocket.send_json(
            {
                "type": "status",
                "stage": "ssh_authenticated",
                "message": f"SSH login successful: {host} as root. Starting SNML SQL*Plus.",
            }
        )
        await asyncio.to_thread(channel.sendall, (startup_command("snml") + "\n").encode("utf-8"))
        prompt_buffer = ""
        pending_events: list[object] = []
        database_ready = False
        while not database_ready:
            try:
                event = await asyncio.wait_for(websocket.receive_json(), timeout=0.03)
            except asyncio.TimeoutError:
                event = None
            except WebSocketDisconnect:
                return
            if isinstance(event, dict) and event.get("type") == "close":
                return
            if event is not None:
                pending_events.append(event)

            if channel.recv_ready():
                chunk = channel.recv(65536).decode("utf-8", errors="replace")
                await websocket.send_json({"type": "output", "data": chunk})
                prompt_buffer = (prompt_buffer + chunk)[-4096:]
                clean_prompt = re.sub(
                    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])",
                    "",
                    prompt_buffer,
                )
                if re.search(r"SQL>\s*$", clean_prompt):
                    database_ready = True
                    break
            elif channel.exit_status_ready():
                break
        if not database_ready:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "The SNML SQL*Plus session ended before its prompt became ready.",
                }
            )
            return
        await websocket.send_json(
            {
                "type": "status",
                "stage": "database_open",
                "database": "snml",
                "message": "SNML SQL*Plus prompt is ready.",
            }
        )

        while True:
            if pending_events:
                event = pending_events.pop(0)
            else:
                try:
                    event = await asyncio.wait_for(websocket.receive_json(), timeout=0.03)
                except asyncio.TimeoutError:
                    event = None
                except ValueError:
                    await websocket.send_json({"type": "error", "message": "Received an invalid terminal message."})
                    break

            if isinstance(event, dict) and event.get("type") == "input":
                data = event.get("data")
                if isinstance(data, str) and len(data) <= 4096:
                    await asyncio.to_thread(channel.sendall, data.encode("utf-8"))
            elif isinstance(event, dict) and event.get("type") == "lookup":
                await run_lookup_task(websocket, channel, event)
            elif isinstance(event, dict) and event.get("type") == "close":
                break

            while channel.recv_ready():
                output = channel.recv(65536)
                if not output:
                    break
                await websocket.send_json(
                    {"type": "output", "data": output.decode("utf-8", errors="replace")}
                )

            if channel.exit_status_ready():
                await websocket.send_json({"type": "status", "message": "The SQL*Plus session ended."})
                break
    except WebSocketDisconnect:
        pass
    except paramiko.AuthenticationException:
        await websocket.send_json({"type": "error", "message": "SSH authentication failed. Check the root password."})
    except paramiko.BadHostKeyException:
        await websocket.send_json(
            {"type": "error", "message": "SSH host-key verification failed; verify the server key in known_hosts."}
        )
    except paramiko.SSHException as exc:
        await websocket.send_json({"type": "error", "message": f"SSH connection failed: {exc}"})
    except (TimeoutError, OSError) as exc:
        await websocket.send_json({"type": "error", "message": f"Could not reach the SSH server: {exc}"})
    finally:
        if channel is not None:
            channel.close()
        if ssh_client is not None:
            ssh_client.close()
