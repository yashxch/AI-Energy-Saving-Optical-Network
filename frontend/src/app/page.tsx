'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Header } from '../components/Header';
import { NetworkTopology } from '../components/NetworkTopology';
import { PowerOptimization } from '../components/PowerOptimization';
import { PredictionCharts } from '../components/PredictionCharts';
import { TelemetryGrid } from '../components/TelemetryGrid';
import { FcapsDashboard } from '../components/FcapsDashboard';
import { OpticalChatbot } from '../components/OpticalChatbot';

import {
  Device,
  Recommendation,
  AnomalyItem,
  FCAPSAlarm,
  FCAPSEnergyAccounting,
  FCAPSSecurityLog
} from '../lib/types';

import {
  getDevices,
  getRecommendations,
  getAnomalies,
  getFCAPSAlarms,
  getFCAPSEnergyAccounting,
  getFCAPSSecurityLogs
} from '../lib/api';

export default function Home() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([]);
  const [alarms, setAlarms] = useState<FCAPSAlarm[]>([]);
  const [accounting, setAccounting] = useState<FCAPSEnergyAccounting | null>(null);
  const [securityLogs, setSecurityLogs] = useState<FCAPSSecurityLog[]>([]);
  const [selectedNodeFilter, setSelectedNodeFilter] = useState<string | null>(null);

  const fetchAllData = useCallback(async () => {
    try {
      const [devsRes, recsRes, anoRes, almRes, accRes, secRes] = await Promise.all([
        getDevices(),
        getRecommendations(),
        getAnomalies(),
        getFCAPSAlarms(),
        getFCAPSEnergyAccounting(),
        getFCAPSSecurityLogs()
      ]);

      if (devsRes.length > 0) setDevices(devsRes);
      setRecommendations(recsRes);
      setAnomalies(anoRes);
      setAlarms(almRes);
      if (accRes) setAccounting(accRes);
      setSecurityLogs(secRes);
    } catch (err) {
      console.warn("Telemetry fetch error:", err);
    }
  }, []);

  // Poll telemetry every 2 seconds
  useEffect(() => {
    fetchAllData();
    const interval = setInterval(() => {
      fetchAllData();
    }, 2000);
    return () => clearInterval(interval);
  }, [fetchAllData]);

  return (
    <div className="min-h-screen bg-[#070a10] text-slate-100 pb-16">
      
      {/* 1. Header Bar */}
      <Header
        accounting={accounting}
        alarms={alarms}
        onRefresh={fetchAllData}
      />

      <main className="max-w-[1700px] mx-auto px-4 lg:px-8 pt-6 space-y-6">
        
        {/* 2. Network Topology & AI Power Optimization */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7">
            <NetworkTopology
              devices={devices}
              onSelectNode={(nodeName) => setSelectedNodeFilter(nodeName)}
            />
          </div>
          <div className="lg:col-span-5">
            <PowerOptimization
              recommendations={recommendations}
              onActionExecuted={fetchAllData}
            />
          </div>
        </div>

        {/* 3. Traffic Prediction & Isolation Forest Anomaly Feed */}
        <PredictionCharts anomalies={anomalies} />

        {/* 4. 100 Optical Devices Telemetry Grid */}
        <TelemetryGrid
          devices={devices}
          selectedNodeFilter={selectedNodeFilter}
          onClearNodeFilter={() => setSelectedNodeFilter(null)}
        />

        {/* 5. 5-Section FCAPS Dashboard (Fault, Config, Accounting, Perf, Security) */}
        <FcapsDashboard
          alarms={alarms}
          accounting={accounting}
          securityLogs={securityLogs}
          devices={devices}
          onRefresh={fetchAllData}
        />

      </main>

      {/* 6. Floating AI Telecom Assistant Chatbot */}
      <OpticalChatbot />

    </div>
  );
}
