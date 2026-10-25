'use client';

import React, { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CheckCircle2, FileSpreadsheet } from 'lucide-react';
import {
  CsvIngestionStatus,
  CsvMetricMapping,
  CsvTelemetryRecord,
  Device,
} from '../lib/types';

const slots = ['device_1', 'device_2'] as const;
type DeviceSlot = (typeof slots)[number];

const csvHistory = (device: Device): CsvTelemetryRecord[] => {
  const history = device.raw_record?.csv_history;
  return Array.isArray(history) ? history as CsvTelemetryRecord[] : [];
};

const metricMapping = (device: Device): Record<string, CsvMetricMapping> => {
  const mapping = device.raw_record?.csv_metric_mapping;
  return mapping && typeof mapping === 'object'
    ? mapping as Record<string, CsvMetricMapping>
    : {};
};

const ingestionSlot = (device: Device): DeviceSlot | null => {
  const ingestion = device.raw_record?.csv_ingestion;
  if (!ingestion || typeof ingestion !== 'object' || !('slot' in ingestion)) return null;
  const slot = ingestion.slot;
  return slot === 'device_1' || slot === 'device_2' ? slot : null;
};

const formatValue = (value: number | undefined, unit: string) => {
  if (value === undefined || !Number.isFinite(value)) return 'No data available';
  const formatted = Math.abs(value) > 0 && Math.abs(value) < 0.001
    ? value.toExponential(3)
    : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  return `${formatted} ${unit}`.trim();
};

