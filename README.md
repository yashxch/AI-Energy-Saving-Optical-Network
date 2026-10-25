# AI-Based Power Saving in Optical Networks

## Project Name
AI-Based Power Saving in Optical Networks

## Project Description
An intelligent, autonomous energy optimization and network management platform modeled after Nokia 1830 PSS optical transport network architectures. The platform integrates a real-time telemetry simulator of 100 optical transport devices (800G Muxponders, Variable Gain EDFA Amplifiers, ROADMs, and Optical Filter Cards) across 8 major US network nodes (NYC, BOS, CHI, WDC, ATL, DAL, SFO, LAX).

Key features include:
- **ML Traffic Prediction Engine**: Time-series forecasting for network traffic over 5m, 1h, and 24h horizons using linear & moving-average models.
- **Anomaly Detection Engine**: Real-time detection of high Bit Error Rate (BER), thermal spikes, Optical Signal-to-Noise Ratio (OSNR) drops, and power anomalies.
- **LLM Energy Recommendation Engine**: Generates action-oriented energy-saving recommendations (deep transponder sleep, amplifier gain tuning, traffic rerouting).
- **Optical SLA Policy Engine**: Rigorously validates all proposed actions against carrier SLAs, QoS thresholds (99.99%), pre-FEC BER limits ($\le 1.0 \times 10^{-4}$), OSNR margins ($\ge 14.5 \text{ dB}$), and 1+1 Optical Supervisory Channel (OSC) protection paths.
- **FCAPS Telecommunications Management**: Full Fault, Configuration, Accounting, Performance, and Security logging with live energy kW and carbon emission reduction tracking.
- **Telecom AI Chatbot**: Natural language query interface powered by optical network domain context for real-time network query and diagnostics.
- **Modern Interactive Dashboard**: Next.js 14 frontend built with TailwindCSS and Recharts for dynamic visual control and monitoring.

## College Name
SRM Institute of Science and Technology

## Total number of months
3 months 

## Project Start Date
July 2026

## Nokia Mentor
- Varun Gupta
- Sandeep Dabhade
- Amit Tilwankar

## College Mentor
- Dr. J. Justina Michael

## Students
- Yashwanth Ch 
- Anwesha Pattanayak
- Chelsea Sharma

---

## Users guide

### Installation

#### Describe how one can get and install your project

##### 1. Repository Cloning & Python Virtual Environment Setup (Python Script / FastAPI Backend)
This project consists of a Python FastAPI backend and a Next.js 14 Node.js frontend. Follow the steps below to clone the repository and install all required dependencies using a Python Virtual Environment (`venv`):

```bash
# Step 1: Clone the repository from GitHub
git clone https://github.com/university-connect/ai-power-saving-optical-networks.git
cd ai-power-saving-optical-networks

# Step 2: Create a Python virtual environment (recommended to isolate dependencies)
python -m venv venv

# Step 3: Activate the virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (Command Prompt):
.\venv\Scripts\activate.bat
# On Linux/macOS:
source venv/bin/activate

# Step 4: Install backend Python dependencies
pip install --upgrade pip
pip install -r backend/requirements.txt
```

##### 2. Frontend Dependencies Installation (Next.js / Node.js)
```bash
# Navigate to the frontend directory
cd frontend

# Install Node modules via npm
npm install

# Return to root directory
cd ..
```

##### 3. Compilation Requirements (e.g. Go, C++)
This project is written in **Python 3.10+** (FastAPI) and **TypeScript/JavaScript** (Next.js 14). **No compilation step (like Go or C++) is required** before execution. Python scripts run directly via the Uvicorn ASGI server, and Next.js handles on-demand compilation during development (`npm run dev`) or optional static bundle production (`npm run build`).

##### 4. Containerization (Docker Support)
While running natively via Python and Node.js is the default, the project can also be containerized using Docker. To build and run using Docker:

```bash
# Build Docker image for backend
docker build -t optical-network-backend ./backend

# Run backend container on port 8000
docker run -d -p 8000:8000 --name backend-service optical-network-backend

# Build Docker image for frontend
docker build -t optical-network-frontend ./frontend

# Run frontend container on port 3000
docker run -d -p 3000:3000 --name frontend-service optical-network-frontend
```

---

### Usage

#### Explain how people can use your project

To run the full stack application, start both the backend API server and the frontend Next.js web application.

##### Step 1: Start the Backend API Server
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The FastAPI backend server will start at `http://127.0.0.1:8000`. You can inspect and test interactive API documentation (Swagger UI) at `http://127.0.0.1:8000/docs`.

##### Step 2: Start the Frontend Dashboard UI
In a separate terminal window:
```bash
cd frontend
npm run dev
```
Open your browser and navigate to `http://localhost:3000` to interact with the live telemetry dashboard, AI recommendations, FCAPS alarms, and Telecom Chatbot.

##### Nokia project-folder CSV telemetry
The backend reads these two configured files directly from the repository root when it starts:

