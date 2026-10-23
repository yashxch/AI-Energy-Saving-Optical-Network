# Standalone SNML Database Console

This folder contains an independent interface and SSH bridge. It does not depend on or modify the optical network dashboard.

## Run

From this folder, install the requirements and start the local server:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765>, enter the Linux server IP and root password, then select **Connect to SNML**. After SSH authentication, the bridge starts:

`docker exec -it database bash -lc 'cd / && . ./usr/Systems/OTNE_1/.snmlrc && exec sqlplus /@snml_alias'`

When the SQL*Plus prompt is ready, enter SQL*Plus commands in the terminal pane. Press Enter to send a line and Ctrl+C to interrupt. The session has no idle timeout and remains open until you select **Disconnect session** or the remote SSH/SQL*Plus process ends. SSH connection and authentication attempts still have limits while establishing the connection. Use `exit` to leave SQL*Plus and **Disconnect session** to close SSH.

## Read-only network lookup

After connecting, enter a user label and click **Find network element**. The console searches `ASON_NE` by user-label suffix and automatically processes every matching `NEID`/`USERLABEL` row; no row selection or follow-up SQL input is required. For each match, it queries `ASON_CONNEC` for `CONNECTID`, `PORTCONNID`, and `USERLABEL`, then `ROUPHC` for `ROUTEID` by the returned `CONNECTID` values, `TRAIL` for `TRAILID`, `ROUTEID`, and `CONNECTID` by those same `CONNECTID` values, and `LC` for `LCID` by the returned `TRAILID` values. Results from all matched network elements are shown in the corresponding tables with `NEID` and `NE_USERLABEL` columns for context.

The browser presents each result set in its own table. These lookup requests are fixed `SELECT` statements only; no changes are made to the database. A lookup waits for SQL*Plus to finish or for you to disconnect. Actual availability depends on the connected Oracle user's schema permissions and the database's table/column names.

Below the lookup controls, the **SQL*Plus execution and captured output** window shows the exact query sent for each step and the raw output returned by SQL*Plus. The backend logs when each step is sent, completed with a captured row count, or fails.

## SSH host keys and security

The server rejects unknown SSH host keys. Before the first connection, add the server's key to the backend process user's SSH `known_hosts` file and verify its fingerprint out-of-band. Do not disable host-key checking.

The password is not stored; it is used only to authenticate the SSH connection. The SSH username, port, Docker container name, and SNML startup command are fixed in `server.py`. The terminal grants access to SQL*Plus commands. Keep this console on a trusted machine/network. Do not expose it publicly without authentication and TLS at a trusted reverse proxy, restrict network access, and use HTTPS/WSS. The built-in origin check is not authentication.

To let another computer access this server, configure deployment-level access controls and TLS, then bind Uvicorn to an appropriate interface (for example, `--host 0.0.0.0`) only behind those controls.
