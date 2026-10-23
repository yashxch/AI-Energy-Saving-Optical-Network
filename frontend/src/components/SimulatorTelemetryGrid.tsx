'use client';

import React, { useState } from 'react';
import { Cpu, Search, Filter, ShieldCheck, AlertTriangle, Eye, X, Activity, Thermometer, Zap } from 'lucide-react';
import { Device, DeviceType, PowerMode } from '../lib/types';

interface TelemetryGridProps {
  devices: Device[];
  selectedNodeFilter: string | null;
  onClearNodeFilter: () => void;
}

export const SimulatorTelemetryGrid: React.FC<TelemetryGridProps> = ({ devices, selectedNodeFilter, onClearNodeFilter }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');
  const [modeFilter, setModeFilter] = useState<string>('ALL');
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);

  const filteredDevices = devices.filter(d => {
    const matchesSearch = d.id.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          d.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          d.node_location.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === 'ALL' || d.type === typeFilter;
    const matchesMode = modeFilter === 'ALL' || d.power_mode === modeFilter;
    const matchesNode = !selectedNodeFilter || d.node_location === selectedNodeFilter;
    return matchesSearch && matchesType && matchesMode && matchesNode;
  });

  return (
    <div className="glass-card rounded-2xl p-5 border border-white/10 relative">
      
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold text-white tracking-wide">Optical Devices Telemetry Matrix</h2>
            <span className="px-2 py-0.5 text-xs font-mono bg-cyan-950/80 text-cyan-400 border border-cyan-500/30 rounded-md">
              {filteredDevices.length} / {devices.length} Devices Online
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time telemetry feeds for 800G Muxponders, EDFA Amplifiers, ROADMs, and Filter Cards
          </p>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          
          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search ID, name, node..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-slate-900/90 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500 w-44"
            />
          </div>

          {/* Type Filter */}
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="bg-slate-900/90 border border-white/10 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="ALL">All Hardware Types</option>
            <option value="Transponder-800G">800G Transponders</option>
            <option value="EDFA Amplifier">EDFA Amplifiers</option>
            <option value="ROADM WSS">ROADM WSS</option>
            <option value="Filter Card">Filter Cards</option>
          </select>

          {/* Power Mode Filter */}
          <select
            value={modeFilter}
            onChange={(e) => setModeFilter(e.target.value)}
            className="bg-slate-900/90 border border-white/10 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
          >
            <option value="ALL">All Power Modes</option>
            <option value="Normal">Normal Mode</option>
            <option value="Eco">Eco Mode</option>
            <option value="Sleep">Sleep Mode</option>
            <option value="Low Gain">Low Gain Mode</option>
          </select>

          {selectedNodeFilter && (
            <button
              onClick={onClearNodeFilter}
              className="px-2.5 py-1.5 bg-rose-950/60 border border-rose-500/40 text-rose-300 rounded-lg flex items-center gap-1 font-mono hover:bg-rose-900/60 transition"
            >
              Clear Node: {selectedNodeFilter} <X className="w-3 h-3" />
            </button>
          )}

        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto rounded-xl border border-white/10 bg-[#060910]">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-[#0b101d] text-[10px] uppercase font-mono tracking-wider text-slate-400 border-b border-white/10">
            <tr>
              <th className="py-3 px-4">Device ID / Name</th>
              <th className="py-3 px-3">Type</th>
              <th className="py-3 px-3">Node</th>
              <th className="py-3 px-3">Power Mode</th>
              <th className="py-3 px-3">Traffic Load</th>
              <th className="py-3 px-3">Pre-FEC BER</th>
              <th className="py-3 px-3">OSNR (dB)</th>
              <th className="py-3 px-3">DSP Temp</th>
              <th className="py-3 px-3">Power Draw</th>
              <th className="py-3 px-3 text-right">Inspect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 font-mono">
            {filteredDevices.slice(0, 15).map((dev) => {
              const t = dev.telemetry;
              const isWarning = dev.health !== 'Normal';

              return (
                <tr
                  key={dev.id}
                  className={`hover:bg-slate-800/40 transition cursor-pointer ${
                    isWarning ? 'bg-rose-950/20' : ''
                  }`}
                  onClick={() => setSelectedDevice(dev)}
                >
                  <td className="py-2.5 px-4 font-semibold text-cyan-300 flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${isWarning ? 'bg-rose-400 animate-ping' : 'bg-emerald-400'}`} />
                    <div>
                      <div>{dev.id}</div>
                      <div className="text-[10px] text-slate-400 font-sans">{dev.name}</div>
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-slate-300">{dev.type}</td>
                  <td className="py-2.5 px-3 text-slate-400">{dev.node_location}</td>
                  <td className="py-2.5 px-3">
                    <span className={`px-2 py-0.5 text-[10px] rounded border ${
                      dev.power_mode === 'Normal' ? 'bg-cyan-950 text-cyan-400 border-cyan-500/30' :
                      dev.power_mode === 'Sleep' ? 'bg-emerald-950 text-emerald-400 border-emerald-500/30' :
                      'bg-purple-950 text-purple-400 border-purple-500/30'
                    }`}>
                      {dev.power_mode}
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex items-center gap-2 w-28">
                      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-cyan-400 rounded-full"
                          style={{ width: `${t.traffic_utilization_pct}%` }}
                        />
                      </div>
                      <span className="text-[11px] text-slate-300">{t.traffic_utilization_pct}%</span>
                    </div>
                  </td>
                  <td className={`py-2.5 px-3 ${t.pre_fec_ber > 1e-4 ? 'text-rose-400 font-bold' : 'text-slate-300'}`}>
                    {t.pre_fec_ber.toExponential(2)}
                  </td>
                  <td className={`py-2.5 px-3 ${t.osnr_db < 15.0 ? 'text-amber-400 font-bold' : 'text-slate-300'}`}>
                    {t.osnr_db} dB
                  </td>
                  <td className={`py-2.5 px-3 ${t.dsp_temp_c > 75.0 ? 'text-rose-400 font-bold' : 'text-slate-300'}`}>
                    {t.dsp_temp_c}°C
                  </td>
                  <td className="py-2.5 px-3 text-emerald-400 font-bold">
                    {t.power_consumption_w} W
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedDevice(dev);
                      }}
                      className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-cyan-400 transition"
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filteredDevices.length > 15 && (
          <div className="p-2.5 text-center text-xs text-slate-400 bg-slate-900/60 border-t border-white/5 font-mono">
            Showing top 15 devices of {filteredDevices.length} matches (Use search/filters to narrow)
          </div>
        )}
      </div>

      {/* Telemetry Detail Modal Drawer */}
      {selectedDevice && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl border border-cyan-500/30 max-w-2xl w-full p-6 relative text-slate-100 shadow-2xl animate-in fade-in zoom-in duration-200">
            <button
              onClick={() => setSelectedDevice(null)}
              className="absolute top-4 right-4 p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 border-b border-white/10 pb-4 mb-4">
              <div className="p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-cyan-400">
                <Cpu className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">{selectedDevice.name}</h3>
                <div className="flex items-center gap-2 text-xs font-mono text-cyan-400">
                  <span>ID: {selectedDevice.id}</span>
                  <span>•</span>
                  <span>Wavelength: {selectedDevice.wavelength_nm} nm</span>
                  <span>•</span>
                  <span>Node: {selectedDevice.node_location}</span>
                </div>
              </div>
            </div>

            {/* 16 Telemetry Attributes Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Tx Optical Power</div>
                <div className="text-sm font-bold text-cyan-400">{selectedDevice.telemetry.tx_power_dbm} dBm</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Rx Optical Power</div>
                <div className="text-sm font-bold text-cyan-400">{selectedDevice.telemetry.rx_power_dbm} dBm</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Laser Bias Current</div>
                <div className="text-sm font-bold text-slate-200">{selectedDevice.telemetry.laser_bias_ma} mA</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Laser Temp</div>
                <div className="text-sm font-bold text-slate-200">{selectedDevice.telemetry.laser_temp_c}°C</div>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">DSP Temp</div>
                <div className="text-sm font-bold text-amber-400">{selectedDevice.telemetry.dsp_temp_c}°C</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Module Temp</div>
                <div className="text-sm font-bold text-slate-200">{selectedDevice.telemetry.module_temp_c}°C</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Pre-FEC BER</div>
                <div className="text-sm font-bold text-slate-200">{selectedDevice.telemetry.pre_fec_ber.toExponential(2)}</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Post-FEC BER</div>
                <div className="text-sm font-bold text-slate-200">{selectedDevice.telemetry.post_fec_ber}</div>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Q-Factor</div>
                <div className="text-sm font-bold text-purple-400">{selectedDevice.telemetry.q_factor_db} dB</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">OSNR</div>
                <div className="text-sm font-bold text-emerald-400">{selectedDevice.telemetry.osnr_db} dB</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Chromatic Dispersion</div>
                <div className="text-sm font-bold text-slate-200">{selectedDevice.telemetry.chromatic_dispersion} ps/nm</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Fan RPM</div>
                <div className="text-sm font-bold text-slate-200">{selectedDevice.telemetry.fan_rpm} RPM</div>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Supply Voltage</div>
                <div className="text-sm font-bold text-slate-200">{selectedDevice.telemetry.voltage_v} V</div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/80 border border-white/5">
                <div className="text-[10px] text-slate-400">Current Draw</div>
                <div className="text-sm font-bold text-slate-200">{selectedDevice.telemetry.current_a} A</div>
              </div>
              <div className="p-2.5 rounded-lg bg-cyan-950/40 border border-cyan-500/30">
                <div className="text-[10px] text-cyan-400">Traffic Load</div>
                <div className="text-sm font-bold text-cyan-300">{selectedDevice.telemetry.traffic_utilization_pct}%</div>
              </div>
              <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30">
                <div className="text-[10px] text-emerald-400">Active Power</div>
                <div className="text-sm font-bold text-emerald-300">{selectedDevice.telemetry.power_consumption_w} W</div>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-white/10 flex justify-end">
              <button
                onClick={() => setSelectedDevice(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-mono"
              >
                Close Telemetry View
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
};
