from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
import time

class DeviceType(str, Enum):
    TRANSPONDER_800G = "Transponder-800G"
    EDFA = "EDFA Amplifier"
    ROADM = "ROADM WSS"
    FILTER_CARD = "Filter Card"
    NETWORK_ELEMENT = "Network Element"

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
    # Nokia 1830 PSS / WaveSuite PM fields. Optional because availability is
    # equipment and software-release dependent.
    fec_ubc: Optional[int] = None
    q_margin_min_db: Optional[float] = None
    q_margin_max_db: Optional[float] = None
    q_margin_avg_db: Optional[float] = None
    rx_lane_power_1_dbm: Optional[float] = None
    rx_lane_power_2_dbm: Optional[float] = None
    rx_lane_power_3_dbm: Optional[float] = None
    rx_lane_power_4_dbm: Optional[float] = None
    tx_lane_power_1_dbm: Optional[float] = None
    tx_lane_power_2_dbm: Optional[float] = None
    tx_lane_power_3_dbm: Optional[float] = None
    tx_lane_power_4_dbm: Optional[float] = None
    opr_min_dbm: Optional[float] = None
    opr_max_dbm: Optional[float] = None
    opr_avg_dbm: Optional[float] = None
    expected_network_output_power_dbm: Optional[float] = None
    measured_network_output_power_dbm: Optional[float] = None
    laser_case_temp_c: Optional[float] = None
    admin_state: Optional[str] = None
    state_qualifier: Optional[str] = None
    status_led: Optional[str] = None
    oper_capability: Optional[str] = None
    module_type: Optional[str] = None
    max_port_rate: Optional[str] = None
    signal_rate: Optional[str] = None
    odu_rate: Optional[str] = None
    channel_tx_frequency_thz: Optional[float] = None
    channel_rx_frequency_thz: Optional[float] = None
    channel_tx_offset_ghz: Optional[float] = None
    channel_rx_offset_ghz: Optional[float] = None
    grid_step_size_ghz: Optional[float] = None
    link_span_km: Optional[float] = None
    otsig_id: Optional[str] = None
    eth_octets_rx: Optional[int] = None
    eth_octets_tx: Optional[int] = None
    eth_errors_rx: Optional[int] = None
    eth_errors_tx: Optional[int] = None
    eth_packets_rx: Optional[int] = None
    eth_packets_tx: Optional[int] = None
    eth_error_rate_pct: Optional[float] = None
    bandwidth_gbps: Optional[float] = None
    confirmed_utilization_pct: Optional[float] = None
    opt_min_dbm: Optional[float] = None
    opt_max_dbm: Optional[float] = None
    opt_avg_dbm: Optional[float] = None
    opr_high_dbm: Optional[float] = None
    opr_low_dbm: Optional[float] = None
    opt_high_dbm: Optional[float] = None
    opt_low_dbm: Optional[float] = None
    cv_pcs: Optional[int] = None
    es_pcs: Optional[int] = None
    sefs_pcs: Optional[int] = None
    ses_pcs: Optional[int] = None
    esnr_db: Optional[float] = None
    esnr_min_db: Optional[float] = None
    esnr_max_db: Optional[float] = None
    esnr_avg_db: Optional[float] = None
    connection_state: Optional[str] = None
    connection_type: Optional[str] = None
    connection_rate: Optional[str] = None
    endpoint_source: Optional[str] = None
    endpoint_target: Optional[str] = None
    ains_state: Optional[str] = None
    ains_timer_sec: Optional[int] = None
    fan_status: Optional[str] = None
    device_power_w: Optional[float] = None
    card_power_w: Optional[float] = None
    port_utilization_pct: Optional[float] = None
    module_health: Optional[str] = None
    ambient_temp_c: Optional[float] = None
    humidity_pct: Optional[float] = None

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
    ne_name: Optional[str] = None
    shelf_id: Optional[str] = None
    slot_id: Optional[str] = None
    port_id: Optional[str] = None
    description: Optional[str] = None
    equipment_name: Optional[str] = None
    card_name: Optional[str] = None
    interface_name: Optional[str] = None
    chassis_id: Optional[str] = None
    raw_record: Optional[Dict[str, Any]] = None

class NokiaThresholdResult(BaseModel):
    device_id: str
    device_name: str
    ne_name: Optional[str] = None
    shelf_id: Optional[str] = None
    slot_id: Optional[str] = None
    port_id: Optional[str] = None
    metric: str
    measured_value: Any
    unit: str
    severity: str
    explanation: str
    threshold_used: Optional[str] = None
    baseline_used: Optional[str] = None
    quality: str
    complete: bool
    interval: str
    timestamp: float

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

