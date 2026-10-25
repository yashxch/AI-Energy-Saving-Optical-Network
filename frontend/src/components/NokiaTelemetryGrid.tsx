'use client';

import React, { useState } from 'react';
import { Cpu, Search, Eye, X } from 'lucide-react';
import { Device } from '../lib/types';

interface TelemetryGridProps {
  devices: Device[];
  selectedNodeFilter: string | null;
  onClearNodeFilter: () => void;
}

type MetricItem = [string, string];

const formatMetric = (value: number | string | null | undefined, unit = '') =>
  value === null || value === undefined || value === '' ? '—' : `${value}${unit}`;

const isCsvSnapshot = (device: Device) =>
  Array.isArray(device.raw_record?.csv_available_metrics);

const hasCsvMetric = (device: Device, metric: string) => {
  const availableMetrics = device.raw_record?.csv_available_metrics;
  return !Array.isArray(availableMetrics) || availableMetrics.includes(metric);
};

const formatAvailableMetric = (
  device: Device,
  metric: string,
  value: number | string | null | undefined,
  unit = '',
) => {
  if (!hasCsvMetric(device, metric)) return '—';
  return formatMetric(value, unit);
};

const csvMetricCatalog = [
  { key: 'traffic_utilization_pct', label: 'Traffic utilization', read: (d: Device) => d.telemetry.traffic_utilization_pct, unit: '%' },
  { key: 'pre_fec_ber', label: 'Pre-FEC BER', read: (d: Device) => d.telemetry.pre_fec_ber, format: (v: number) => v.toExponential(2) },
  { key: 'osnr_db', label: 'OSNR', read: (d: Device) => d.telemetry.osnr_db, unit: ' dB' },
  { key: 'dsp_temp_c', label: 'DSP temperature', read: (d: Device) => d.telemetry.dsp_temp_c, unit: '°C' },
  { key: 'power_consumption_w', label: 'Power draw', read: (d: Device) => d.telemetry.power_consumption_w, unit: ' W' },
  { key: 'tx_power_dbm', label: 'Tx Optical Power', read: (d: Device) => d.telemetry.tx_power_dbm, unit: ' dBm' },
  { key: 'rx_power_dbm', label: 'Rx Optical Power', read: (d: Device) => d.telemetry.rx_power_dbm, unit: ' dBm' },
  { key: 'laser_bias_ma', label: 'Laser bias current', read: (d: Device) => d.telemetry.laser_bias_ma, unit: ' mA' },
  { key: 'laser_temp_c', label: 'Laser temperature', read: (d: Device) => d.telemetry.laser_temp_c, unit: '°C' },
  { key: 'module_temp_c', label: 'Module temperature', read: (d: Device) => d.telemetry.module_temp_c, unit: '°C' },
  { key: 'post_fec_ber', label: 'Post-FEC BER', read: (d: Device) => d.telemetry.post_fec_ber, format: (v: number) => v.toExponential(2) },
  { key: 'q_factor_db', label: 'Q-Factor', read: (d: Device) => d.telemetry.q_factor_db, unit: ' dB' },
  { key: 'chromatic_dispersion', label: 'Chromatic dispersion', read: (d: Device) => d.telemetry.chromatic_dispersion, unit: ' ps/nm' },
  { key: 'fan_rpm', label: 'Fan speed', read: (d: Device) => d.telemetry.fan_rpm, unit: ' rpm' },
  { key: 'voltage_v', label: 'Supply voltage', read: (d: Device) => d.telemetry.voltage_v, unit: ' V' },
  { key: 'current_a', label: 'Current draw', read: (d: Device) => d.telemetry.current_a, unit: ' A' },
] as const;

const formatCsvMetric = (device: Device, metric: (typeof csvMetricCatalog)[number]) => {
  const value = metric.read(device);
  if (value === null || value === undefined) return '';
  if ('format' in metric) return metric.format(value);
  return formatMetric(value, 'unit' in metric ? metric.unit : '');
};

