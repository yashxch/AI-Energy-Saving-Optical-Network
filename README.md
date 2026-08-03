# AI-Based Power Saving in Optical Networks

An intelligent, autonomous energy optimization and network management platform modeled after Nokia 1830 PSS optical transport network architectures.

## 🌟 Key Features

- **100 Optical Devices Telemetry Simulator**: Real-time simulation of 800G Muxponders, Variable Gain EDFA Amplifiers, ROADMs, and Optical Filter Cards across 8 major US network nodes (NYC, BOS, CHI, WDC, ATL, DAL, SFO, LAX).
- **ML Traffic Prediction Engine**: Time-series forecasting for network traffic over 5m, 1h, and 24h horizons.
- **Anomaly Detection**: Real-time detection of high BER, thermal spikes, OSNR drops, and power anomalies.
- **LLM Energy Recommendation Engine**: Generates action-oriented recommendations for placing transponders in deep sleep, adjusting amplifier gains, or rerouting traffic.
- **Optical Policy Engine**: Validates actions against strict carrier SLAs, QoS thresholds (99.99%), pre-FEC BER limits ($\le 1.0 \times 10^{-4}$), OSNR margins ($\ge 14.5 \text{ dB}$), and 1+1 OSC protection paths.
- **FCAPS Telecommunications Management**: Full Fault, Configuration, Accounting, Performance, and Security logging with live energy/carbon savings calculation.
- **Telecom AI Chatbot**: Natural language query interface powered by optical network domain context.
- **Modern Interactive Dashboard**: Next.js 14 frontend built with TailwindCSS and Recharts for live monitoring and active control.

---

## 🏗️ Architecture

```
optical-network-power-saver/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI Application & API Endpoints
│   │   ├── simulator.py       # 100 Optical Device Simulation & Diurnal Waves
│   │   ├── ml_engine.py       # ML Traffic Forecasting & Anomaly Detection
│   │   ├── llm_engine.py      # LLM Reasoning & Telecom Chatbot Logic
│   │   ├── policy_engine.py   # SLA/QoS Policy Validation Engine
│   │   ├── fcaps.py           # Telecom FCAPS Management System
│   │   └── models.py          # Pydantic Schemas & Data Structures
│   ├── test_backend.py        # Backend Unit & Integration Tests
│   └── requirements.txt       # Python Dependencies
├── frontend/
│   ├── src/                   # Next.js 14 Dashboard UI Components
│   └── package.json           # Frontend Dependencies
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt
python test_backend.py         # Run test suite
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

FastAPI server runs at: `http://127.0.0.1:8000`  
Swagger API Docs available at: `http://127.0.0.1:8000/docs`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Next.js Dashboard runs at: `http://localhost:3000`

---

## 🧪 License

MIT
