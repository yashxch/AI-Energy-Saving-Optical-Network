import asyncio
import re

import pytest

import server
from server import build_lookup_script, parse_connection_request, run_lookup_task, startup_command


def test_startup_command_runs_snml_database_session() -> None:
    assert startup_command("snml") == (
        "docker exec -it database bash -lc "
        "'cd / && . ./usr/Systems/OTNE_1/.snmlrc && exec sqlplus /@snml_alias'"
    )


def test_parse_connection_request_normalizes_address_and_preserves_credentials() -> None:
    assert parse_connection_request(
        {"host": " 192.168.1.20 ", "password": "secret"}
    ) == ("192.168.1.20", "secret")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"host": "host.example", "password": "p"}, "IPv4 or IPv6"),
        ({"host": "0.0.0.0", "password": "p"}, "cannot be used"),
        ({"host": "192.168.1.20", "password": ""}, "password"),
    ],
)
def test_parse_connection_request_rejects_invalid_values(payload: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_connection_request(payload)


@pytest.mark.parametrize(
    ("payload", "expected_sql"),
    [
        (
            {"step": 1, "userlabel": "NE-01"},
            "SELECT neid, userlabel FROM ason_ne WHERE userlabel LIKE '%NE-01';",
        ),
        (
            {"step": 2, "nename": "NE-01"},
            "SELECT connectid, portconnid, userlabel FROM ason_connec WHERE userlabel LIKE '%NE-01%';",
        ),
        (
            {"step": 3, "connectids": ["1001", "1002"]},
            "SELECT routeid, connectid FROM rouphc WHERE connectid IN ('1001', '1002');",
        ),
        (
            {"step": 4, "connectids": ["1001"]},
            "SELECT trailid, routeid, connectid FROM trail WHERE connectid IN ('1001');",
        ),
        (
            {"step": 5, "trailids": ["TR-1"]},
            "SELECT lcid, trailid FROM lc WHERE trailid IN ('TR-1');",
        ),
    ],
)
def test_lookup_steps_build_fixed_select_queries(payload: dict, expected_sql: str) -> None:
    step, token, query, script = build_lookup_script(payload)
    assert step == payload["step"]
    assert expected_sql == query
    assert expected_sql in script
    assert f"__SNML_LOOKUP_BEGIN_{token}__" in script
    assert f"__SNML_LOOKUP_END_{token}__" in script


def test_lookup_sql_escapes_quotes_and_rejects_control_characters() -> None:
    _, _, _, script = build_lookup_script({"step": 1, "userlabel": "NE'01"})
    assert "WHERE userlabel LIKE '%NE''01'" in script
    with pytest.raises(ValueError, match="control characters"):
        build_lookup_script({"step": 1, "userlabel": "NE-01\n"})


def test_lookup_task_returns_parsed_csv_rows() -> None:
    class FakeChannel:
        def __init__(self) -> None:
            self.output = b""
            self.script = ""

        def sendall(self, value: bytes) -> None:
            script = value.decode("utf-8")
            self.script = script
            begin = re.search(r"PROMPT (__SNML_LOOKUP_BEGIN_[0-9a-f]+__)", script).group(1)
            end = re.search(r"PROMPT (__SNML_LOOKUP_END_[0-9a-f]+__)", script).group(1)
            self.output = (
                f"PROMPT {begin}\r\nSELECT neid, userlabel FROM ason_ne WHERE userlabel LIKE '%Example NE';\r\nSQL> {begin}\r\n"
                'NEID,USERLABEL\r\n"NE,01","Example NE"\r\n'
                f"PROMPT {end}\r\nSQL> {end}"
            ).encode()

        def recv_ready(self) -> bool:
            return bool(self.output)

        def recv(self, size: int) -> bytes:
            chunk, self.output = self.output[:size], self.output[size:]
            return chunk

    class FakeWebSocket:
        def __init__(self) -> None:
            self.messages: list[dict] = []

        async def receive_json(self) -> dict:
            await asyncio.sleep(0.001)
            return {}

        async def send_json(self, message: dict) -> None:
            self.messages.append(message)
            self.message = message

    websocket = FakeWebSocket()
    channel = FakeChannel()
    asyncio.run(
        run_lookup_task(
            websocket,  # type: ignore[arg-type]
            channel,  # type: ignore[arg-type]
            {"step": 1, "userlabel": "Example NE"},
        )
    )
    assert websocket.message == {
        "type": "lookup_result",
        "step": 1,
        "query": "SELECT neid, userlabel FROM ason_ne WHERE userlabel LIKE '%Example NE';",
        "output": 'NEID,USERLABEL\n"NE,01","Example NE"\n',
        "rows": [{"NEID": "NE,01", "USERLABEL": "Example NE"}],
    }
    assert websocket.messages[0] == {
        "type": "lookup_started",
        "step": 1,
        "query": "SELECT neid, userlabel FROM ason_ne WHERE userlabel LIKE '%Example NE';",
    }
    assert any(message["type"] == "lookup_output" for message in websocket.messages)
    assert "SELECT neid, userlabel FROM ason_ne WHERE userlabel LIKE '%Example NE';\n" in channel.script


def test_ssh_login_automatically_opens_snml_and_forwards_terminal_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeChannel:
        def __init__(self) -> None:
            self.sent: list[str] = []
            self.output = b""

        def sendall(self, value: bytes) -> None:
            text = value.decode("utf-8")
            self.sent.append(text)
            if text.startswith("docker exec"):
                self.output = b"SQL> "
            elif text.startswith("SELECT"):
                self.output = b"1 row selected.\r\nSQL> "

        def recv_ready(self) -> bool:
            return bool(self.output)

        def recv(self, size: int) -> bytes:
            chunk, self.output = self.output[:size], self.output[size:]
            return chunk

        def exit_status_ready(self) -> bool:
            return False

        def close(self) -> None:
            pass

    class FakeSSHClient:
        def __init__(self) -> None:
            self.channel = FakeChannel()

        def load_system_host_keys(self) -> None:
            pass

        def set_missing_host_key_policy(self, _policy: object) -> None:
            pass

        def connect(self, **kwargs: object) -> None:
            assert kwargs.get("username") == "root"

        def invoke_shell(self, **_kwargs: object) -> FakeChannel:
            return self.channel

        def close(self) -> None:
            pass

    client = FakeSSHClient()
    monkeypatch.setattr(server.paramiko, "SSHClient", lambda: client)

    class FakeWebSocket:
        headers = {"origin": "http://testserver", "host": "testserver"}

        def __init__(self) -> None:
            self.incoming = [
                {"host": "192.168.1.20", "password": "secret"},
                {"type": "input", "data": "SELECT 1 FROM dual;\r"},
                {"type": "close"},
            ]
            self.outgoing: list[dict] = []

        async def accept(self) -> None:
            pass

        async def receive_json(self) -> dict:
            return self.incoming.pop(0)

        async def send_json(self, message: dict) -> None:
            self.outgoing.append(message)

        async def close(self, **kwargs: object) -> None:
            pass

    websocket = FakeWebSocket()

    async def run_session() -> None:
        await server.terminal(websocket)  # type: ignore[arg-type]

    asyncio.run(run_session())

    assert websocket.outgoing[0]["stage"] == "ssh_authenticated"
    assert websocket.outgoing[1] == {"type": "output", "data": "SQL> "}
    assert websocket.outgoing[2]["stage"] == "database_open"
    assert client.channel.sent == [
        startup_command("snml") + "\n",
        "SELECT 1 FROM dual;\r",
    ]
    assert any(message.get("data") == "1 row selected.\r\nSQL> " for message in websocket.outgoing)
