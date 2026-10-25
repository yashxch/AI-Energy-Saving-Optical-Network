'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Header } from '../components/Header';
import { NetworkTopology } from '../components/NetworkTopology';
import { PowerOptimization } from '../components/PowerOptimization';
import { PredictionCharts } from '../components/PredictionCharts';
import { TelemetryGrid } from '../components/TelemetryGrid';
import { FcapsDashboard } from '../components/FcapsDashboard';
import { OpticalChatbot } from '../components/OpticalChatbot';
import { DigitalTwinDashboard } from '../components/DigitalTwinDashboard';
import { QuantumOptimizationDashboard } from '../components/QuantumOptimizationDashboard';
import { NokiaCsvWorkflow } from '../components/NokiaCsvWorkflow';

import {
  Device,
  Recommendation,
  AnomalyItem,
  FCAPSAlarm,
  FCAPSEnergyAccounting,
  FCAPSSecurityLog,
  TelemetrySourceStatus,
} from '../lib/types';

import {
  getDevices,
  getRecommendations,
  getAnomalies,
  getFCAPSAlarms,
  getFCAPSEnergyAccounting,
  getFCAPSSecurityLogs,
  getTelemetrySource,
  setTelemetrySource,
  refreshTelemetry,
} from '../lib/api';

export default function Home() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [alarms, setAlarms] = useState<FCAPSAlarm[]>([]);
  const [accounting, setAccounting] = useState<FCAPSEnergyAccounting | null>(null);
  const [securityLogs, setSecurityLogs] = useState<FCAPSSecurityLog[]>([]);
  const [selectedNodeFilter, setSelectedNodeFilter] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'telemetry' | 'digital_twin' | 'quantum'>('telemetry');
  const [telemetrySource, setTelemetrySourceState] = useState<TelemetrySourceStatus | null>(null);

  const fetchAllData = useCallback(async () => {
    try {
      const sourceStatus = await getTelemetrySource();
      const historicalCsv = sourceStatus?.data_origin === 'project_csv';
      if (sourceStatus) setTelemetrySourceState(sourceStatus);
      if (historicalCsv) {
        setRecommendations([]);
        setAnomalies([]);
        setAlarms([]);
        setAccounting(null);
        setSecurityLogs([]);
      }
      const [devsRes, recsRes, anoRes, almRes, accRes, secRes] = await Promise.all([
        getDevices(),
        getRecommendations(),
        getAnomalies(),
        historicalCsv ? Promise.resolve([]) : getFCAPSAlarms(),
        historicalCsv ? Promise.resolve(null) : getFCAPSEnergyAccounting(),
        historicalCsv ? Promise.resolve([]) : getFCAPSSecurityLogs()
      ]);

      const hasTelemetry = devsRes.length > 0;
      setDevices(devsRes);
      setRecommendations(hasTelemetry ? recsRes : []);
      setAnomalies(hasTelemetry ? anoRes : []);
      setAlarms(hasTelemetry ? almRes : []);
      setAccounting(hasTelemetry ? accRes : null);
      setSecurityLogs(hasTelemetry ? secRes : []);
      if (sourceStatus) setTelemetrySourceState(sourceStatus);
    } catch (err) {
      console.warn("Telemetry fetch error:", err);
    }
  }, []);

  const refreshAllData = useCallback(async () => {
    const status = await refreshTelemetry();
    if (status) setTelemetrySourceState(status);
    await fetchAllData();
  }, [fetchAllData]);

  const changeTelemetrySource = useCallback(async (source: 'simulator' | 'nokia') => {
    setDevices([]);
    const status = await setTelemetrySource(source);
    if (status) setTelemetrySourceState(status);
    await fetchAllData();
  }, [fetchAllData]);

  // Poll telemetry every 2 seconds
  useEffect(() => {
    getTelemetrySource().then((status) => status && setTelemetrySourceState(status));
    fetchAllData();
    const interval = setInterval(() => {
      fetchAllData();
    }, 2000);
    return () => clearInterval(interval);
  }, [fetchAllData]);

  return (
    <div className="min-h-screen bg-[#070a10] text-slate-100 pb-16">
      
      {/* 1. Header Bar with Tab Switcher */}
      <Header
        accounting={accounting}
        alarms={alarms}
        onRefresh={refreshAllData}
        telemetrySource={telemetrySource}
        onTelemetrySourceChange={changeTelemetrySource}
        activeTab={activeTab}
        onTabChange={(tab) => setActiveTab(tab)}
      />

      <main className="max-w-[1700px] mx-auto px-4 lg:px-8 pt-6 space-y-6">
        
        {/* View Selection Toggle (Mobile/Tablet + Desktop Quick Toggle) */}
        <div className="flex items-center justify-between bg-[#0e1626] border border-cyan-900/40 rounded-xl p-3">
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-400 font-mono">Select View Mode:</span>
            <div className="flex p-1 bg-slate-900 rounded-lg border border-slate-800 text-xs font-mono">
              <button
                onClick={() => setActiveTab('telemetry')}
                className={`px-3 py-1.5 rounded-md font-semibold transition ${
                  activeTab === 'telemetry' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                📊 Optical Telemetry Dashboard
              </button>
              <button
                onClick={() => setActiveTab('digital_twin')}
                className={`px-3 py-1.5 rounded-md font-semibold transition flex items-center gap-1.5 ${
                  activeTab === 'digital_twin' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>🌐 Digital Twin & What-If Engine</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              </button>
              <button
                onClick={() => setActiveTab('quantum')}
                className={`px-3 py-1.5 rounded-md font-semibold transition flex items-center gap-1.5 ${
                  activeTab === 'quantum' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>⚛ Quantum Optimization</span>
              </button>
            </div>
          </div>

          <div className="hidden sm:flex items-center text-xs text-slate-400 font-mono">
            <span>Principle: AI Recommends ➔ Digital Twin Simulates ➔ Policy Validates ➔ Controller Executes</span>
          </div>
        </div>

        {/* TAB 1: Live Telemetry Dashboard */}
        {activeTab === 'telemetry' && (
          <>
            {telemetrySource?.source === 'nokia' && (
              <NokiaCsvWorkflow
                devices={devices}
                ingestionStatus={telemetrySource.csv_ingestion_status}
                sourceError={telemetrySource.last_refresh_error}
              />
            )}

            {telemetrySource?.data_origin === 'project_csv' ? (
              <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-xs text-amber-200">
                Historical CSV mode uses the device-scoped telemetry and history above. Live topology, FCAPS alarms, and simulator-derived predictions are withheld because the project files do not verify those states.
              </div>
            ) : (
              <>
                {/* Network Topology & AI Power Optimization */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  <div className="lg:col-span-7">
                    <NetworkTopology
                      devices={devices}
                      onSelectNode={(nodeName) => setSelectedNodeFilter(nodeName)}
                      telemetrySource={telemetrySource?.source ?? null}
                    />
                  </div>
                  <div className="lg:col-span-5">
                    <PowerOptimization
                      recommendations={recommendations}
                      onActionExecuted={fetchAllData}
                    />
                  </div>
                </div>

                {/* Traffic Prediction & Isolation Forest Anomaly Feed */}
                <PredictionCharts anomalies={anomalies} />

                {/* Device Telemetry Grid */}
                <TelemetryGrid
                  devices={devices}
                  selectedNodeFilter={selectedNodeFilter}
                  onClearNodeFilter={() => setSelectedNodeFilter(null)}
                  telemetrySource={telemetrySource?.source ?? null}
                />

                {/* FCAPS Dashboard */}
                <FcapsDashboard
                  alarms={alarms}
                  accounting={accounting}
                  securityLogs={securityLogs}
                  devices={devices}
                  onRefresh={refreshAllData}
                />
              </>
            )}
          </>
        )}

        {/* TAB 2: Digital Twin & What-If Engine Section */}
        {activeTab === 'digital_twin' && (
          <DigitalTwinDashboard isHistoricalCsv={telemetrySource?.data_origin === 'project_csv'} />
        )}

        {activeTab === 'quantum' && (
          <QuantumOptimizationDashboard isHistoricalCsv={telemetrySource?.data_origin === 'project_csv'} />
        )}

      </main>

      {/* Floating AI Telecom Assistant Chatbot */}
      <OpticalChatbot />

    </div>
  );
}
