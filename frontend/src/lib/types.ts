export type DeviceType = "Transponder-800G" | "EDFA Amplifier" | "ROADM WSS" | "Filter Card";
export type PowerMode = "Normal" | "Eco" | "Sleep" | "Low Gain";
export type HealthState = "Normal" | "Warning" | "Critical";

export interface Telemetry {
  tx_power_dbm: number;
  rx_power_dbm: number;
  laser_bias_ma: number;
  laser_temp_c: number;
  dsp_temp_c: number;
  module_temp_c: number;
  ber: number;
  pre_fec_ber: number;
  post_fec_ber: number;
  q_factor_db: number;
  osnr_db: number;
  chromatic_dispersion: number;
  voltage_v: number;
  current_a: number;
  fan_rpm: number;
  traffic_utilization_pct: number;
  power_consumption_w: number;
  timestamp: number;
}

export interface Device {
  id: string;
  name: string;
  type: DeviceType;
  node_location: string;
  target_node: string;
  wavelength_nm: number;
  power_mode: PowerMode;
  health: HealthState;
  telemetry: Telemetry;
}

export interface PolicyCheckItem {
  name: string;
  required: string;
  measured: string;
  passed: boolean;
}

export interface Recommendation {
  id: string;
  device_id: string;
  device_name: string;
  action_type: string;
  reasoning: string;
  estimated_power_savings_w: number;
  validation_passed: boolean;
  policy_checks: PolicyCheckItem[];
  rejection_reason?: string;
  executed: boolean;
  timestamp: number;
}

export interface TrafficPrediction {
  horizon: string;
  timestamps: string[];
  predicted_traffic_gbps: number[];
  upper_bound_gbps: number[];
  lower_bound_gbps: number[];
  confidence_score: number;
}

export interface AnomalyItem {
  id: string;
  device_id: string;
  device_name: string;
  anomaly_type: string;
  severity: "Warning" | "Critical";
  score: number;
  details: string;
  timestamp: string;
}

export interface FCAPSAlarm {
  id: string;
  device_id: string;
  device_name: string;
  severity: string;
  message: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface FCAPSEnergyAccounting {
  total_power_kw: number;
  baseline_power_kw: number;
  energy_saved_kwh: number;
  power_savings_pct: number;
  carbon_reduced_kg: number;
  cost_savings_usd: number;
  power_history: { time: string; Baseline_kW: number; AI_Optimized_kW: number }[];
}

export interface FCAPSSecurityLog {
  id: string;
  timestamp: string;
  user: string;
  event: string;
  ip_address: string;
  status: string;
}
