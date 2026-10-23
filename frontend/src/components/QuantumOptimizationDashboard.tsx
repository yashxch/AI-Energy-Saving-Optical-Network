'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertCircle,
  CheckCircle,
  Cpu,
  RefreshCw,
  ShieldCheck,
  XCircle
} from 'lucide-react';
import { getQuantumValidation } from '../lib/api';
import {
  QuantumDigitalTwinValidation,
  QuantumSolution,
  QuantumValidationErrorResponse,
  QuantumValidationPendingResponse,
  QuantumValidationResponse,
  QuantumValidationSuccessResponse
} from '../lib/types';

const pipelineSteps = [
  'Telemetry',
  'Candidate Selection',
  'QUBO',
  'QAOA',
  'IBM Quantum QPU',
  'Device Selection',
  'Digital Twin',
  'Policy Validation',
  'Execute / Reject'
];

function isPending(response: QuantumValidationResponse): response is QuantumValidationPendingResponse {
  return response.status === 'pending';
}

function isError(response: QuantumValidationResponse): response is QuantumValidationErrorResponse {
  return response.status === 'error';
}

function isSuccess(response: QuantumValidationResponse): response is QuantumValidationSuccessResponse {
  return response.status === 'APPROVED' || response.status === 'REJECTED';
}

function Metric({
  label,
  value,
  tone = 'text-slate-100'
}: {
  label: string;
  value: React.ReactNode;
  tone?: string;
}) {
  return (
    <div className="rounded-lg bg-slate-900/70 border border-white/10 p-3">
      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">{label}</div>
      <div className={`mt-1 text-sm font-bold font-mono break-words ${tone}`}>{value}</div>
    </div>
  );
}

function SectionTitle({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <h3 className="flex items-center gap-2 text-sm font-bold tracking-wide text-white">
      {icon}
      {title}
    </h3>
  );
}