- `NOKIA-001_telemetry_60_rows_siteB_S4X400_with_anomalies.csv`
- `NOKIA-003_PSIM-NEW-UPPER-SITE-A_SMF6_60_rows_Nokia_LAB_1sec_BER_scientific.csv`

No browser file upload is required. The Simulator and Nokia project-folder CSV modes remain selectable. The existing aggregated 15-minute, 865-element snapshot is not selected or used. If either configured project CSV is missing or invalid, the Nokia source reports an error rather than falling back to that snapshot or live Nokia endpoints. Update `nokia_csv_files` in `backend/app/config/policies.json` if the project-root filenames change.

Both supplied CSV schemas contain **16 numeric telemetry fields** each (in addition to identity, timestamp, and power-mode columns), not 12. The importer maps and displays all 16 observed fields rather than dropping or fabricating metrics. This is historical data, not a live Nokia connection; it does not authorize hardware commands or produce estimated or measured energy savings. Power-saving eligibility is withheld unless the configured 15-minute minimum observation window, 30-second telemetry-freshness limit, hardware support, and protected service capacity can all be verified.

##### IBM Quantum job retrieval
In **Quantum Optimization**, use **Retrieve Existing Job** to check an IBM Runtime job ID without submitting another job (`GET /api/quantum/job/{job_id}`). Completed jobs display measured counts; device recommendations are shown only when the candidate/QUBO metadata from that run is available for decoding and Digital Twin/Policy validation. New explicit QPU runs save their candidate mapping and run configuration under the ignored local `backend/.quantum_runs/` directory so polling can recover them after a backend restart. Do not treat a completed measurement as a validated recommendation when that metadata is unavailable.

---

#### Configuration parameters & Environmental variables expected

The application comes pre-configured with sensible defaults for local development. Optional environment variables can be customized:

| Environment Variable | Target Component | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `HOST` | Backend | `127.0.0.1` | IP interface host address for Uvicorn server |
| `PORT` | Backend | `8000` | Port for the backend FastAPI server |
| `NEXT_PUBLIC_API_URL` | Frontend | `http://127.0.0.1:8000` | URL endpoint of backend API accessed by Next.js |
| `NODE_ENV` | Frontend | `development` | Node environment (`development` or `production`) |

The default Nokia telemetry mode is configured for project-folder CSV telemetry. The configured `nokia_csv_files` list takes precedence over local snapshots and Nokia live endpoints. Do not remove the configured list if you want to keep Nokia mode restricted to the two project CSVs.

---

#### Command Line Parameters

##### Backend Execution (Uvicorn CLI Options)
- `--host TEXT`: Specifies bind socket host [default: `127.0.0.1`]
- `--port INT`: Specifies bind socket port [default: `8000`]
- `--reload`: Enables auto-reload on backend code changes during development
- `--workers INT`: Number of worker processes (used in production deployments)

##### Backend Test Suite CLI
- `python backend/test_backend.py`: Runs automated unit & integration test suite verifying simulator ticks, ML predictions, anomaly detection, policy validation, and chatbot functionality.

##### Frontend Scripts CLI (`npm`)
- `npm run dev`: Starts Next.js development server with hot-reloading on port 3000.
- `npm run build`: Compiles production build of Next.js dashboard.
- `npm run start`: Launches production server.
- `npm run lint`: Executes Next.js linter to verify TypeScript and syntax standards.

---

#### Input file expectations

1. **Telemetry & Network Topology**:
   - The simulator dynamically generates telemetry data for 100 Nokia 1830 PSS style optical devices across 8 US nodes (NYC, BOS, CHI, WDC, ATL, DAL, SFO, LAX).
   - No external input files are required to start the simulation.
2. **JSON Payloads for API Requests**:
   - Executing actions via `/api/actions/execute` expects `{"recommendation_id": "REC-..."}`.
   - Injecting faults via `/api/faults/inject` expects query parameters `device_id` and `fault_type` (`"high_ber"`, `"thermal_spike"`, `"osnr_drop"`, `"power_anomaly"`).
   - Chatbot queries via `/api/chatbot` expect `{"prompt": "Your question here"}`.

---

#### What users can expect from it

1. **Live Network Telemetry**: Continuous real-time stream of device operating parameters (Power consumption, Temperature, Pre-FEC BER, OSNR, Active Channels, Power Mode).
2. **AI Energy Optimizations**: Intelligent recommendations generated when network traffic drops (e.g. during off-peak hours), placing transponders into deep sleep or putting amplifiers in low-gain mode.
3. **Carrier SLA Enforcement**: Automated policy checks that prevent unsafe energy savings actions if OSNR drops below 14.5 dB or BER exceeds $1.0 \times 10^{-4}$.
4. **FCAPS Telecom Compliance**: Full visibility into active alarms, energy accounting (kW saved & carbon emissions reduced), security audit logs, and diagnostic AI chatbot support.

---

#### Output of the project and how to interpret it