class NodeSpatialModel(BaseModel):
    name: str
    x: float
    y: float
    z: float
    radius: float
    azimuth_deg: float
    orientation_deg: float

class MultiAngularLinkModel(BaseModel):
    src: str
    dst: str
    distance_km: float
    bearing_deg: float
    active: bool

class TopologyStateModel(BaseModel):
    pattern: str
    global_rotation_deg: float
    total_nodes: int
    total_links: int
    active_links: int
    nodes: Dict[str, NodeSpatialModel]
    links: List[MultiAngularLinkModel]

class RotateTopologyRequest(BaseModel):
    delta_deg: float = Field(..., description="Degrees to rotate network (0-360)")
    node_name: Optional[str] = Field(None, description="Optional single node to rotate orientation for")

class SetTopologyPatternRequest(BaseModel):
    pattern: str = Field(..., description="Topology pattern: ring, full_mesh, partial_mesh, star, tree, directional_sector, rotational_sweep, hybrid")

# ==================== DIGITAL TWIN MODELS ====================

class SyncStatus(str, Enum):
    SYNCED = "SYNCED"
    STALE = "STALE"
    OFFLINE = "OFFLINE"

class SimulationResult(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUIRES_OPERATOR_APPROVAL = "REQUIRES_OPERATOR_APPROVAL"

class DigitalTwinDevice(BaseModel):
    device_id: str
    name: str
    type: DeviceType
    status: str  # ACTIVE, SLEEP, ECO, LOW_GAIN, WARNING, CRITICAL
    power_mode: PowerMode
    node_location: str
    target_node: str
    traffic_utilization_pct: float
    power_consumption_w: float
    tx_power_dbm: float
    rx_power_dbm: float
    osnr_db: float
    ber: float
    pre_fec_ber: float
    q_factor_db: float
    temperature_c: float
    capacity_gbps: float
    protection_role: str  # primary, backup
    last_updated: float
    sync_status: SyncStatus
    telemetry_freshness_sec: float

class DigitalTwinGraphNode(BaseModel):
    id: str
    name: str
    node_type: str  # NetworkNode, Transponder, Amplifier, ROADM, FilterCard
    location: str
    status: str
    active: bool

class DigitalTwinGraphEdge(BaseModel):
    source: str
    target: str
    capacity_gbps: float
    available_bandwidth_gbps: float
    distance_km: float
    osnr_margin_db: float
    utilization_pct: float
    protection_relationship: str
    active: bool

class DigitalTwinTopologyGraph(BaseModel):
    nodes: List[DigitalTwinGraphNode]
    edges: List[DigitalTwinGraphEdge]
    total_nodes: int
    total_edges: int

class DigitalTwinStateSummary(BaseModel):
    total_devices: int
    active_devices: int
    sleeping_devices: int
    devices_under_simulation: int
    synchronized_devices: int
    stale_devices: int
    offline_devices: int
    network_health: str
    sync_status: SyncStatus
    last_sync_timestamp: float
    baseline_power_kw: float
    current_power_kw: float
    instantaneous_savings_w: float
    estimated_daily_savings_kwh: float
    estimated_monthly_savings_kwh: float
    savings_percentage: float
    co2_reduction_kg: float

class PowerSavingsMetric(BaseModel):
    instantaneous_w: float
    daily_kwh: float
    monthly_kwh: float
    percentage_reduction: float
    co2_reduction_kg: float

class WhatIfSimulationRequest(BaseModel):
    device_id: str
    action_type: ActionType
    custom_power_w: Optional[float] = None

class WhatIfSimulationResponse(BaseModel):
    simulation_id: str
    timestamp: float
    device_id: str
    device_name: str
    action_type: ActionType
    result: SimulationResult
    reason: str
    current_state: Dict[str, Any]
    simulated_state: Dict[str, Any]
    policy_checks: List[PolicyCheckItem]
    power_savings: PowerSavingsMetric
    traffic_redistribution: Dict[str, Any]
    discarded: bool = True

class SimulationHistoryItem(BaseModel):
    id: str
    timestamp: str
    device_id: str
    device_name: str
    action_type: str
    result: str
    energy_saving_w: float
    reason: str

class DemoScenarioInfo(BaseModel):
    scenario_id: str
    title: str
    description: str
    device_id: str
    action_type: ActionType
    expected_result: SimulationResult
