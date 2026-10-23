import {
  Device, Recommendation, TrafficPrediction, AnomalyItem, FCAPSAlarm,
  FCAPSEnergyAccounting, FCAPSSecurityLog, DigitalTwinStateSummary,
  DigitalTwinDevice, DigitalTwinTopologyGraph, WhatIfSimulationRequest,
  WhatIfSimulationResponse, SimulationHistoryItem, DemoScenarioInfo,
  QuantumValidationResponse
  , TelemetrySourceStatus
} from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
      },
      ...options,
    });
    if (!res.ok) {
      console.warn(`API request to ${endpoint} failed: ${res.statusText}`);
      return null;
    }
    return await res.json();
  } catch (err) {
    console.warn(`Network error connecting to ${endpoint}:`, err);
    return null;
  }
}

export async function getDevices(): Promise<Device[]> {
  const data = await fetchJson<Device[]>('/devices');
  return data || [];
}

export async function getTelemetrySource(): Promise<TelemetrySourceStatus | null> {
  return await fetchJson<TelemetrySourceStatus>('/telemetry/source');
}

export async function setTelemetrySource(source: 'simulator' | 'nokia'): Promise<TelemetrySourceStatus | null> {
  return await fetchJson<TelemetrySourceStatus>(`/telemetry/source?source=${source}`, { method: 'POST' });
}

export async function refreshTelemetry(): Promise<TelemetrySourceStatus | null> {
  return await fetchJson<TelemetrySourceStatus>('/telemetry/refresh', { method: 'POST' });
}

export async function getPredictions(horizon: string = '5m'): Promise<TrafficPrediction | null> {
  return await fetchJson<TrafficPrediction>(`/predictions?horizon=${horizon}`);
}

export async function getAnomalies(): Promise<AnomalyItem[]> {
  const data = await fetchJson<AnomalyItem[]>('/anomalies');
  return data || [];
}

export async function getRecommendations(): Promise<Recommendation[]> {
  const data = await fetchJson<Recommendation[]>('/recommendations');
  return data || [];
}

export async function executeAction(recommendation_id: string): Promise<{ status: string; message: string } | null> {
  return await fetchJson('/actions/execute', {
    method: 'POST',
    body: JSON.stringify({ recommendation_id }),
  });
}

export async function injectFault(device_id: string, fault_type: string): Promise<any> {
  return await fetchJson(`/faults/inject?device_id=${device_id}&fault_type=${fault_type}`, {
    method: 'POST',
  });
}

export async function clearFault(device_id: string): Promise<any> {
  return await fetchJson(`/faults/clear?device_id=${device_id}`, {
    method: 'POST',
  });
}

export async function getFCAPSAlarms(): Promise<FCAPSAlarm[]> {
  const data = await fetchJson<FCAPSAlarm[]>('/fcaps/alarms');
  return data || [];
}

export async function acknowledgeAlarm(alarm_id: string): Promise<any> {
  return await fetchJson(`/fcaps/alarms/ack?alarm_id=${alarm_id}`, {
    method: 'POST',
  });
}

export async function getFCAPSEnergyAccounting(): Promise<FCAPSEnergyAccounting | null> {
  return await fetchJson<FCAPSEnergyAccounting>('/fcaps/accounting');
}

export async function getFCAPSSecurityLogs(): Promise<FCAPSSecurityLog[]> {
  const data = await fetchJson<FCAPSSecurityLog[]>('/fcaps/security');
  return data || [];
}

export async function sendChatQuery(prompt: string): Promise<string> {
  const res = await fetchJson<{ response: string }>('/chatbot', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
  return res?.response || "Unable to reach AI Optical Assistant backend.";
}

export async function getQuantumValidation(): Promise<QuantumValidationResponse | null> {
  return await fetchJson<QuantumValidationResponse>('/quantum/validate');
}

// ==================== DIGITAL TWIN API FUNCTIONS ====================

export async function getDigitalTwinState(): Promise<DigitalTwinStateSummary | null> {
  return await fetchJson<DigitalTwinStateSummary>('/digital-twin/state');
}

export async function getDigitalTwinDevices(): Promise<DigitalTwinDevice[]> {
  const data = await fetchJson<DigitalTwinDevice[]>('/digital-twin/devices');
  return data || [];
}

export async function getDigitalTwinDevice(device_id: string): Promise<DigitalTwinDevice | null> {
  return await fetchJson<DigitalTwinDevice>(`/digital-twin/devices/${device_id}`);
}

export async function getDigitalTwinTopology(): Promise<DigitalTwinTopologyGraph | null> {
  return await fetchJson<DigitalTwinTopologyGraph>('/digital-twin/topology');
}

export async function simulateWhatIf(req: WhatIfSimulationRequest): Promise<WhatIfSimulationResponse | null> {
  return await fetchJson<WhatIfSimulationResponse>('/digital-twin/simulate', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function getSimulationHistory(): Promise<SimulationHistoryItem[]> {
  const data = await fetchJson<SimulationHistoryItem[]>('/digital-twin/simulations');
  return data || [];
}

export async function executeDigitalTwinAction(req: WhatIfSimulationRequest): Promise<any> {
  return await fetchJson('/digital-twin/execute', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function getDemoScenarios(): Promise<DemoScenarioInfo[]> {
  const data = await fetchJson<DemoScenarioInfo[]>('/digital-twin/demo/scenarios');
  return data || [];
}

export async function runDemoScenario(scenario_id: string): Promise<WhatIfSimulationResponse | null> {
  return await fetchJson<WhatIfSimulationResponse>(`/digital-twin/demo/run?scenario_id=${scenario_id}`, {
    method: 'POST',
  });
}
