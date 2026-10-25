'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  CheckCircle,
  Cpu,
  RefreshCw,
  ShieldCheck,
  XCircle
} from 'lucide-react';
import {
  getExistingQuantumJob,
  getQuantumOptimizationRun,
  startQuantumOptimization
} from '../lib/api';
import {
  LocalQaoaAnalysis,
  QuantumDigitalTwinValidation,
  QuantumSolution,
  QuantumValidationErrorResponse,
  QuantumValidationPendingResponse,
  QuantumValidationResponse,
  QuantumValidationSuccessResponse,
  QuantumOptimizationRun
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
  'Recommend / Reject'
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

function QuantumHeader({ onRefresh }: { onRefresh?: () => void }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5 text-cyan-400" />
          <h2 className="text-xl font-bold tracking-wide text-white">QUANTUM OPTIMIZATION</h2>
        </div>
        <p className="text-xs text-slate-400 mt-1">QAOA-based power optimization using IBM Quantum</p>
      </div>
      {onRefresh && (
        <button
          onClick={onRefresh}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-2 text-xs font-mono text-slate-200"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Result
        </button>
      )}
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
                  : step === 'Recommend / Reject'
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

export function QuantumOptimizationDashboard({ isHistoricalCsv = false }: { isHistoricalCsv?: boolean }) {
  const [run, setRun] = useState<QuantumOptimizationRun | null>(null);
  const [jobIdInput, setJobIdInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [requestMessage, setRequestMessage] = useState('');
  const pollingRef = useRef(false);

  const startRun = useCallback(async () => {
    setIsSubmitting(true);
    setRequestMessage('');
    const response = await startQuantumOptimization(128);
    if (response) {
      setRun(response);
      setJobIdInput(response.job_id ?? '');
      if (response.run_id) window.localStorage.setItem('optical-qpu-run-id', response.run_id);
      if (response.job_id) window.localStorage.setItem('optical-qpu-job-id', response.job_id);
    } else {
      setRun({
        execution_method: 'ibm_qpu',
        status: 'error',
        message: 'The QPU submission request failed. Check the backend and its safe error logs before retrying.',
        execution_performed: false
      });
    }
    setIsSubmitting(false);
  }, []);

  const retrieveExistingJob = useCallback(async (requestedJobId = jobIdInput) => {
    const normalizedJobId = requestedJobId.trim();
    if (!normalizedJobId) {
      setRequestMessage('Enter an IBM job ID to retrieve its existing status. This does not submit a job.');
      return;
    }

    setIsRefreshing(true);
    setRequestMessage('');
    const response = await getExistingQuantumJob(normalizedJobId);
    if (response) {
      setRun(response);
      setJobIdInput(normalizedJobId);
      window.localStorage.setItem('optical-qpu-job-id', normalizedJobId);
      if (response.run_id) window.localStorage.setItem('optical-qpu-run-id', response.run_id);
      else window.localStorage.removeItem('optical-qpu-run-id');
    } else {
      setRequestMessage('Could not retrieve this job from the backend. No replacement job was submitted.');
    }
    setIsRefreshing(false);
  }, [jobIdInput]);

  const refreshCurrentResult = useCallback(async () => {
    if (run?.run_id) {
      setIsRefreshing(true);
      setRequestMessage('');
      const response = await getQuantumOptimizationRun(run.run_id);
      if (response) setRun(response);
      else setRequestMessage('Could not refresh this run. Its IBM job was not resubmitted.');
      setIsRefreshing(false);
      return;
    }
    await retrieveExistingJob(run?.job_id ?? jobIdInput);
  }, [jobIdInput, retrieveExistingJob, run?.job_id, run?.run_id]);

  useEffect(() => {
    const activeJobId = run?.job_id;
    if (!activeJobId || !['queued', 'running'].includes(run.status)) return;

    let active = true;
    const poll = async () => {
      if (pollingRef.current) return;
      pollingRef.current = true;
      try {
        const response = run.run_id
          ? await getQuantumOptimizationRun(run.run_id)
          : await getExistingQuantumJob(activeJobId);
        if (active && response) setRun(response);
        else if (active && !response) {
          setRequestMessage('Automatic status refresh failed. Use Refresh Result to retry; no replacement job was submitted.');
        }
      } finally {
        pollingRef.current = false;
      }
    };

    const interval = setInterval(() => void poll(), 8000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [run?.job_id, run?.run_id, run?.status]);

  const isPendingRun = run?.status === 'queued' || run?.status === 'running';
  const recommendations = run?.recommendations ?? [];
  const selectedSolution = run?.qpu_solution;
  const validation = run?.digital_twin;
  const terminalFailure = ['failed', 'cancelled', 'error', 'rejected', 'no_candidates'].includes(run?.status ?? '');
  const bannerTone = terminalFailure
    ? 'border-rose-500/40 bg-rose-950/30 text-rose-100'
    : run?.metadata_available === false
      ? 'border-amber-500/40 bg-amber-950/30 text-amber-100'
    : run?.status === 'completed'
      ? 'border-emerald-500/40 bg-emerald-950/30 text-emerald-100'
      : isPendingRun
        ? 'border-amber-500/40 bg-amber-950/30 text-amber-100'
        : 'border-slate-700 bg-slate-900/70 text-slate-200';
  const pipelineCurrentIndex = run?.metadata_available === false
    ? 4
    : run?.status === 'queued' || run?.status === 'running'
    ? 4
    : run?.status === 'completed' || run?.status === 'rejected'
      ? 8
      : run?.status === 'failed' || run?.status === 'cancelled' || run?.status === 'error'
        ? 4
        : -1;

  useEffect(() => {
    const storedJobId = window.localStorage.getItem('optical-qpu-job-id');
    const storedRunId = window.localStorage.getItem('optical-qpu-run-id');
    if (storedJobId) setJobIdInput(storedJobId);
    if (!storedRunId) return;

    let active = true;
    void getQuantumOptimizationRun(storedRunId).then((storedRun) => {
      if (active && storedRun) {
        setRun(storedRun);
        if (storedRun.job_id) setJobIdInput(storedRun.job_id);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-cyan-900/60 bg-[#07111f] p-4 sm:p-5 space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-[0.22em] text-cyan-500 font-mono">NOKIA 1830 PSS / QUANTUM ENGINE</p>
            <h2 className="mt-1 flex items-center gap-2 text-xl font-bold tracking-wide text-white">
              <Cpu className="h-5 w-5 text-cyan-400" /> QUANTUM OPTIMIZATION
            </h2>
            <p className="mt-1 text-xs text-slate-400">QAOA-based power optimization using IBM Quantum Runtime</p>
          </div>
          <button
            type="button"
            onClick={() => void refreshCurrentResult()}
            disabled={isRefreshing || isSubmitting}
            className="inline-flex items-center justify-center gap-2 rounded-md border border-cyan-900 bg-[#0b1a2a] px-3 py-2 text-xs font-mono text-cyan-200 hover:border-cyan-500 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh Result
          </button>
        </div>

        <div className="flex items-start gap-2 rounded-md border border-cyan-900/70 bg-cyan-950/30 px-3 py-2.5 text-xs leading-relaxed text-cyan-100">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
          IBM produces advisory proposals only. The Digital Twin and Policy Engine validate recommendations; no optical-network actions are executed.
        </div>

        <div className="grid gap-2 md:grid-cols-[minmax(220px,1fr)_auto_auto]">
          <label className="sr-only" htmlFor="existing-ibm-job">Existing IBM job ID</label>
          <input
            id="existing-ibm-job"
            value={jobIdInput}
            onChange={(event) => setJobIdInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                void retrieveExistingJob();
              }
            }}
            placeholder="Enter an existing IBM job ID"
            className="min-w-0 rounded-md border border-slate-700 bg-[#050b14] px-3 py-2 text-xs font-mono text-slate-100 placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
          />
          <button
            type="button"
            onClick={() => void retrieveExistingJob()}
            disabled={isRefreshing || !jobIdInput.trim()}
            className="rounded-md border border-cyan-700 bg-cyan-950/60 px-3 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-900/70 disabled:opacity-50"
          >
            Retrieve Existing Job
          </button>
          <button
            type="button"
            onClick={() => void startRun()}
            disabled={isSubmitting || isPendingRun}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-300 hover:border-amber-600 hover:text-amber-200 disabled:opacity-50"
            title="Submits a new IBM QPU job only when clicked."
          >
            {isSubmitting ? 'Submitting…' : 'Submit New QPU Run'}
          </button>
        </div>
        {requestMessage && <p role="alert" className="text-xs text-amber-200">{requestMessage}</p>}

        {!run && (
          <div className="rounded-md border border-slate-800 bg-[#091321] px-4 py-5 text-sm text-slate-400">
            No result is loaded. Retrieve an existing IBM job by ID; this will not create a new job.
          </div>
        )}

        {run && (
          <div className={`rounded-md border px-4 py-3 ${bannerTone}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-bold tracking-wide">
                {run.status.replaceAll('_', ' ').toUpperCase()}
                {run.job_status && <span className="ml-2 font-mono text-xs opacity-80">IBM {run.job_status}</span>}
              </div>
              {run.validation_status && (
                <span className={`rounded border px-2 py-1 text-[10px] font-mono ${
                  run.validation_status === 'APPROVED'
                    ? 'border-emerald-600/60 text-emerald-300'
                    : 'border-rose-600/60 text-rose-300'
                }`}>
                  POLICY {run.validation_status}
                </span>
              )}
            </div>
            <p className="mt-1 text-xs leading-relaxed">{run.message}</p>
            {(run.error_type || run.error) && (
              <p className="mt-2 break-words font-mono text-xs text-rose-200">{run.error_type ? `${run.error_type}: ` : ''}{run.error}</p>
            )}
          </div>
        )}
      </section>

      {run && (
        <>
          <div className="grid gap-4 xl:grid-cols-2">
            <section className="rounded-xl border border-slate-800 bg-[#091321] p-4">
              <SectionTitle icon={<Cpu className="h-4 w-4 text-cyan-400" />} title="QPU RESULT" />
              <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-3">
                <Metric label="Backend" value={run.backend ?? 'Not available'} tone="text-cyan-300" />
                <Metric label="IBM job ID" value={run.job_id ?? 'Not available'} />
                <Metric label="Execution method" value={run.execution_method} tone="text-cyan-300" />
                <Metric label="Telemetry source" value={run.source ? `${run.source} / ${run.data_origin ?? 'unknown origin'}` : 'Not available'} />
                <Metric label="Requested shots" value={run.requested_shots ?? 'Not available'} />
                <Metric label="Retrieved shots" value={run.result_retrieved ? run.shots ?? 'Not available' : 'Not retrieved'} />
                <Metric label="Submitted" value={run.submitted_at ?? 'Not available'} />
                <Metric label="Completed" value={run.completed_at ?? 'Not available'} />
                <Metric label="Network actions" value={run.execution_performed ? 'Executed' : 'None'} tone="text-emerald-300" />
              </div>
            </section>

            <section className="rounded-xl border border-slate-800 bg-[#091321] p-4">
              <SectionTitle icon={<Activity className="h-4 w-4 text-cyan-400" />} title="QUBO / OPTIMIZATION" />
              <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-3">
                <Metric label="Eligible candidates" value={run.eligible_candidate_count ?? 'Not available'} />
                <Metric label="QUBO variables" value={run.qubo_variables ?? 'Not available'} />
                <Metric label="QUBO variable order" value={run.qubo_variable_names?.join(', ') ?? 'Not available'} />
                <Metric label="Maximum actions" value={run.max_actions ?? 'Not available'} />
                <Metric label="Selected actions" value={run.selected_action_count ?? 'Not available'} />
                <Metric label="Validated recommendations" value={recommendations.length} />
                <Metric label="Validated estimated savings" value={run.total_estimated_power_saving_w != null ? `${run.total_estimated_power_saving_w.toFixed(1)} W` : 'Not available'} tone="text-emerald-300" />
                <Metric label="QUBO feasibility" value={selectedSolution ? (selectedSolution.feasible ? 'FEASIBLE' : 'INFEASIBLE') : 'Not available'} tone={selectedSolution?.feasible ? 'text-emerald-300' : 'text-slate-300'} />
                <Metric label="Transpiled circuit wires" value={run.num_qubits ?? 'Not available'} />
                <Metric label="Transpiled circuit depth" value={run.circuit_depth ?? 'Not available'} />
                <Metric label="QAOA β / γ" value={run.qaoa_beta != null && run.qaoa_gamma != null ? `${run.qaoa_beta.toFixed(3)} / ${run.qaoa_gamma.toFixed(3)}` : 'Not available'} />
              </div>
              {selectedSolution && (
                <p className="mt-3 break-all rounded border border-slate-800 bg-[#050b14] px-3 py-2 font-mono text-[10px] text-slate-400">
                  Measured: {selectedSolution.raw_bitstring} · variables: {selectedSolution.variable_bitstring}
                </p>
              )}
              {run.metadata_available === false && (
                <div className="mt-3 rounded border border-amber-700/50 bg-amber-950/20 px-3 py-2 text-xs text-amber-200">
                  Candidate/QUBO metadata was not persisted for this job. Measurements cannot be mapped to devices, so no selected-device or savings claims are available.
                </div>
              )}
              {!!run.measurement_counts && (
                <details className="mt-3 rounded border border-slate-800 bg-[#050b14] px-3 py-2">
                  <summary className="cursor-pointer text-[10px] font-mono text-slate-400">
                    Retrieved measurement counts · {Object.keys(run.measurement_counts).length} bitstrings (not decoded)
                  </summary>
                  <div className="mt-2 max-h-36 overflow-auto space-y-1 font-mono text-[10px] text-slate-400">
                    {Object.entries(run.measurement_counts).map(([bits, count]) => (
                      <p key={bits}>{bits}: {count}</p>
                    ))}
                  </div>
                </details>
              )}
            </section>
          </div>

          <section className="rounded-xl border border-slate-800 bg-[#091321] p-4">
            <SectionTitle icon={<Activity className="h-4 w-4 text-cyan-400" />} title={`SELECTED DEVICES · ${recommendations.length} VALIDATED`} />
            <div className="mt-3 overflow-x-auto rounded-md border border-slate-800">
              <table className="w-full min-w-[650px] border-collapse text-left text-xs">
                <thead className="bg-[#0d1a2a] text-[10px] uppercase tracking-wider text-slate-400">
                  <tr>
                    <th scope="col" className="px-3 py-2.5">Device ID</th>
                    <th scope="col" className="px-3 py-2.5">Type</th>
                    <th scope="col" className="px-3 py-2.5">Proposed action</th>
                    <th scope="col" className="px-3 py-2.5 text-right">Traffic</th>
                    <th scope="col" className="px-3 py-2.5 text-right">Est. saving</th>
                    <th scope="col" className="px-3 py-2.5">Validation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {recommendations.length ? recommendations.map((item) => (
                    <tr key={item.device_id} className="text-slate-300 hover:bg-cyan-950/15">
                      <td className="px-3 py-2.5 font-mono text-cyan-300">{item.device_id}</td>
                      <td className="px-3 py-2.5">{item.device_type}</td>
                      <td className="px-3 py-2.5">{item.action}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums">{item.traffic}%</td>
                      <td className="px-3 py-2.5 text-right font-mono text-emerald-300 tabular-nums">{item.estimated_power_saving_w.toFixed(1)} W</td>
                      <td className="px-3 py-2.5 text-emerald-300">{item.validation_status}</td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={6} className="px-3 py-7 text-center text-slate-500">
                        {run.metadata_available === false
                          ? 'No device mapping is available for this IBM result.'
                          : 'No validated recommendations are available for this run.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {!!run.rejections?.length && (
              <div className="mt-3 space-y-1 rounded-md border border-rose-900/50 bg-rose-950/20 p-3 text-xs text-rose-200">
                {run.rejections.map((item, index) => (
                  <p key={`${item.device_id ?? 'rejected'}-${index}`}>
                    <span className="font-mono">{item.device_id ?? 'Candidate'}:</span> {item.reason}
                  </p>
                ))}
              </div>
            )}
          </section>

          {validation && (
            <section className={`rounded-xl border p-4 ${
              validation.all_actions_approved
                ? 'border-emerald-900/70 bg-[#081711]'
                : 'border-rose-900/70 bg-[#190d14]'
            }`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <SectionTitle icon={<ShieldCheck className="h-4 w-4 text-cyan-400" />} title="DIGITAL TWIN & POLICY VALIDATION" />
                <span className={`font-mono text-xs font-bold ${validation.all_actions_approved ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {validation.status}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                <Metric label="Proposed actions" value={validation.action_count} />
                <Metric label="Approved actions" value={validation.approved_count} />
                <Metric label="Validated savings" value={`${validation.total_power_saving_w.toFixed(1)} W`} tone="text-emerald-300" />
                <Metric label="Execution performed" value={run.execution_performed ? 'YES' : 'NO'} tone="text-emerald-300" />
              </div>
              {!!validation.affected_links.length && (
                <p className="mt-3 text-xs text-slate-300">
                  Affected links: {validation.affected_links.map((link) =>
                    `${link.source} → ${link.target} (${link.protection_utilization_pct}%)`
                  ).join(' · ')}
                </p>
              )}
              <div className="mt-3 space-y-1">
                {validation.actions.map((action, index) => (
                  <p key={`${action.device_id}-${index}`} className={`text-xs ${action.result === 'APPROVED' ? 'text-emerald-200' : 'text-rose-200'}`}>
                    {action.device_id} · {action.result} · {action.reason}
                  </p>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <section className="rounded-xl border border-slate-800 bg-[#091321] p-4">
        <SectionTitle icon={<Activity className="h-4 w-4 text-cyan-400" />} title="QUANTUM SAFETY PIPELINE" />
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {[
            'Telemetry',
            'Candidate Selection',
            'QUBO',
            'QAOA',
            'IBM Quantum QPU',
            'Device Selection',
            'Digital Twin',
            'Policy Validation',
            'Execute / Reject'
          ].map((stage, index) => {
            const isCurrent = index === pipelineCurrentIndex;
            const isComplete = run?.metadata_available !== false && pipelineCurrentIndex > index;
            const isFailed = isCurrent && terminalFailure;
            const color = isFailed
              ? 'border-rose-700 bg-rose-950/40 text-rose-200'
              : isCurrent && isPendingRun
                ? 'border-amber-600 bg-amber-950/40 text-amber-200'
                : isComplete || (isCurrent && run?.status === 'completed')
                  ? 'border-emerald-700 bg-emerald-950/30 text-emerald-200'
                  : isCurrent
                    ? 'border-cyan-600 bg-cyan-950/40 text-cyan-200'
                    : 'border-slate-800 bg-[#050b14] text-slate-500';
            return (
              <React.Fragment key={stage}>
                <span className={`rounded border px-2 py-1.5 text-[10px] font-mono ${color}`}>{stage}</span>
                {index < 8 && <span aria-hidden="true" className="text-[10px] text-slate-600">→</span>}
              </React.Fragment>
            );
          })}
        </div>
        <p className="mt-3 text-[11px] text-slate-500">
          {run?.metadata_available === false
            ? 'IBM job status was retrieved, but the missing run metadata prevents candidate, Digital Twin, and policy stages from being reconstructed.'
            : 'The QPU returns a proposal only. Final recommendations pass through the Digital Twin and Policy Engine; no network action is executed.'}
        </p>
        {isHistoricalCsv && (
          <p className="mt-1 text-[11px] text-amber-300">
            Current source is a historical Nokia CSV; the QPU optimizer will reject it if it does not meet the live-observation eligibility rules.
          </p>
        )}
      </section>
    </div>
  );
}