export const NokiaCsvWorkflow: React.FC<{
  devices: Device[];
  ingestionStatus: CsvIngestionStatus | null | undefined;
  sourceError?: string | null;
}> = ({ devices, ingestionStatus, sourceError }) => {
  const csvDevices = devices.filter((device) => csvHistory(device).length > 0);
  const [selectedDeviceId, setSelectedDeviceId] = useState('');
  const selectedDevice =
    csvDevices.find((device) => device.id === selectedDeviceId) ?? csvDevices[0];
  const history = selectedDevice ? csvHistory(selectedDevice) : [];
  const mappings = selectedDevice ? metricMapping(selectedDevice) : {};
  const selectedSlot = selectedDevice ? ingestionSlot(selectedDevice) : null;
  const powerSavingReason = selectedSlot
    ? ingestionStatus?.devices?.[selectedSlot]?.power_saving_reason
    : undefined;
  const [selectedMetric, setSelectedMetric] = useState('');
  const [newestFirst, setNewestFirst] = useState(true);
  const metricEntries = Object.entries(mappings);
  const activeMetric = metricEntries.find(([header, mapping]) =>
    (selectedMetric || metricEntries[0]?.[0]) === header ||
    (selectedMetric || metricEntries[0]?.[0]) === mapping.internal_field
  );

  const chartData = useMemo(() => {
    if (!activeMetric) return [];
    const [, mapping] = activeMetric;
    return history.map((record) => ({
      time: new Date(record.timestamp_epoch * 1000).toLocaleTimeString(),
      value: record.metrics[mapping.internal_field],
    }));
  }, [activeMetric, history]);

  return (
    <section className="glass-card rounded-2xl p-5 border border-cyan-900/40 space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white">Nokia CSV telemetry</h2>
          <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-amber-950/70 text-amber-300 border border-amber-500/30 rounded">
            Project-folder files · read only
          </span>
        </div>
        <p className="mt-1 text-xs text-slate-400">
          The backend reads the configured CSV files directly from the project folder. Data is historical and is not a live connection.
        </p>
      </div>
      {sourceError && (
        <div role="alert" className="rounded-lg border border-rose-500/30 bg-rose-950/30 p-3 text-xs text-rose-200">
          Project CSV files could not be loaded: {sourceError}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {slots.map((slot, index) => {
          const imported = ingestionStatus?.devices?.[slot];
          return (
            <div key={slot} className="rounded-xl border border-white/10 bg-slate-950/40 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-cyan-300">Device {index + 1}</h3>
                <span className={`text-[10px] font-mono uppercase ${imported ? 'text-emerald-300' : 'text-slate-500'}`}>
                  {imported ? 'Loaded from project' : 'File unavailable'}
                </span>
              </div>
              {imported && (
                <div className="text-xs text-slate-300">
                  {imported.device_name} <span className="text-slate-500">({imported.device_id})</span>
                  <div className="mt-1 text-slate-500">
                    {imported.filename} · {imported.accepted_rows} accepted · {imported.rejected_rows} rejected · {imported.skipped_rows} skipped
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {csvDevices.length > 0 && selectedDevice && (
        <div className="border-t border-white/10 pt-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-white">Device telemetry history</h3>
              <p className="text-[11px] text-slate-500">Timestamp-free values are treated as UTC. Chart timestamps are displayed in your browser’s local timezone.</p>
            </div>
            <select
              value={selectedDevice.id}
              onChange={(event) => {
                setSelectedDeviceId(event.target.value);
                setSelectedMetric('');
              }}
              className="rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-xs text-white"
            >
              {csvDevices.map((device) => (
                <option key={device.id} value={device.id}>{device.name} ({device.id})</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {metricEntries.map(([header, mapping]) => {
              const latest = history[history.length - 1]?.metrics[mapping.internal_field];
              const first = history[0]?.metrics[mapping.internal_field];
              const hasTrend = history.length > 1 && first !== undefined && latest !== undefined;
              const trend = hasTrend
                ? latest! > first! ? 'Rising' : latest! < first! ? 'Falling' : 'Stable'
                : 'Not available';
              return (
                <button
                  type="button"
                  key={header}
                  onClick={() => setSelectedMetric(mapping.internal_field)}
                  className={`rounded-lg border p-3 text-left ${activeMetric?.[0] === header ? 'border-cyan-500/60 bg-cyan-950/30' : 'border-white/10 bg-slate-950/30'}`}
                >
                  <div className="text-[10px] uppercase text-slate-500">{mapping.display_label}</div>
                  <div className="mt-1 text-sm font-bold text-slate-100">{formatValue(latest, mapping.unit)}</div>
                  <div className="mt-1 text-[10px] text-slate-500">
                    {history.length ? history[history.length - 1].timestamp : 'No data available'} · {trend}
                  </div>
                </button>
              );
            })}
          </div>

          {activeMetric && (
            <div className="rounded-xl border border-white/10 bg-slate-950/30 p-3">
              <div className="mb-2 flex items-center justify-between text-xs text-slate-300">
                <span>{activeMetric[1].display_label} ({activeMetric[1].unit})</span>
                <span>{chartData.length} records</span>
              </div>
              {history.length > 1 ? (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="time" stroke="#94a3b8" tick={{ fontSize: 10 }} />
                      <YAxis stroke="#94a3b8" tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} />
                      <Line type="monotone" dataKey="value" stroke="#22d3ee" dot={false} connectNulls={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="py-8 text-center text-xs text-slate-500">
                  {history.length === 1 ? 'One observation; a trend chart is not available.' : 'No data available.'}
                </div>
              )}
            </div>
          )}

          <div className="overflow-x-auto rounded-xl border border-white/10">
            <div className="flex justify-end border-b border-white/10 bg-slate-900 p-2">
              <button
                onClick={() => setNewestFirst((value) => !value)}
                className="rounded bg-slate-800 px-2.5 py-1 text-[11px] text-slate-300 hover:bg-slate-700"
              >
                {newestFirst ? 'Newest first' : 'Oldest first'}
              </button>
            </div>
            <table className="min-w-full text-left text-[11px] text-slate-300">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <th className="px-3 py-2">Timestamp</th>
                  {metricEntries.map(([header, mapping]) => <th key={header} className="px-3 py-2 whitespace-nowrap">{mapping.display_label} ({mapping.unit})</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {(newestFirst ? [...history].reverse() : history).map((record) => (
                  <tr key={`${record.timestamp}-${record.timestamp_epoch}`}>
                    <td className="px-3 py-2 whitespace-nowrap">{record.timestamp}</td>
                    {metricEntries.map(([, mapping]) => (
                      <td key={mapping.internal_field} className="px-3 py-2 font-mono whitespace-nowrap">
                        {formatValue(record.metrics[mapping.internal_field], mapping.unit)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-950/20 p-3 text-xs text-amber-200">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            {powerSavingReason
              ?? 'Power saving is not eligible from historical CSV telemetry alone. No savings are estimated and no device action is taken.'}
          </div>
        </div>
      )}
    </section>
  );
};