export const NokiaTelemetryGrid: React.FC<TelemetryGridProps> = ({
  devices,
  selectedNodeFilter,
  onClearNodeFilter,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [modeFilter, setModeFilter] = useState('ALL');
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);

  const filteredDevices = devices.filter((device) => {
    const query = searchTerm.toLowerCase();
    return (
      (device.id.toLowerCase().includes(query) ||
        device.name.toLowerCase().includes(query) ||
        device.node_location.toLowerCase().includes(query)) &&
      (typeFilter === 'ALL' || device.type === typeFilter) &&
      (modeFilter === 'ALL' || (!isCsvSnapshot(device) && device.power_mode === modeFilter)) &&
      (!selectedNodeFilter || device.node_location === selectedNodeFilter)
    );
  });

  const getMetricGroups = (device: Device): { title: string; items: MetricItem[] }[] => {
    const t = device.telemetry;
    if (isCsvSnapshot(device)) {
      return [{
        title: 'CSV measurements',
        items: csvMetricCatalog
          .filter((metric) => hasCsvMetric(device, metric.key))
          .map((metric) => [metric.label, formatCsvMetric(device, metric)]),
      }];
    }
    return [
      {
        title: 'Optical and FEC',
        items: [
          ['FEC UBC', formatMetric(t.fec_ubc)],
          ['Q-Margin Min', formatMetric(t.q_margin_min_db, ' dB')],
          ['Q-Margin Max', formatMetric(t.q_margin_max_db, ' dB')],
          ['Q-Margin Average', formatMetric(t.q_margin_avg_db, ' dB')],
          ['OPR Min / Max / Avg', `${formatMetric(t.opr_min_dbm)} / ${formatMetric(t.opr_max_dbm)} / ${formatMetric(t.opr_avg_dbm)} dBm`],
          ['Network Output Expected', formatMetric(t.expected_network_output_power_dbm, ' dBm')],
          ['Network Output Measured', formatMetric(t.measured_network_output_power_dbm, ' dBm')],
          ['ESNR Min / Max / Avg', `${formatMetric(t.esnr_min_db)} / ${formatMetric(t.esnr_max_db)} / ${formatMetric(t.esnr_avg_db)} dB`],
        ],
      },
      {
        title: 'Lane Power',
        items: [
          ['Rx Lanes 1–4', [1, 2, 3, 4].map((lane) => formatMetric(t[`rx_lane_power_${lane}_dbm` as keyof typeof t] as number, ' dBm')).join('  |  ')],
          ['Tx Lanes 1–4', [1, 2, 3, 4].map((lane) => formatMetric(t[`tx_lane_power_${lane}_dbm` as keyof typeof t] as number, ' dBm')).join('  |  ')],
        ],
      },
      {
        title: 'Module and Channel',
        items: [
          ['Laser Case Temperature', formatMetric(t.laser_case_temp_c, '°C')],
          ['Admin / Qualifier', `${formatMetric(t.admin_state)} / ${formatMetric(t.state_qualifier)}`],
          ['Status LED / Capability', `${formatMetric(t.status_led)} / ${formatMetric(t.oper_capability)}`],
          ['Module Type', formatMetric(t.module_type)],
          ['Rates', `${formatMetric(t.max_port_rate)} / ${formatMetric(t.signal_rate)} / ${formatMetric(t.odu_rate)}`],
          ['Tx / Rx Frequency', `${formatMetric(t.channel_tx_frequency_thz)} / ${formatMetric(t.channel_rx_frequency_thz)} THz`],
          ['Tx / Rx Offset', `${formatMetric(t.channel_tx_offset_ghz)} / ${formatMetric(t.channel_rx_offset_ghz)} GHz`],
          ['Grid / Span / OTSiG', `${formatMetric(t.grid_step_size_ghz)} GHz / ${formatMetric(t.link_span_km)} km / ${formatMetric(t.otsig_id)}`],
          ['Timestamp', t.timestamp ? new Date(t.timestamp * 1000).toLocaleString() : '—'],
        ],
      },
      {
        title: 'Traffic, Errors and Health',
        items: [
          ['Bandwidth / Utilization', `${formatMetric(t.bandwidth_gbps)} Gbps / ${formatMetric(t.confirmed_utilization_pct, '%')}`],
          ['Port Utilization', formatMetric(t.port_utilization_pct, '%')],
          ['Ethernet Rx / Tx Octets', `${formatMetric(t.eth_octets_rx)} / ${formatMetric(t.eth_octets_tx)}`],
          ['Ethernet Rx / Tx Packets', `${formatMetric(t.eth_packets_rx)} / ${formatMetric(t.eth_packets_tx)}`],
          ['Ethernet Rx / Tx Errors', `${formatMetric(t.eth_errors_rx)} / ${formatMetric(t.eth_errors_tx)}`],
          ['Ethernet Error Rate', formatMetric(t.eth_error_rate_pct, '%')],
          ['PCS CV / ES', `${formatMetric(t.cv_pcs)} / ${formatMetric(t.es_pcs)}`],
          ['PCS SEFS / SES', `${formatMetric(t.sefs_pcs)} / ${formatMetric(t.ses_pcs)}`],
          ['Connection', `${formatMetric(t.connection_state)} / ${formatMetric(t.connection_type)} / ${formatMetric(t.connection_rate)}`],
          ['Endpoints', `${formatMetric(t.endpoint_source)} → ${formatMetric(t.endpoint_target)}`],
          ['AINS', `${formatMetric(t.ains_state)} / ${formatMetric(t.ains_timer_sec, ' s')}`],
          ['Power / Fan', `${formatMetric(t.device_power_w, ' W')} / ${formatMetric(t.card_power_w, ' W')} / ${formatMetric(t.fan_status)}`],
          ['Environment', `${formatMetric(t.module_health)} / ${formatMetric(t.ambient_temp_c, '°C')} / ${formatMetric(t.humidity_pct, '%')}`],
        ],
      },
    ];
  };

  const coreMetrics = (device: Device): MetricItem[] => {
    const t = device.telemetry;
    if (isCsvSnapshot(device)) {
      const coreKeys = new Set([
        'traffic_utilization_pct',
        'pre_fec_ber',
        'osnr_db',
        'power_consumption_w',
        'tx_power_dbm',
        'rx_power_dbm',
        'q_factor_db',
      ]);
      return csvMetricCatalog
        .filter((metric) => coreKeys.has(metric.key) && hasCsvMetric(device, metric.key))
        .map((metric) => [metric.label, formatCsvMetric(device, metric)]);
    }
    return [
      ['Traffic', formatMetric(t.traffic_utilization_pct, '%')],
      ['Pre-FEC BER', hasCsvMetric(device, 'pre_fec_ber') ? t.pre_fec_ber.toExponential(2) : '—'],
      ['OSNR', formatAvailableMetric(device, 'osnr_db', t.osnr_db, ' dB')],
      ['ESNR', formatAvailableMetric(device, 'esnr_db', t.esnr_db, ' dB')],
      ['DSP Temp', formatAvailableMetric(device, 'dsp_temp_c', t.dsp_temp_c, '°C')],
      ['Power Draw', formatAvailableMetric(device, 'power_consumption_w', t.power_consumption_w, ' W')],
      ['Q-Factor', formatAvailableMetric(device, 'q_factor_db', t.q_factor_db, ' dB')],
    ];
  };

  const renderMetricCard = ([label, value]: MetricItem) => (
    <div key={label} className={`rounded-lg border px-3 py-2 ${value === '—' ? 'bg-slate-950/40 border-white/5' : 'bg-slate-900/80 border-white/10'}`}>
      <div className="text-[10px] uppercase tracking-wide text-slate-500 truncate" title={label}>{label}</div>
      <div className={`mt-1 text-sm font-bold break-words ${value === '—' ? 'text-slate-600' : 'text-slate-200'}`}>{value}</div>
    </div>
  );

  const csvSnapshot = devices.some(isCsvSnapshot);
  const visibleCsvMetrics = csvMetricCatalog.filter((metric) =>
    devices.some((device) => hasCsvMetric(device, metric.key))
  );

  return (
    <div className="glass-card rounded-2xl p-5 border border-white/10 relative">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold text-white tracking-wide">Optical Devices Telemetry Matrix</h2>
            <span className="px-2 py-0.5 text-xs font-mono bg-cyan-950/80 text-cyan-400 border border-cyan-500/30 rounded-md">
              {filteredDevices.length} / {devices.length} Devices
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {devices.some(isCsvSnapshot)
              ? 'Project-folder CSV telemetry; blank metrics were not present in the source files.'
              : 'Select a device to inspect organized live telemetry.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search ID, name, node..."
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              className="bg-slate-900/90 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500 w-44"
            />
          </div>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="bg-slate-900/90 border border-white/10 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono">
            <option value="ALL">All Hardware Types</option>
            <option value="Transponder-800G">800G Transponders</option>
            <option value="EDFA Amplifier">EDFA Amplifiers</option>
            <option value="ROADM WSS">ROADM WSS</option>
            <option value="Filter Card">Filter Cards</option>
            <option value="Network Element">Network Elements</option>
          </select>
          {!csvSnapshot && (
            <select value={modeFilter} onChange={(event) => setModeFilter(event.target.value)} className="bg-slate-900/90 border border-white/10 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono">
              <option value="ALL">All Power Modes</option>
              <option value="Normal">Normal Mode</option>
              <option value="Eco">Eco Mode</option>
              <option value="Sleep">Sleep Mode</option>
              <option value="Low Gain">Low Gain Mode</option>
            </select>
          )}
          {selectedNodeFilter && (
            <button onClick={onClearNodeFilter} className="px-2.5 py-1.5 bg-rose-950/60 border border-rose-500/40 text-rose-300 rounded-lg">
              Clear Node: {selectedNodeFilter} <X className="inline w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-white/10 bg-[#060910]">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-[#0b101d] text-[10px] uppercase font-mono tracking-wider text-slate-400 border-b border-white/10">
            <tr>
              <th className="py-3 px-4">Device ID / Name</th>
              <th className="py-3 px-3">Type</th>
              <th className="py-3 px-3">Node</th>
              {!csvSnapshot && <th className="py-3 px-3">Mode</th>}
              {csvSnapshot
                ? visibleCsvMetrics.map((metric) => <th key={metric.key} className="py-3 px-3">{metric.label}</th>)
                : <>
                    <th className="py-3 px-3">Traffic</th>
                    <th className="py-3 px-3">Pre-FEC BER</th>
                    <th className="py-3 px-3">OSNR</th>
                    <th className="py-3 px-3">DSP Temp</th>
                    <th className="py-3 px-3">Power</th>
                  </>}
              <th className="py-3 px-3 text-right">View</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 font-mono">
            {filteredDevices.slice(0, 15).map((device) => {
              const t = device.telemetry;
              const warning = device.health !== 'Normal';
              const statusDot = isCsvSnapshot(device)
                ? 'bg-slate-500'
                : warning ? 'bg-rose-400' : 'bg-emerald-400';
              return (
                <tr key={device.id} onClick={() => setSelectedDevice(device)} className={`hover:bg-slate-800/40 transition cursor-pointer ${warning ? 'bg-rose-950/20' : ''}`}>
                  <td className="py-2.5 px-4 font-semibold text-cyan-300"><span className={`inline-block w-2 h-2 rounded-full mr-2 ${statusDot}`} />{device.id}<div className="text-[10px] text-slate-400 font-sans ml-4">{device.name}</div></td>
                  <td className="py-2.5 px-3">{device.type}</td>
                  <td className="py-2.5 px-3 text-slate-400">{device.node_location}</td>
                  {!csvSnapshot && <td className="py-2.5 px-3">{device.power_mode}</td>}
                  {csvSnapshot
                    ? visibleCsvMetrics.map((metric) => (
                        <td key={metric.key} className="py-2.5 px-3">
                          {hasCsvMetric(device, metric.key) ? formatCsvMetric(device, metric) : ''}
                        </td>
                      ))
                    : <>
                        <td className="py-2.5 px-3">{formatAvailableMetric(device, 'traffic_utilization_pct', t.traffic_utilization_pct, '%')}</td>
                        <td className={`py-2.5 px-3 ${t.pre_fec_ber > 1e-4 ? 'text-rose-400 font-bold' : ''}`}>{formatAvailableMetric(device, 'pre_fec_ber', t.pre_fec_ber.toExponential(2))}</td>
                        <td className={`py-2.5 px-3 ${t.osnr_db < 15 ? 'text-amber-400 font-bold' : ''}`}>{formatAvailableMetric(device, 'osnr_db', t.osnr_db, ' dB')}</td>
                        <td className={`py-2.5 px-3 ${t.dsp_temp_c > 75 ? 'text-rose-400 font-bold' : ''}`}>{formatAvailableMetric(device, 'dsp_temp_c', t.dsp_temp_c, '°C')}</td>
                        <td className="py-2.5 px-3 text-emerald-400 font-bold">{formatAvailableMetric(device, 'power_consumption_w', t.power_consumption_w, ' W')}</td>
                      </>}
                  <td className="py-2.5 px-3 text-right"><button onClick={(event) => { event.stopPropagation(); setSelectedDevice(device); }} className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-cyan-400"><Eye className="w-3.5 h-3.5" /></button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filteredDevices.length > 15 && <div className="p-2.5 text-center text-xs text-slate-400 bg-slate-900/60 border-t border-white/5 font-mono">Showing 15 of {filteredDevices.length} matches. Use search or filters to narrow the list.</div>}
      </div>

      {selectedDevice && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl border border-cyan-500/30 max-w-6xl max-h-[92vh] overflow-y-auto w-full p-6 relative text-slate-100 shadow-2xl">
            <button onClick={() => setSelectedDevice(null)} className="absolute top-4 right-4 p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
            <div className="flex items-center gap-3 border-b border-white/10 pb-4 mb-4">
              <div className="p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-cyan-400"><Cpu className="w-6 h-6" /></div>
              <div>
                <h3 className="text-lg font-bold text-white">{selectedDevice.name}</h3>
                <div className="flex flex-wrap gap-2 text-xs font-mono text-cyan-400">
                  <span>{selectedDevice.id}</span><span>•</span><span>{selectedDevice.type}</span><span>•</span><span>{selectedDevice.node_location} → {selectedDevice.target_node}</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mb-4">
              {coreMetrics(selectedDevice).map(renderMetricCard)}
            </div>

            <div className="space-y-3">
              {getMetricGroups(selectedDevice).map((group, index) => (
                <details key={group.title} open={index === 0} className="group rounded-xl border border-white/10 bg-slate-950/30">
                  <summary className="cursor-pointer list-none px-4 py-3 flex items-center justify-between text-xs font-bold uppercase tracking-wider text-cyan-400">
                    <span>{group.title}</span><span className="text-slate-500 group-open:rotate-180 transition">▼</span>
                  </summary>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 p-3 border-t border-white/10">
                    {group.items.map(renderMetricCard)}
                  </div>
                </details>
              ))}
            </div>

            <details className="group mt-3 rounded-xl border border-white/10 bg-slate-950/30">
              <summary className="cursor-pointer list-none px-4 py-3 flex items-center justify-between text-xs font-bold uppercase tracking-wider text-cyan-400">
                <span>Network identifiers</span><span className="text-slate-500 group-open:rotate-180 transition">▼</span>
              </summary>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 p-3 border-t border-white/10">
                {([
                  ['Device name', selectedDevice.name],
                  ['NE Name', selectedDevice.ne_name],
                  ['Description', selectedDevice.description],
                  ['Chassis', selectedDevice.chassis_id],
                  ['Equipment', selectedDevice.equipment_name],
                  ['Card', selectedDevice.card_name],
                  ['Interface', selectedDevice.interface_name],
                  ['Shelf', selectedDevice.shelf_id],
                  ['Slot', selectedDevice.slot_id],
                  ['Port', selectedDevice.port_id],
                  ['Wavelength', formatMetric(selectedDevice.wavelength_nm, ' nm')],
                ] as [string, string | number | null | undefined][]).map(([label, value]) =>
                  renderMetricCard([label, formatMetric(value)])
                )}
              </div>
            </details>

            <div className="mt-4 pt-4 border-t border-white/10 flex justify-end">
              <button onClick={() => setSelectedDevice(null)} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-mono">Close Telemetry View</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
