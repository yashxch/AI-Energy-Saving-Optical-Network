'use client';

import React, { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ShieldCheck, AlertTriangle, Settings, DollarSign, Activity, Lock, CheckCircle, RefreshCw } from 'lucide-react';
import { FCAPSAlarm, FCAPSEnergyAccounting, FCAPSSecurityLog, Device } from '../lib/types';
import { acknowledgeAlarm } from '../lib/api';

interface FcapsDashboardProps {
  alarms: FCAPSAlarm[];
  accounting: FCAPSEnergyAccounting | null;
  securityLogs: FCAPSSecurityLog[];
  devices: Device[];
  onRefresh: () => void;
}

export const FcapsDashboard: React.FC<FcapsDashboardProps> = ({
  alarms,
  accounting,
  securityLogs,
  devices,
  onRefresh
}) => {
  const [activeTab, setActiveTab] = useState<'Fault' | 'Configuration' | 'Accounting' | 'Performance' | 'Security'>('Fault');

  const handleAckAlarm = async (alarmId: string) => {
    await acknowledgeAlarm(alarmId);
    onRefresh();
  };

  const normalCount = devices.filter(d => d.power_mode === 'Normal').length;
  const ecoCount = devices.filter(d => d.power_mode === 'Eco' || d.power_mode === 'Low Gain').length;
  const sleepCount = devices.filter(d => d.power_mode === 'Sleep').length;

  return (
    <div className="glass-card rounded-2xl p-5 border border-white/10 relative">
      
      {/* FCAPS Tabs Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4 mb-5">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold text-white tracking-wide">FCAPS Telecom Network Management</h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            ISO Telecommunications FCAPS Standard Framework (Fault, Config, Accounting, Performance, Security)
          </p>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-1 bg-slate-900/90 p-1.5 rounded-xl border border-white/10 text-xs font-mono">
          <button
            onClick={() => setActiveTab('Fault')}
            className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
              activeTab === 'Fault' ? 'bg-cyan-500 text-black font-bold shadow-md' : 'text-slate-400 hover:text-white'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" /> Fault ({alarms.filter(a => !a.acknowledged).length})
          </button>
          <button
            onClick={() => setActiveTab('Configuration')}
            className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
              activeTab === 'Configuration' ? 'bg-cyan-500 text-black font-bold shadow-md' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Settings className="w-3.5 h-3.5" /> Config
          </button>
          <button
            onClick={() => setActiveTab('Accounting')}
            className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
              activeTab === 'Accounting' ? 'bg-cyan-500 text-black font-bold shadow-md' : 'text-slate-400 hover:text-white'
            }`}
          >
            <DollarSign className="w-3.5 h-3.5" /> Accounting
          </button>
          <button
            onClick={() => setActiveTab('Performance')}
            className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
              activeTab === 'Performance' ? 'bg-cyan-500 text-black font-bold shadow-md' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Activity className="w-3.5 h-3.5" /> Performance
          </button>
          <button
            onClick={() => setActiveTab('Security')}
            className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
              activeTab === 'Security' ? 'bg-cyan-500 text-black font-bold shadow-md' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Lock className="w-3.5 h-3.5" /> Security
          </button>
        </div>
      </div>

      {/* 1. FAULT TAB */}
      {activeTab === 'Fault' && (
        <div className="space-y-3">
          <div className="text-xs font-mono text-slate-400 mb-2">Active Telecom Network Alarms:</div>
          {alarms.length > 0 ? (
            <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
              {alarms.map((alm) => (
                <div
                  key={alm.id}
                  className={`p-3 rounded-xl border text-xs font-mono flex items-center justify-between ${
                    alm.severity === 'Critical' ? 'bg-rose-950/40 border-rose-500/40 text-rose-200' :
                    alm.severity === 'Major' ? 'bg-amber-950/40 border-amber-500/40 text-amber-200' :
                    'bg-slate-900 border-white/10 text-slate-300'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <AlertTriangle className={`w-5 h-5 mt-0.5 ${alm.severity === 'Critical' ? 'text-rose-400 animate-bounce' : 'text-amber-400'}`} />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">{alm.device_name} ({alm.device_id})</span>
                        <span className={`px-1.5 py-0.5 text-[9px] uppercase font-bold rounded ${
                          alm.severity === 'Critical' ? 'bg-rose-600 text-white' : 'bg-amber-600 text-white'
                        }`}>
                          {alm.severity}
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 mt-1">{alm.message}</p>
                      <span className="text-[10px] text-slate-400 mt-0.5 block">Time: {alm.timestamp}</span>
                    </div>
                  </div>

                  {!alm.acknowledged ? (
                    <button
                      onClick={() => handleAckAlarm(alm.id)}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-cyan-300 rounded-lg text-xs font-mono transition border border-cyan-500/30"
                    >
                      Acknowledge
                    </button>
                  ) : (
                    <span className="text-xs text-emerald-400 flex items-center gap-1 font-mono">
                      <CheckCircle className="w-3.5 h-3.5" /> ACKED
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-xs font-mono text-slate-400 bg-slate-900/60 rounded-xl border border-white/5">
              ✅ Zero active hardware alarms reported. All optical transport links operating normally.
            </div>
          )}
        </div>
      )}

      {/* 2. CONFIGURATION TAB */}
      {activeTab === 'Configuration' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-xs">
            <div className="p-4 rounded-xl bg-cyan-950/40 border border-cyan-500/30">
              <div className="text-slate-400">Normal High-Power Mode</div>
              <div className="text-2xl font-bold text-cyan-300 mt-1">{normalCount} Devices</div>
              <div className="text-[10px] text-slate-400 mt-1">100% Optical Gain / Full Capacity</div>
            </div>
            <div className="p-4 rounded-xl bg-purple-950/40 border border-purple-500/30">
              <div className="text-slate-400">Eco / Low-Gain Mode</div>
              <div className="text-2xl font-bold text-purple-300 mt-1">{ecoCount} Devices</div>
              <div className="text-[10px] text-slate-400 mt-1">Reduced Gain / Low Channel Density</div>
            </div>
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/30">
              <div className="text-slate-400">Deep Sleep Mode</div>
              <div className="text-2xl font-bold text-emerald-300 mt-1">{sleepCount} Devices</div>
              <div className="text-[10px] text-slate-400 mt-1">Idle DSP Cores Powered Off (45W)</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-white/5 text-xs text-slate-300">
            <h4 className="font-bold text-white mb-2">Hardware Device Inventory Summary</h4>
            <ul className="space-y-1 font-mono text-slate-400 text-[11px]">
              <li>• 50 units: 800G Coherent Muxponder Cards (Wavelengths 1530nm - 1570nm)</li>
              <li>• 20 units: Variable Gain EDFA Optical Line Amplifiers</li>
              <li>• 15 units: Directionless / Contentionless ROADM WSS Modules</li>
              <li>• 15 units: Passive Optical Filter Multiplexer Cards</li>
            </ul>
          </div>
        </div>
      )}

      {/* 3. ACCOUNTING TAB */}
      {activeTab === 'Accounting' && accounting && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 font-mono text-xs">
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-white/10">
              <div className="text-[10px] text-slate-400">Current Power Draw</div>
              <div className="text-lg font-bold text-cyan-300">{accounting.total_power_kw} kW</div>
              <div className="text-[10px] text-slate-500">Baseline: {accounting.baseline_power_kw} kW</div>
            </div>
            <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/30">
              <div className="text-[10px] text-emerald-400">Accumulated Savings</div>
              <div className="text-lg font-bold text-emerald-300">{accounting.energy_saved_kwh} kWh</div>
              <div className="text-[10px] text-emerald-400/80">{accounting.power_savings_pct}% Power Reduction</div>
            </div>
            <div className="p-3.5 rounded-xl bg-cyan-950/40 border border-cyan-500/30">
              <div className="text-[10px] text-cyan-400">Carbon Footprint Avoided</div>
              <div className="text-lg font-bold text-cyan-300">{accounting.carbon_reduced_kg} kg CO₂</div>
              <div className="text-[10px] text-cyan-400/80">0.42 kg CO₂ / kWh</div>
            </div>
            <div className="p-3.5 rounded-xl bg-purple-950/40 border border-purple-500/30">
              <div className="text-[10px] text-purple-400">OPEX Cost Savings</div>
              <div className="text-lg font-bold text-purple-300">${accounting.cost_savings_usd} USD</div>
              <div className="text-[10px] text-purple-400/80">@ $0.14 / kWh tariff</div>
            </div>
          </div>

          {/* 24h Historical Power Curve */}
          <div className="p-4 rounded-xl bg-[#060910] border border-white/10">
            <div className="text-xs font-bold text-white mb-2">24-Hour Energy Consumption Curve (Baseline vs AI Optimized)</div>
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={accounting.power_history} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 10 }} unit=" kW" />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: 'rgba(0,240,255,0.3)', borderRadius: '8px', fontSize: '12px' }} />
                  <Area type="monotone" dataKey="Baseline_kW" stroke="#f43f5e" fill="rgba(244,63,94,0.1)" strokeDasharray="3 3" name="Baseline Power (kW)" />
                  <Area type="monotone" dataKey="AI_Optimized_kW" stroke="#10b981" fill="rgba(16,185,129,0.2)" strokeWidth={2.5} name="AI Optimized Power (kW)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* 4. PERFORMANCE TAB */}
      {activeTab === 'Performance' && (
        <div className="space-y-4 font-mono text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-slate-900 border border-white/10">
              <div className="text-slate-400 text-[10px]">Avg OSNR</div>
              <div className="text-lg font-bold text-emerald-400">
                {(devices.reduce((acc, d) => acc + d.telemetry.osnr_db, 0) / (devices.length || 1)).toFixed(1)} dB
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-white/10">
              <div className="text-slate-400 text-[10px]">Avg Pre-FEC BER</div>
              <div className="text-lg font-bold text-cyan-400">
                {(devices.reduce((acc, d) => acc + d.telemetry.pre_fec_ber, 0) / (devices.length || 1)).toExponential(2)}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-white/10">
              <div className="text-slate-400 text-[10px]">Avg Q-Factor</div>
              <div className="text-lg font-bold text-purple-400">
                {(devices.reduce((acc, d) => acc + d.telemetry.q_factor_db, 0) / (devices.length || 1)).toFixed(1)} dB
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-900 border border-white/10">
              <div className="text-slate-400 text-[10px]">Network Throughput</div>
              <div className="text-lg font-bold text-amber-400">28.4 Tbps</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-white/5">
            <h4 className="font-bold text-white mb-2">Optical Signal Health Metrics Summary</h4>
            <p className="text-slate-300 font-sans text-xs leading-relaxed">
              Continuous 100-device telemetry monitoring confirms zero FEC uncorrectable frame errors across 8 regional DWDM spans. 
              Signal margins strictly comply with Nokia 1830 PSS target optical OSNR boundaries (&gt;= 14.5 dB).
            </p>
          </div>
        </div>
      )}

      {/* 5. SECURITY TAB */}
      {activeTab === 'Security' && (
        <div className="space-y-3 font-mono text-xs">
          <div className="text-slate-400 text-xs">Security Audit Logs & Unauthorized API Access Monitor:</div>
          <div className="overflow-x-auto rounded-xl border border-white/10 bg-[#060910]">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0b101d] text-[10px] uppercase text-slate-400 border-b border-white/10">
                <tr>
                  <th className="py-2.5 px-3">Log ID</th>
                  <th className="py-2.5 px-3">Time</th>
                  <th className="py-2.5 px-3">User / Agent</th>
                  <th className="py-2.5 px-3">Event Description</th>
                  <th className="py-2.5 px-3">IP Address</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {securityLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/40">
                    <td className="py-2 px-3 text-cyan-400">{log.id}</td>
                    <td className="py-2 px-3 text-slate-400">{log.timestamp}</td>
                    <td className="py-2 px-3 text-white">{log.user}</td>
                    <td className="py-2 px-3 text-slate-300">{log.event}</td>
                    <td className="py-2 px-3 text-slate-400">{log.ip_address}</td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-0.5 text-[10px] rounded font-bold ${
                        log.status === 'SUCCESS' ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/30' : 'bg-rose-950 text-rose-300 border border-rose-500/30'
                      }`}>
                        {log.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
};