function StatusBadge({ status }: { status: 'APPROVED' | 'REJECTED' }) {
  const approved = status === 'APPROVED';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-bold font-mono ${
        approved
          ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/40'
          : 'bg-rose-950/60 text-rose-300 border border-rose-500/40'
      }`}
    >
      {approved ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
      {status}
    </span>
  );
}

function QuantumHeader({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5 text-cyan-400" />
          <h2 className="text-xl font-bold tracking-wide text-white">QUANTUM OPTIMIZATION</h2>
        </div>
        <p className="text-xs text-slate-400 mt-1">QAOA-based power optimization using IBM Quantum</p>
      </div>
      <button
        onClick={onRefresh}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-2 text-xs font-mono text-slate-200"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Refresh Result
      </button>
    </div>
  );
}

function Pipeline() {
  return (
    <section className="glass-card rounded-2xl p-5 border border-white/10">
      <SectionTitle icon={<Activity className="w-4 h-4 text-cyan-400" />} title="QUANTUM SAFETY PIPELINE" />
      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs font-mono">
        {pipelineSteps.map((step, index) => (
          <React.Fragment key={step}>
            <span
              className={`rounded-lg border px-2.5 py-2 ${
                step === 'IBM Quantum QPU'
                  ? 'border-cyan-500/50 bg-cyan-950/40 text-cyan-200'
                  : step === 'Execute / Reject'
                    ? 'border-amber-500/40 bg-amber-950/30 text-amber-200'
                    : 'border-slate-700 bg-slate-900/70 text-slate-300'
              }`}
            >
              {step}
            </span>
            {index < pipelineSteps.length - 1 && <span className="text-cyan-500">↓</span>}
          </React.Fragment>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-400">The IBM Quantum QPU produces a proposal. It does not directly control devices.</p>
    </section>
  );
}

function MessageState({
  title,
  message,
  details,
  tone,
  onRefresh
}: {
  title: string;
  message: string;
  details?: string;
  tone: 'amber' | 'rose';
  onRefresh: () => void;
}) {
  const colors = tone === 'amber'
    ? 'border-amber-500/30 bg-amber-950/20 text-amber-300'
    : 'border-rose-500/30 bg-rose-950/20 text-rose-300';

  return (
    <div className={`rounded-xl border p-5 space-y-2 ${colors}`}>
      <div className="font-bold">{title}</div>
      <p className="text-sm text-slate-300">{message}</p>
      {details && <p className="text-xs font-mono break-words">{details}</p>}
      <button
        onClick={onRefresh}
        className="mt-2 inline-flex items-center gap-2 rounded-lg bg-slate-800 hover:bg-slate-700 px-3 py-2 text-xs font-mono text-slate-200"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Refresh Result
      </button>
    </div>
  );
}

function ValidationCard({
  status,
  twin,
  executionPerformed
}: {
  status: 'APPROVED' | 'REJECTED';
  twin: QuantumDigitalTwinValidation | null;
  executionPerformed: boolean;
}) {
  const actions = twin?.actions ?? [];

  return (
    <section className="glass-card rounded-2xl p-5 border border-white/10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <SectionTitle icon={<ShieldCheck className="w-4 h-4 text-cyan-400" />} title="DIGITAL TWIN VALIDATION" />
        <StatusBadge status={status} />
      </div>
      {twin ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
            <Metric label="Action count" value={twin.action_count} />
            <Metric label="Approved count" value={twin.approved_count} />
            <Metric label="Validated saving" value={`${twin.total_power_saving_w.toFixed(1)} W`} tone="text-emerald-300" />
            <Metric label="Execution performed" value={executionPerformed ? 'YES' : 'NO'} tone={executionPerformed ? 'text-amber-300' : 'text-slate-300'} />
          </div>
          <div className="mt-4 text-sm text-slate-300">
            <span className="text-slate-500 font-mono text-xs uppercase">Affected links: </span>
            {twin.affected_links.length
              ? twin.affected_links.map((link) => `${link.source} -> ${link.target} (${link.protection_utilization_pct}%)`).join(', ')
              : 'None returned'}
          </div>
          <p className="mt-3 text-sm text-slate-400">{twin.reason}</p>
          <div className="mt-5">
            <SectionTitle icon={<Activity className="w-4 h-4 text-cyan-400" />} title="ACTION-LEVEL VALIDATION" />
            {actions.length ? (
              <div className="mt-3 space-y-3">
                {actions.map((action, index) => {
                  const approved = action.result === 'APPROVED';
                  const saving = typeof action.saving_w === 'number'
                    ? `${action.saving_w.toFixed(1)} W`
                    : 'Unavailable';

                  return (
                    <div key={`${action.device_id || 'action'}-${index}`} className="rounded-lg border border-white/10 bg-slate-900/50 p-3">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <div className="font-mono text-sm text-cyan-300 break-words">{action.device_id || 'Unknown device'}</div>
                          <div className="text-xs text-slate-400 break-words">{action.action || 'Unknown action'}</div>
                          <div className="text-xs text-slate-500 break-words">
                            Validation traffic: {typeof action.traffic_pct === 'number' ? `${action.traffic_pct}%` : 'Unavailable'}
                          </div>
                        </div>
                        <div className="flex items-center gap-3 text-xs font-mono">
                          <span className={approved ? 'text-emerald-300' : 'text-rose-300'}>
                            {approved ? 'APPROVED' : 'REJECTED'}
                          </span>
                          <span className="text-slate-300">{saving}</span>
                        </div>
                      </div>
                      {!approved && action.reason && (
                        <p className="mt-2 text-xs text-rose-200 break-words">{action.reason}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-400">No action-level validation details were returned.</p>
            )}
          </div>
        </>
      ) : (
        <p className="mt-4 text-sm text-slate-400">Digital Twin validation details were not returned.</p>
      )}
    </section>
  );
}

function SelectedDevices({ solution }: { solution: QuantumSolution | null }) {
  const devices = solution?.selected_devices || [];

  return (
    <section className="glass-card rounded-2xl p-5 border border-white/10">
      <SectionTitle icon={<Activity className="w-4 h-4 text-cyan-400" />} title={`SELECTED DEVICES (${devices.length})`} />
      <div className="overflow-x-auto mt-4">
        <table className="w-full min-w-[650px] text-left text-xs">
          <thead className="text-[10px] uppercase text-slate-500 border-b border-white/10">
            <tr>
              <th className="py-2 px-3">Device ID</th>
              <th className="py-2 px-3">Device type</th>
              <th className="py-2 px-3">Action</th>
              <th className="py-2 px-3">Candidate Snapshot Traffic</th>
              <th className="py-2 px-3">Estimated saving</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {devices.length ? devices.map((device) => (
              <tr key={device.device_id} className="text-slate-300">
                <td className="py-2.5 px-3 text-cyan-300 font-mono">{device.device_id}</td>
                <td className="py-2.5 px-3">{device.device_type}</td>
                <td className="py-2.5 px-3">{device.action}</td>
                <td className="py-2.5 px-3">{device.traffic}%</td>
                <td className="py-2.5 px-3 text-emerald-300">{device.power_saving_w.toFixed(1)} W</td>
              </tr>
            )) : (
              <tr>
                <td colSpan={5} className="py-6 px-3 text-center text-slate-500">No devices selected by the QPU solution.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function OptimizationMetrics({ solution }: { solution: QuantumSolution | null }) {
  if (!solution) return <p className="mt-4 text-sm text-slate-400">No QPU solution was returned.</p>;

  return (
    <div className="grid grid-cols-2 gap-3 mt-4">
      <Metric label="Selected devices" value={solution.num_selected} />
      <Metric label="Maximum actions" value="Not returned by API" tone="text-slate-400" />
      <Metric label="Estimated saving" value={`${solution.total_power_saving_w.toFixed(1)} W`} tone="text-emerald-300" />
      <Metric label="Feasibility" value={solution.feasible ? 'FEASIBLE' : 'INFEASIBLE'} tone={solution.feasible ? 'text-emerald-300' : 'text-rose-300'} />
      <div className="col-span-2">
        <Metric label="QAOA bitstrings" value={`${solution.raw_bitstring} | ${solution.variable_bitstring} | device ${solution.device_bitstring}`} />
      </div>
    </div>
  );
}

function QuantumResult({ result, onRefresh }: { result: QuantumValidationSuccessResponse; onRefresh: () => void }) {
  const solution = result.qpu.solution;
  const twin = result.digital_twin;

  return (
    <div className="space-y-6">
      <QuantumHeader onRefresh={onRefresh} />
      <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/20 px-4 py-3 text-sm text-cyan-100 flex items-start gap-2">
        <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0 text-cyan-400" />
        Quantum output is validated by the Digital Twin and Policy Engine before any device action is executed.
      </div>
      {result.status === 'REJECTED' && <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 px-4 py-3 text-sm text-rose-200">QPU proposal rejected by safety validation. No device state was changed.</div>}
      {result.status === 'APPROVED' && <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-200">Quantum proposal passed Digital Twin validation. Execution is not automatic.</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="glass-card rounded-2xl p-5 border border-white/10">
          <SectionTitle icon={<Activity className="w-4 h-4 text-cyan-400" />} title="QPU RESULT" />
          <div className="grid grid-cols-2 gap-3 mt-4">
            <Metric label="Backend" value={result.qpu.backend} tone="text-cyan-300" />
            <Metric label="Job ID" value={result.qpu.job_id} />
            <Metric label="Shots" value={result.qpu.shots} />
            <Metric label="QPU status" value="DONE" tone="text-emerald-300" />
          </div>
        </section>
        <section className="glass-card rounded-2xl p-5 border border-white/10">
          <SectionTitle icon={<Cpu className="w-4 h-4 text-cyan-400" />} title="QUBO / OPTIMIZATION" />
          <OptimizationMetrics solution={solution} />
        </section>
      </div>

      <SelectedDevices solution={solution} />
      <ValidationCard status={result.status} twin={twin} executionPerformed={result.execution_performed} />
      <Pipeline />
    </div>
  );
}

export function QuantumOptimizationDashboard() {
  const [result, setResult] = useState<QuantumValidationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [requestError, setRequestError] = useState(false);

  const loadResult = useCallback(async () => {
    setLoading(true);
    setRequestError(false);
    const response = await getQuantumValidation();
    if (response) setResult(response);
    else setRequestError(true);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadResult();
  }, [loadResult]);

  if (loading) {
    return <div className="glass-card rounded-2xl p-8 border border-cyan-500/20 text-sm text-cyan-300 font-mono animate-pulse">Loading IBM Quantum validation result...</div>;
  }

  if (requestError || !result) {
    return (
      <div className="glass-card rounded-2xl p-8 border border-rose-500/30 space-y-4">
        <div className="flex items-center gap-2 text-rose-300"><AlertCircle className="w-5 h-5" />Unable to retrieve quantum validation result.</div>
        <button onClick={loadResult} className="inline-flex items-center gap-2 rounded-lg bg-slate-800 hover:bg-slate-700 px-3 py-2 text-xs font-mono text-slate-200"><RefreshCw className="w-3.5 h-3.5" />Refresh Result</button>
      </div>
    );
  }

  if (isPending(result)) {
    return (
      <div className="space-y-6">
        <QuantumHeader onRefresh={loadResult} />
        <MessageState title="IBM Quantum job is pending" message={result.message} details={`Job: ${result.job_id} | QPU status: ${result.qpu_status}`} tone="amber" onRefresh={loadResult} />
        <Pipeline />
      </div>
    );
  }

  if (isError(result)) {
    return (
      <div className="space-y-6">
        <QuantumHeader onRefresh={loadResult} />
        <MessageState title="Quantum validation failed" message={result.message} details={`${result.error_type}: ${result.error}`} tone="rose" onRefresh={loadResult} />
        <Pipeline />
      </div>
    );
  }

  if (isSuccess(result)) return <QuantumResult result={result} onRefresh={loadResult} />;
  return null;
}
