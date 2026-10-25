export type DeviceType = "Transponder-800G" | "Transponder" | "SMF6" | "EDFA Amplifier" | "ROADM WSS" | "Filter Card" | "Network Element" | "Unknown";
export type PowerMode = "Normal" | "Eco" | "Sleep" | "Low Gain" | "Unknown";
export type HealthState = "Normal" | "Warning" | "Critical" | "Unknown";
export type ActionType = "Sleep idle transponder" | "Wake transponder" | "Reduce amplifier gain" | "Disable idle wavelength" | "Re-route traffic" | "Restore device" | string;

export interface TelemetrySourceStatus {
  source: 'simulator' | 'nokia';
  device_count: number;
  refresh_status?: string;
  last_refresh_error?: string | null;
  data_origin?: string;
  nokia_execution_enabled?: boolean;
  csv_ingestion_status?: CsvIngestionStatus | null;
}

export interface CsvIngestionDeviceStatus {
  filename: string;
  device_id: string;
  device_name: string;
  accepted_rows: number;
  rejected_rows: number;
  skipped_rows: number;
  latest_timestamp: string;
  assumed_timezone: string;
  rejected_reasons: string[];
  power_saving_status?: string;
  power_saving_reason?: string;
  observation_duration_seconds?: number;
  telemetry_age_seconds?: number;
  telemetry_stale?: boolean;
  metric_mapping: Record<string, CsvMetricMapping>;
}

export interface CsvMetricMapping {
  original_header: string;
  internal_field: string;
  display_label: string;
  unit: string;
  data_type: string;
  validation_rules: string;
  required: boolean;
  chartable: boolean;
  alertable: boolean;
  power_calc: boolean;
}

export interface CsvTelemetryRecord {
  timestamp: string;
  timestamp_utc: string;
  timestamp_epoch: number;
  device_id: string;
  device_name: string;
  node_location: string;
  device_type: string;
  power_mode: string;
  original_metrics: Record<string, string>;
  metrics: Record<string, number>;
}

export interface CsvPreviewResponse extends CsvIngestionDeviceStatus {
  latest_metrics: Record<string, number>;
}

export interface CsvIngestionStatus {
  ingestion_status: string;
  device_count: number;
  devices: Record<string, CsvIngestionDeviceStatus>;
  last_ingested_at: string | null;
  record_limit: number;
  size_limit_bytes: number;
}

export interface Telemetry {
  tx_power_dbm: number;
  rx_power_dbm: number;
  laser_bias_ma: number;
  laser_temp_c: number;
  dsp_temp_c: number;
  module_temp_c: number;
  ber: number | null;
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
  fec_ubc?: number | null;
  q_margin_min_db?: number | null;
  q_margin_max_db?: number | null;
  q_margin_avg_db?: number | null;
  rx_lane_power_1_dbm?: number | null;
  rx_lane_power_2_dbm?: number | null;
  rx_lane_power_3_dbm?: number | null;
  rx_lane_power_4_dbm?: number | null;
  tx_lane_power_1_dbm?: number | null;
  tx_lane_power_2_dbm?: number | null;
  tx_lane_power_3_dbm?: number | null;
  tx_lane_power_4_dbm?: number | null;
  opr_min_dbm?: number | null;
  opr_max_dbm?: number | null;
  opr_avg_dbm?: number | null;
  expected_network_output_power_dbm?: number | null;
  measured_network_output_power_dbm?: number | null;
  laser_case_temp_c?: number | null;
  admin_state?: string | null;
  state_qualifier?: string | null;
  status_led?: string | null;
  oper_capability?: string | null;
  module_type?: string | null;
  max_port_rate?: string | null;
  signal_rate?: string | null;
  odu_rate?: string | null;
  channel_tx_frequency_thz?: number | null;
  channel_rx_frequency_thz?: number | null;
  channel_tx_offset_ghz?: number | null;
  channel_rx_offset_ghz?: number | null;
  grid_step_size_ghz?: number | null;
  link_span_km?: number | null;
  otsig_id?: string | null;
  eth_octets_rx?: number | null;
  eth_octets_tx?: number | null;
  eth_errors_rx?: number | null;
  eth_errors_tx?: number | null;
  eth_packets_rx?: number | null;
  eth_packets_tx?: number | null;
  eth_error_rate_pct?: number | null;
  bandwidth_gbps?: number | null;
  confirmed_utilization_pct?: number | null;
  opt_min_dbm?: number | null;
  opt_max_dbm?: number | null;
  opt_avg_dbm?: number | null;
  opr_high_dbm?: number | null;
  opr_low_dbm?: number | null;
  opt_high_dbm?: number | null;
  opt_low_dbm?: number | null;
  cv_pcs?: number | null;
  es_pcs?: number | null;
  sefs_pcs?: number | null;
  ses_pcs?: number | null;
  esnr_db?: number | null;
  esnr_min_db?: number | null;
  esnr_max_db?: number | null;
  esnr_avg_db?: number | null;
  connection_state?: string | null;
  connection_type?: string | null;
  connection_rate?: string | null;
  endpoint_source?: string | null;
  endpoint_target?: string | null;
  ains_state?: string | null;
  ains_timer_sec?: number | null;
  fan_status?: string | null;
  device_power_w?: number | null;
  card_power_w?: number | null;
  port_utilization_pct?: number | null;
  module_health?: string | null;
  ambient_temp_c?: number | null;
  humidity_pct?: number | null;
}

