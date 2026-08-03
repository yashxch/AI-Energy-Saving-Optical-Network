import asyncio
import time
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

from .models import (
    Device, Recommendation, TrafficPrediction, AnomalyItem,
    FCAPSAlarm, FCAPSEnergyAccounting, FCAPSSecurityLog,
    ChatRequest, ChatResponse, ActionExecutionRequest, PowerMode
)
from .simulator import simulator
from .ml_engine import ml_engine
from .llm_engine import llm_engine
from .policy_engine import policy_engine
from .fcaps import fcaps_manager

app = FastAPI(
    title="AI-Based Power Saving in Optical Networks API",
    description="Nokia 1830 PSS style optical transport network simulation and AI energy optimization engine.",
    version="1.0.0"
)

# Enable CORS for local Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background tick loop task
async def background_simulation_loop():
    while True:
        try:
            simulator.tick()
        except Exception as e:
            print(f"Simulation tick error: {e}")
        await asyncio.sleep(1.0)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_simulation_loop())

@app.get("/")
def read_root():
    return {
        "status": "online",
        "system": "AI-Based Power Saving in Optical Networks Simulator",
        "device_count": len(simulator.devices),
        "version": "1.0.0"
    }

@app.get("/api/devices", response_model=List[Device])
def get_devices():
    return list(simulator.devices.values())

@app.get("/api/devices/{device_id}", response_model=Device)
def get_device(device_id: str):
    dev = simulator.devices.get(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return dev

@app.get("/api/predictions", response_model=TrafficPrediction)
def get_traffic_prediction(horizon: str = "5m"):
    if horizon not in ["5m", "1h", "24h"]:
        raise HTTPException(status_code=400, detail="Invalid horizon. Choose '5m', '1h', or '24h'")
    return ml_engine.predict_traffic(horizon)

@app.get("/api/anomalies", response_model=List[AnomalyItem])
def get_anomalies():
    return ml_engine.detect_anomalies()

@app.get("/api/recommendations", response_model=List[Recommendation])
def get_recommendations():
    return llm_engine.get_recommendations()

@app.post("/api/actions/execute")
def execute_action(req: ActionExecutionRequest):
    recs = llm_engine.get_recommendations()
    target_rec = next((r for r in recs if r.id == req.recommendation_id), None)
    
    if not target_rec:
        # Fallback search or direct execution
        raise HTTPException(status_code=404, detail="Recommendation not found or expired")

    if not target_rec.validation_passed:
        fcaps_manager.log_security_event(
            user="ai_agent_policy",
            event=f"BLOCKED Execution on {target_rec.device_id}: {target_rec.rejection_reason}",
            ip="127.0.0.1",
            status="DENIED"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Action REJECTED by Optical Policy Engine: {target_rec.rejection_reason}"
        )

    # Apply mode change
    dev_id = target_rec.device_id
    if "Sleep" in target_rec.action_type.value:
        simulator.set_device_power_mode(dev_id, PowerMode.SLEEP)
    elif "Reduce" in target_rec.action_type.value:
        simulator.set_device_power_mode(dev_id, PowerMode.LOW_GAIN)
    elif "Wake" in target_rec.action_type.value or "Restore" in target_rec.action_type.value:
        simulator.set_device_power_mode(dev_id, PowerMode.NORMAL)

    fcaps_manager.log_security_event(
        user="operator_admin",
        event=f"EXECUTED Power Optimization {target_rec.action_type.value} on {target_rec.device_name} ({dev_id})",
        ip="127.0.0.1",
        status="SUCCESS"
    )

    return {
        "status": "success",
        "message": f"Successfully executed '{target_rec.action_type.value}' on {target_rec.device_name} ({dev_id}). Power reduction in effect.",
        "device_id": dev_id,
        "new_power_mode": simulator.devices[dev_id].power_mode.value
    }

@app.post("/api/faults/inject")
def inject_fault(device_id: str, fault_type: str):
    if device_id not in simulator.devices:
        raise HTTPException(status_code=404, detail="Device not found")
    simulator.inject_fault(device_id, fault_type)
    return {"status": "injected", "device_id": device_id, "fault_type": fault_type}

@app.post("/api/faults/clear")
def clear_fault(device_id: str):
    if device_id not in simulator.devices:
        raise HTTPException(status_code=404, detail="Device not found")
    simulator.clear_fault(device_id)
    return {"status": "cleared", "device_id": device_id}

@app.get("/api/fcaps/alarms", response_model=List[FCAPSAlarm])
def get_fcaps_alarms():
    return fcaps_manager.get_fault_alarms()

@app.post("/api/fcaps/alarms/ack")
def acknowledge_alarm(alarm_id: str):
    fcaps_manager.acknowledge_alarm(alarm_id)
    return {"status": "acknowledged", "alarm_id": alarm_id}

@app.get("/api/fcaps/accounting", response_model=FCAPSEnergyAccounting)
def get_energy_accounting():
    return fcaps_manager.get_energy_accounting()

@app.get("/api/fcaps/security", response_model=List[FCAPSSecurityLog])
def get_security_logs():
    return fcaps_manager.security_logs

@app.post("/api/chatbot")
def process_chatbot_query(req: ChatRequest):
    response_text = llm_engine.process_chat_query(req.prompt)
    return {"response": response_text}