##### 1. Backend REST API Responses (JSON format)
- `GET /api/devices`: Array of 100 device states containing ID, name, node, type, power kW, temperature °C, BER, OSNR dB, active channels, and power mode (`NORMAL`, `SLEEP`, `LOW_GAIN`).
- `GET /api/predictions`: Time-series forecast arrays for 5m, 1h, and 24h horizons.
- `GET /api/recommendations`: List of AI recommendations with policy validation flags (`validation_passed: true/false`, `rejection_reason`).
- `GET /api/fcaps/accounting`: Real-time energy telemetry metrics (Total active power in kW, energy saved in kWh, carbon offset in kg CO₂).

##### 2. Frontend Dashboard Interpretation
- **Device Grid & Node Map**: Green indicators denote normal operation; yellow/red indicate elevated BER or thermal warnings.
- **Traffic vs Power Graph**: Displays traffic diurnal curves alongside total network power draw.
- **Recommendation Panel**: Displays executable AI optimization proposals with policy validation checkmarks.

---

#### Error situations and how to solve them

| Error Scenario | Root Cause | Solution / Fix |
| :--- | :--- | :--- |
| `Address already in use` (Port 8000/3000) | Another process is already running on port 8000 or 3000. | Kill the process using port 8000/3000 (`npx kill-port 8000 3000` or change port via `--port 8001`). |
| `ModuleNotFoundError: No module named 'fastapi'` | Python virtual environment not activated or dependencies not installed. | Activate virtual environment (`source venv/bin/activate` or `.\venv\Scripts\Activate.ps1`) and run `pip install -r backend/requirements.txt`. |
| `Action REJECTED by Optical Policy Engine` | An AI energy recommendation violates carrier SLA limits (e.g., OSNR < 14.5 dB or BER > $1.0 \times 10^{-4}$). | This is expected behavior. The policy engine blocks risky actions to preserve network reliability (99.99% uptime SLA). |
| `Fetch Error: Failed to fetch API` | Frontend cannot connect to backend at `http://127.0.0.1:8000`. | Ensure backend server is running (`python -m uvicorn app.main:app --port 8000`). |

---

### Complete CLI Reference

```bash
# ---------------------------------------------------------
# 1. Virtual Environment & Dependencies Setup
# ---------------------------------------------------------
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate virtual environment (Linux/macOS)
source venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# ---------------------------------------------------------
# 2. Running Backend & Frontend Services
# ---------------------------------------------------------
# Launch backend server on http://127.0.0.1:8000 with hot reload
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Launch frontend dashboard on http://localhost:3000
cd frontend
npm run dev

# ---------------------------------------------------------
# 3. Testing & Code Quality Verification
# ---------------------------------------------------------
# Run backend automated test suite
python backend/test_backend.py

# Run frontend Next.js linter
cd frontend && npm run lint
```

---

## How to contribute

We welcome contributions to improve the AI traffic prediction models, expand Nokia 1830 PSS device simulations, or enhance the dashboard UI!

### Explain how can someone modify your code and how can they test it

1. **Fork & Clone**: Fork the repository on GitHub and clone your fork locally.
2. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/optical-optimization-enhancement
   ```
3. **Modifying Backend Logic**:
   - `backend/app/simulator.py`: Add or update optical device types, modulation schemes, or node topologies.
   - `backend/app/ml_engine.py`: Tune traffic forecasting algorithms or anomaly detection thresholds.
   - `backend/app/policy_engine.py`: Customize carrier SLA rules (BER, OSNR, latency).
   - `backend/app/llm_engine.py`: Modify AI reasoning prompts and chatbot response generators.
4. **Modifying Frontend Logic**:
   - `frontend/src/app/page.tsx`: Modify dashboard layout, chart visualizations, or FCAPS views.

---

### Any linting rules

- **Python (Backend)**: Follow PEP 8 guidelines. Use 4-space indentation, clear type hints (`typing`), and docstrings for functions.
- **TypeScript/React (Frontend)**: Follow ESLint and Next.js standard conventions. Keep components modular and typed (`interface` / `type`).

---

### How to run tests

Always verify that all unit tests pass before committing code:

```bash
# Run backend unit & integration tests
python backend/test_backend.py
```

Expected output upon success:
```text
Testing 100 Optical Devices Telemetry Simulator...
  ✓ Telemetry simulator tick passed
Testing ML Traffic Prediction Engine...
  ✓ Traffic predictions (5m, 1h, 24h) passed
Testing Anomaly Detection Engine...
  ✓ Anomaly detection passed (0 anomalies flagged)
Testing LLM Recommendation Engine...
  ✓ LLM reasoning engine generated power recommendations
Testing Policy Validation Engine...
  ✓ Policy check on DEV-001: Passed=True, Checks count=5
Testing Telecom Chatbot Query...
  ✓ AI Chatbot query processing passed
Testing FCAPS Manager...
  ✓ FCAPS manager passed (Active kW: 142.5 kW)

ALL BACKEND UNIT TESTS PASSED SUCCESSFULLY! ✅
```

---

## License

This project is licensed under the BSD-3-Clause license. For the complete license text please check the [LICENSE](LICENSE) file.

SPDX-License-Identifier: BSD-3-Clause
