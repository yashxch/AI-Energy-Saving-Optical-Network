'use client';

import React, { useState } from 'react';
import { Zap, Activity, AlertTriangle, ShieldCheck, Leaf, Flame, RefreshCw } from 'lucide-react';
import { FCAPSEnergyAccounting, FCAPSAlarm, TelemetrySourceStatus } from '../lib/types';
import { injectFault, clearFault } from '../lib/api';

interface HeaderProps {
  accounting: FCAPSEnergyAccounting | null;
  alarms: FCAPSAlarm[];
  onRefresh: () => void;
  activeTab?: 'telemetry' | 'digital_twin' | 'quantum';
  onTabChange?: (tab: 'telemetry' | 'digital_twin' | 'quantum') => void;
  telemetrySource: TelemetrySourceStatus | null;
  onTelemetrySourceChange: (source: 'simulator' | 'nokia') => Promise<void>;
}

export const Header: React.FC<HeaderProps> = ({ accounting, alarms, onRefresh, activeTab = 'telemetry', onTabChange, telemetrySource, onTelemetrySourceChange }) => {
  const [injecting, setInjecting] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState('TRX-800G-003');
  const [selectedFault, setSelectedFault] = useState('BER_SPIKE');
  const [switchingSource, setSwitchingSource] = useState(false);

  const activeAlarmsCount = alarms.filter(a => !a.acknowledged).length;

  const handleInjectFault = async () => {
    setInjecting(true);
    await injectFault(selectedDevice, selectedFault);
    setInjecting(false);
    onRefresh();
  };

  const handleClearFault = async () => {
    setInjecting(true);
    await clearFault(selectedDevice);
    setInjecting(false);
    onRefresh();
  };

  const handleSourceChange = async (source: 'simulator' | 'nokia') => {
    setSwitchingSource(true);
    await onTelemetrySourceChange(source);
    setSwitchingSource(false);
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-white/10 bg-[#0a0d14]/90 backdrop-blur-xl px-4 lg:px-8 py-3.5 shadow-2xl">
      <div className="max-w-[1700px] mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        
        {/* Branding Title & Tab Switcher */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Zap className="w-5 h-5 animate-pulse" />
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-emerald-400 rounded-full animate-ping" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight text-white glow-text-cyan">
                  AI-Based Power Saving in Optical Networks
                </h1>
                <span className="px-2 py-0.5 text-[10px] font-mono tracking-wide uppercase bg-cyan-950/80 text-cyan-400 border border-cyan-500/30 rounded-md">
                  Nokia 1830 PSS AI Engine
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Autonomous Optical Telemetry Monitoring • Policy-Validated Energy Optimization
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          {onTabChange && (
            <div className="hidden xl:flex items-center p-1 bg-slate-900/80 border border-slate-800 rounded-lg text-xs font-medium font-mono">
              <button
                onClick={() => onTabChange('telemetry')}
                className={`px-3 py-1.5 rounded-md transition flex items-center gap-1.5 ${
                  activeTab === 'telemetry' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>📊 Network Telemetry</span>
              </button>
              <button
                onClick={() => onTabChange('digital_twin')}
                className={`px-3 py-1.5 rounded-md transition flex items-center gap-1.5 ${
                  activeTab === 'digital_twin' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>🌐 Digital Twin & What-If</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              </button>
              <button
                onClick={() => onTabChange('quantum')}
                className={`px-3 py-1.5 rounded-md transition flex items-center gap-1.5 ${
                  activeTab === 'quantum' ? 'bg-cyan-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>⚛ Quantum Optimization</span>
              </button>
            </div>
          )}
        </div>


        {/* Live Energy & Telemetry Quick Stats */}
        <div className="flex flex-wrap items-center gap-3 md:gap-6">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-950/40 border border-cyan-500/30">
            <div>
              <div className="text-[10px] uppercase font-mono tracking-wider text-cyan-400/80">Telemetry source</div>
              <select
                value={telemetrySource?.source || 'simulator'}
                onChange={(event) => handleSourceChange(event.target.value as 'simulator' | 'nokia')}
                disabled={switchingSource}
                className="bg-slate-900 text-xs font-bold font-mono text-white focus:outline-none"
                style={{ colorScheme: 'dark' }}
              >
                <option value="simulator" className="bg-slate-900 text-white">Simulator</option>
                <option value="nokia" className="bg-slate-900 text-white">
                  {telemetrySource?.data_origin === 'csv_snapshot' ? 'Nokia / CSV snapshot' : 'Nokia / Live PMDATA'}
                </option>
              </select>
              <div className="text-[10px] text-slate-400">
                {switchingSource
                  ? 'Switching…'
                  : telemetrySource?.data_origin === 'csv_snapshot'
                    ? `${telemetrySource.device_count} elements • 15-minute CSV snapshot`
                    : `${telemetrySource?.device_count ?? 0} devices • ${telemetrySource?.refresh_status ?? 'unknown'}`}
              </div>
            </div>
            <button onClick={onRefresh} className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300" title="Refresh selected telemetry source">
              <RefreshCw className={`w-3.5 h-3.5 ${switchingSource ? 'animate-spin' : ''}`} />
            </button>
            <span
              className={`px-2 py-1 rounded-md border text-[10px] font-mono font-bold uppercase tracking-wide ${
                telemetrySource?.source === 'nokia'
                  ? 'bg-amber-950/70 text-amber-300 border-amber-500/40'
                  : 'bg-emerald-950/70 text-emerald-300 border-emerald-500/40'
              }`}
            >
              {telemetrySource?.data_origin === 'csv_snapshot'
                ? 'CSV snapshot'
                : telemetrySource?.source === 'nokia' ? 'Nokia data' : 'Simulated data'}
            </span>
          </div>
          
          {/* Active Power & Savings */}
          <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-400">
            <Zap className="w-4 h-4 text-emerald-400" />
            <div>
              <div className="text-[10px] uppercase font-mono tracking-wider text-emerald-400/80">Energy Saved</div>
              <div className="text-xs font-bold font-mono">
                {accounting ? `${accounting.energy_saved_kwh.toFixed(1)} kWh` : '—'}
                {accounting && (
                  <span className="ml-1 text-[10px] text-emerald-300">({accounting.power_savings_pct}%)</span>
                )}
              </div>
            </div>
          </div>

          {/* Carbon Offset */}
          <div className="hidden lg:flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-cyan-950/40 border border-cyan-500/30 text-cyan-400">
            <Leaf className="w-4 h-4 text-cyan-400" />
            <div>
              <div className="text-[10px] uppercase font-mono tracking-wider text-cyan-400/80">CO₂ Avoided</div>
              <div className="text-xs font-bold font-mono">
                {accounting ? `${accounting.carbon_reduced_kg.toFixed(1)} kg` : '—'}
              </div>
            </div>
          </div>

          {/* Active Alarms */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
            activeAlarmsCount > 0 ? 'bg-rose-950/40 border-rose-500/40 text-rose-400' : 'bg-slate-900/60 border-slate-800 text-slate-400'
          }`}>
            <AlertTriangle className={`w-4 h-4 ${activeAlarmsCount > 0 ? 'animate-bounce text-rose-400' : ''}`} />
            <div>
              <div className="text-[10px] uppercase font-mono tracking-wider">Active Alarms</div>
              <div className="text-xs font-bold font-mono">
                {activeAlarmsCount > 0 ? `${activeAlarmsCount} Unack Alarms` : 'Zero Faults'}
              </div>
            </div>
          </div>

          {/* Fault Simulation Controls */}
          <div className="flex items-center gap-2 pl-3 border-l border-white/10">
            <div className="flex flex-col text-[10px] font-mono text-slate-400">
              <span className="text-slate-500 uppercase">Demo Fault Simulator</span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <select
                  value={selectedDevice}
                  onChange={(e) => setSelectedDevice(e.target.value)}
                  className="bg-slate-900 border border-white/10 text-xs rounded px-1.5 py-0.5 text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="TRX-800G-003">TRX-003</option>
                  <option value="TRX-800G-012">TRX-012</option>
                  <option value="EDFA-AMP-005">EDFA-005</option>
                </select>
                <select
                  value={selectedFault}
                  onChange={(e) => setSelectedFault(e.target.value)}
                  className="bg-slate-900 border border-white/10 text-xs rounded px-1.5 py-0.5 text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="BER_SPIKE">BER Spike</option>
                  <option value="OVERHEAT">Overheat</option>
                  <option value="OSNR_DROP">OSNR Drop</option>
                </select>
                <button
                  onClick={handleInjectFault}
                  disabled={injecting}
                  className="px-2 py-0.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-medium rounded transition flex items-center gap-1"
                  title="Inject fault into device to test Anomaly & Policy Rejection"
                >
                  <Flame className="w-3 h-3" /> Inject
                </button>
                <button
                  onClick={handleClearFault}
                  disabled={injecting}
                  className="px-2 py-0.5 bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-medium rounded transition flex items-center gap-1"
                  title="Clear simulated fault"
                >
                  Clear
                </button>
              </div>
            </div>

            <button
              onClick={onRefresh}
              className="p-2 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 transition hover:text-cyan-400"
              title="Refresh telemetry"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

        </div>

      </div>
    </header>
  );
};