export interface Device {
  id: string;
  name: string;
  type: DeviceType;
  node_location: string;
  target_node: string;
  wavelength_nm: number | null;
  power_mode: PowerMode;
  health: HealthState;
  telemetry: Telemetry;
  ne_name?: string | null;
  shelf_id?: string | null;
  slot_id?: string | null;
  port_id?: string | null;
  description?: string | null;
  equipment_name?: string | null;
  card_name?: string | null;
  interface_name?: string | null;
  chassis_id?: string | null;
  raw_record?: Record<string, unknown> | null;
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

// ==================== DIGITAL TWIN TYPES ====================

export type SyncStatus = "SYNCED" | "STALE" | "OFFLINE";
export type SimulationResult = "APPROVED" | "REJECTED" | "REQUIRES_OPERATOR_APPROVAL";

export interface DigitalTwinDevice {
  device_id: string;
  name: string;
  type: DeviceType;
  status: string;
  power_mode: PowerMode;
  node_location: string;
  target_node: string;
  traffic_utilization_pct: number;
  power_consumption_w: number;
  tx_power_dbm: number;
  rx_power_dbm: number;
  osnr_db: number;
  ber: number | null;
  pre_fec_ber: number;
  q_factor_db: number;
  temperature_c: number;
  capacity_gbps: number;
  protection_role: "primary" | "backup";
  last_updated: number;
  sync_status: SyncStatus;
  telemetry_freshness_sec: number;
}

export interface DigitalTwinGraphNode {
  id: string;
  name: string;
  node_type: string;
  location: string;
  status: string;
  active: boolean;
}

export interface DigitalTwinGraphEdge {
  source: string;
  target: string;
  capacity_gbps: number;
  available_bandwidth_gbps: number;
  distance_km: number;
  osnr_margin_db: number;
  utilization_pct: number;
  protection_relationship: string;
  active: boolean;
}

export interface DigitalTwinTopologyGraph {
  nodes: DigitalTwinGraphNode[];
  edges: DigitalTwinGraphEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface DigitalTwinStateSummary {
  total_devices: number;
  active_devices: number;
  sleeping_devices: number;
  devices_under_simulation: number;
  synchronized_devices: number;
  stale_devices: number;
  offline_devices: number;
  network_health: string;
  sync_status: SyncStatus;
  last_sync_timestamp: number;
  baseline_power_kw: number;
  current_power_kw: number;
  instantaneous_savings_w: number;
  estimated_daily_savings_kwh: number;
  estimated_monthly_savings_kwh: number;
  savings_percentage: number;
  co2_reduction_kg: number;
}

export interface PowerSavingsMetric {
  instantaneous_w: number;
  daily_kwh: number;
  monthly_kwh: number;
  percentage_reduction: number;
  co2_reduction_kg: number;
}

export interface WhatIfSimulationRequest {
  device_id: string;
  action_type: string;
  custom_power_w?: number;
}

export interface WhatIfSimulationResponse {
  simulation_id: string;
  timestamp: number;
  device_id: string;
  device_name: string;
  action_type: string;
  result: SimulationResult;
  reason: string;
  current_state: Record<string, any>;
  simulated_state: Record<string, any>;
  policy_checks: PolicyCheckItem[];
  power_savings: PowerSavingsMetric;
  traffic_redistribution: Record<string, any>;
  discarded: boolean;
}

export interface SimulationHistoryItem {
  id: string;
  timestamp: string;
  device_id: string;
  device_name: string;
  action_type: string;
  result: string;
  energy_saving_w: number;
  reason: string;
}

export interface DemoScenarioInfo {
  scenario_id: string;
  title: string;
  description: string;
  device_id: string;
  action_type: string;
  expected_result: SimulationResult;
}

export interface QuantumSelectedDevice {
  variable: string;
  device_id: string;
  device_type: string;
  action: string;
  traffic: number;
  power_saving_w: number;
}

export interface QuantumSolution {
  raw_bitstring: string;
  variable_bitstring: string;
  device_bitstring: string;
  variable_values?: Record<string, string>;
  selected_devices: QuantumSelectedDevice[];
  num_selected: number;
  total_power_saving_w: number;
  feasible: boolean;
  shots: number;
  probability: number;
}

export interface LocalQaoaAnalysis {
  status: 'success' | 'no_candidates' | 'no_feasible_solution';
  method: 'local_qaoa_statevector';
  candidate_count: number;
  candidates: QuantumSelectedDevice[];
  selected_devices: QuantumSelectedDevice[];
  num_selected: number;
  total_power_saving_w: number;
  feasible: boolean;
  highest_probability?: number;
  statevector_qubits?: number;
  beta: number;
  gamma: number;
  message: string;
  source: 'simulator' | 'nokia';
  data_origin: string;
  minimum_observation_seconds: number;
  observation_durations_seconds: number[];
  qpu_used: false;
  execution_performed: false;
}

export interface QuantumRecommendation extends QuantumSelectedDevice {
  estimated_power_saving_w: number;
  validation_status: string;
  policy_checks: PolicyCheckItem[];
}

export interface QuantumOptimizationRun {
  run_id?: string;
  job_id?: string;
  execution_method: 'ibm_qpu' | 'local_simulator';
  backend?: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'rejected' | 'no_candidates' | 'error';
  job_status?: string;
  source?: 'simulator' | 'nokia';
  data_origin?: string;
  submitted_at?: string;
  completed_at?: string;
  shots?: number;
  requested_shots?: number;
  eligible_candidate_count?: number;
  selected_action_count?: number;
  qubo_variables?: number;
  qubo_variable_names?: string[];
  candidate_variable_names?: string[];
  measurement_bit_order?: string;
  qaoa_beta?: number;
  qaoa_gamma?: number;
  metadata_persisted?: boolean;
  metadata_persistence_error?: string;
  max_actions?: number;
  num_qubits?: number;
  circuit_depth?: number;
  qpu_submitted?: boolean;
  metadata_available?: boolean;
  result_retrieved?: boolean;
  measurement_counts?: Record<string, number>;
  qpu_solution?: QuantumSolution | null;
  digital_twin?: QuantumDigitalTwinValidation | null;
  recommendations?: QuantumRecommendation[];
  rejections?: Array<{ device_id?: string; reason: string; result?: string }>;
  total_estimated_power_saving_w?: number;
  validation_status?: string;
  current_source?: string;
  message: string;
  error_type?: string;
  error?: string;
  execution_performed: false;
}

export interface QuantumQpuResult {
  job_id: string;
  backend: string;
  shots: number;
  solution: QuantumSolution | null;
}

export interface QuantumValidationAction {
  device_id: string;
  action_type: string;
}

export interface QuantumValidationActionResult {
  device_id: string;
  action: string;
  result: string;
  saving_w: number;
  traffic_pct?: number;
  osnr_db?: number;
  protection_utilization_pct?: number;
  protection_available?: boolean;
  policy_checks?: PolicyCheckItem[];
  reason: string;
}

export interface QuantumAffectedLink {
  source: string;
  target: string;
  protection_utilization_pct: number;
}

export interface QuantumDigitalTwinValidation {
  status: 'APPROVED' | 'REJECTED';
  all_actions_approved: boolean;
  action_count: number;
  approved_count: number;
  total_power_saving_w: number;
  total_power_saving_kw: number;
  actions: QuantumValidationActionResult[];
  affected_links: QuantumAffectedLink[];
  state_changed: boolean;
  temporary_state_discarded: boolean;
  reason: string;
}

export interface QuantumValidationSuccessResponse {
  status: 'APPROVED' | 'REJECTED';
  message: string;
  qpu: QuantumQpuResult;
  digital_twin: QuantumDigitalTwinValidation | null;
  actions: QuantumValidationAction[];
  candidate_snapshot: string | null;
  used_current_telemetry: boolean;
  execution_performed: boolean;
}

export interface QuantumValidationPendingResponse {
  status: 'pending';
  job_id: string;
  qpu_status: string;
  message: string;
}

export interface QuantumValidationErrorResponse {
  status: 'error';
  error_type: string;
  error: string;
  job_id: string;
  snapshot: string;
  message: string;
}

export type QuantumValidationResponse =
  | QuantumValidationPendingResponse
  | QuantumValidationSuccessResponse
  | QuantumValidationErrorResponse;
