from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
import time

class DeviceType(str, Enum):
    TRANSPONDER_800G = "Transponder-800G"
    EDFA = "EDFA Amplifier"
    ROADM = "ROADM WSS"
    FILTER_CARD = "Filter Card"

class PowerMode(str, Enum):
    NORMAL = "Normal"
    ECO = "Eco"
    SLEEP = "Sleep"
    LOW_GAIN = "Low Gain"

class HealthState(str, Enum):
    NORMAL = "Normal"
    WARNING = "Warning"
    CRITICAL = "Critical"

class Telemetry(BaseModel):
    tx_power_dbm: float = Field(..., description="Tx Optical Power in dBm")
    rx_power_dbm: float = Field(..., description="Rx Optical Power in dBm")
    laser_bias_ma: float = Field(..., description="Laser Bias Current in mA")
    laser_temp_c: float = Field(..., description="Laser Temperature in °C")
    dsp_temp_c: float = Field(..., description="DSP Temperature in °C")
    module_temp_c: float = Field(..., description="Module Temperature in °C")
    ber: float = Field(..., description="Bit Error Rate")
    pre_fec_ber: float = Field(..., description="Pre-FEC BER")
    post_fec_ber: float = Field(..., description="Post-FEC BER")
    q_factor_db: float = Field(..., description="Q-factor in dB")
    osnr_db: float = Field(..., description="OSNR in dB")
    chromatic_dispersion: float = Field(..., description="Chromatic Dispersion in ps/nm")
    voltage_v: float = Field(..., description="Voltage in V")
    current_a: float = Field(..., description="Current in A")
    fan_rpm: int = Field(..., description="Fan Speed in RPM")
    traffic_utilization_pct: float = Field(..., description="Traffic load utilization percentage")
    power_consumption_w: float = Field(..., description="Current power draw in Watts")
    timestamp: float = Field(default_factory=time.time)

class Device(BaseModel):
    id: str
    name: str
    type: DeviceType
    node_location: str
    target_node: str
    wavelength_nm: float
    power_mode: PowerMode
    health: HealthState
    telemetry: Telemetry

class ActionType(str, Enum):
    SLEEP_TRANSPONDER = "Sleep idle transponder"
    WAKE_TRANSPONDER = "Wake transponder"
    REDUCE_GAIN = "Reduce amplifier gain"
    DISABLE_WAVELENGTH = "Disable idle wavelength"
    REROUTE_TRAFFIC = "Re-route traffic"
    RESTORE_DEVICE = "Restore device"

class PolicyCheckItem(BaseModel):
    name: str
    required: str
    measured: str
    passed: bool

class Recommendation(BaseModel):
    id: str
    device_id: str
    device_name: str
    action_type: ActionType
    reasoning: str
    estimated_power_savings_w: float
    validation_passed: bool
    policy_checks: List[PolicyCheckItem]
    rejection_reason: Optional[str] = None
    executed: bool = False
    timestamp: float = Field(default_factory=time.time)

class TrafficPrediction(BaseModel):
    horizon: str  # "5m", "1h", "24h"
    timestamps: List[str]
    predicted_traffic_gbps: List[float]
    upper_bound_gbps: List[float]
    lower_bound_gbps: List[float]
    confidence_score: float

class AnomalyItem(BaseModel):
    id: str
    device_id: str
    device_name: str
    anomaly_type: str  # "High Temperature", "High BER", "Low OSNR", "Power Spike"
    severity: str      # "Warning", "Critical"
    score: float
    details: str
    timestamp: str

class FCAPSAlarm(BaseModel):
    id: str
    device_id: str
    device_name: str
    severity: str  # Critical, Major, Minor, Warning
    message: str
    timestamp: str
    acknowledged: bool = False

class FCAPSEnergyAccounting(BaseModel):
    total_power_kw: float
    baseline_power_kw: float
    energy_saved_kwh: float
    power_savings_pct: float
    carbon_reduced_kg: float
    cost_savings_usd: float
    power_history: List[Dict[str, Any]]

class FCAPSSecurityLog(BaseModel):
    id: str
    timestamp: str
    user: str
    event: str
    ip_address: str
    status: str  # SUCCESS, DENIED, WARNING

class ChatMessage(BaseModel):
    sender: str  # "user" or "ai"
    text: str
    timestamp: str

class ChatRequest(BaseModel):
    prompt: str

class ChatResponse(BaseModel):
    response: str

class ActionExecutionRequest(BaseModel):
    recommendation_id: str

