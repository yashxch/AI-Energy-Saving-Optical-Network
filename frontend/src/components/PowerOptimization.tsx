'use client';

import React, { useState } from 'react';
import { Sparkles, CheckCircle2, XCircle, ShieldAlert, Zap, ArrowRight, Play, Info } from 'lucide-react';
import { Recommendation } from '../lib/types';
import { executeAction } from '../lib/api';

interface PowerOptimizationProps {
  recommendations: Recommendation[];
  onActionExecuted: () => void;
}

export const PowerOptimization: React.FC<PowerOptimizationProps> = ({ recommendations, onActionExecuted }) => {
  const [executingId, setExecutingId] = useState<string | null>(null);
  const [expandedRecId, setExpandedRecId] = useState<string | null>(null);
  const [executionMessage, setExecutionMessage] = useState<{ text: string; isError: boolean } | null>(null);

  const handleExecute = async (recId: string) => {
    setExecutingId(recId);
    setExecutionMessage(null);
    const res = await executeAction(recId);
    setExecutingId(null);

    if (res && res.status === 'success') {
      setExecutionMessage({ text: res.message, isError: false });
      onActionExecuted();
    } else {
      setExecutionMessage({
        text: res?.message || "Execution blocked by policy engine or recommendation expired.",
        isError: true
      });
    }
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-white/10 relative">
      
      {/* Header */}
      <div className="flex items-center justify-between mb-4 border-b border-white/10 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-purple-500/10 border border-purple-500/30 rounded-xl text-purple-400">
            <Sparkles className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white tracking-wide flex items-center gap-2">
              LLM Power Optimization Engine
              <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-purple-950/80 text-purple-300 border border-purple-500/30 rounded-md">
                Policy Validated
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Autonomous reasoning engine evaluating optical parameters before executing power mode changes
            </p>
          </div>
        </div>

        <div className="text-xs font-mono text-slate-400">
          Active Recommendations: <span className="text-cyan-400 font-bold">{recommendations.length}</span>
        </div>
      </div>

      {executionMessage && (
        <div className={`mb-4 p-3 rounded-xl border text-xs font-mono flex items-center justify-between ${
          executionMessage.isError
            ? 'bg-rose-950/60 border-rose-500/40 text-rose-300'
            : 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
        }`}>
          <span>{executionMessage.text}</span>
          <button onClick={() => setExecutionMessage(null)} className="text-slate-400 hover:text-white">✕</button>
        </div>
      )}

      {/* Recommendations Feed */}
      <div className="space-y-4 max-h-[460px] overflow-y-auto pr-1">
        {recommendations.map((rec) => {
          const isPassed = rec.validation_passed;
          const isExpanded = expandedRecId === rec.id;

          return (
            <div
              key={rec.id}
              className={`p-4 rounded-xl border transition-all duration-200 ${
                isPassed
                  ? 'bg-[#0a1120] border-emerald-500/30 hover:border-emerald-500/60'
                  : 'bg-[#180d12] border-rose-500/30 hover:border-rose-500/60'
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                
                {/* Device & Action Title */}
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg border text-xs font-mono ${
                    isPassed ? 'bg-emerald-950/80 border-emerald-500/40 text-emerald-400' : 'bg-rose-950/80 border-rose-500/40 text-rose-400'
                  }`}>
                    {isPassed ? <CheckCircle2 className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-cyan-300 font-bold text-sm">{rec.device_id}</span>
                      <span className="text-xs text-slate-400">({rec.device_name})</span>
                    </div>
                    <div className="text-xs font-semibold text-white mt-0.5">
                      Proposed Action: <span className="text-purple-300">{rec.action_type}</span>
                    </div>
                  </div>
                </div>

                {/* Validation Status Badge & Action */}
                <div className="flex items-center gap-3">
                  {/* Status Badge */}
                  <div className="text-right">
                    <span className={`px-2.5 py-1 text-xs font-mono font-bold rounded-lg border inline-flex items-center gap-1.5 ${
                      isPassed
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-500/40 glow-text-emerald'
                        : 'bg-rose-950 text-rose-300 border-rose-500/40'
                    }`}>
                      {isPassed ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5" /> APPROVED
                        </>
                      ) : (
                        <>
                          <ShieldAlert className="w-3.5 h-3.5" /> RECOMMENDATION REJECTED
                        </>
                      )}
                    </span>
                    <div className="text-[10px] font-mono text-emerald-400 mt-1">
                      Est. Power Savings: <span className="font-bold">+{rec.estimated_power_savings_w} W</span>
                    </div>
                  </div>

                  {/* Trigger Button */}
                  {isPassed ? (
                    <button
                      onClick={() => handleExecute(rec.id)}
                      disabled={executingId === rec.id}
                      className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-mono font-bold transition flex items-center gap-1.5 shadow-lg shadow-emerald-950/50"
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      {executingId === rec.id ? 'Executing...' : 'Execute'}
                    </button>
                  ) : (
                    <button
                      onClick={() => setExpandedRecId(isExpanded ? null : rec.id)}
                      className="px-3 py-2 bg-rose-950/80 hover:bg-rose-900 border border-rose-500/40 text-rose-300 rounded-lg text-xs font-mono transition flex items-center gap-1"
                    >
                      <Info className="w-3.5 h-3.5" /> Why Rejected?
                    </button>
                  )}
                </div>

              </div>

              {/* Chain-of-Thought Reasoning Box */}
              <div className="mt-3 p-3 rounded-lg bg-slate-900/80 border border-white/5 text-xs text-slate-300 font-sans leading-relaxed">
                <div className="text-[10px] font-mono uppercase text-purple-400 font-semibold mb-1 flex items-center gap-1">
                  <Sparkles className="w-3 h-3" /> LLM Chain-of-Thought Rationale
                </div>
                {rec.reasoning}
              </div>

              {/* Rejection Details & Policy Checks Drawer */}
              {(!isPassed || isExpanded) && rec.rejection_reason && (
                <div className="mt-3 p-3 rounded-lg bg-rose-950/40 border border-rose-500/30 text-xs font-mono">
                  <div className="text-rose-400 font-bold mb-1 flex items-center gap-1">
                    <ShieldAlert className="w-4 h-4" /> Optical Constraint Policy Violation:
                  </div>
                  <p className="text-rose-200 text-xs leading-normal mb-2">{rec.rejection_reason}</p>

                  <div className="text-[10px] uppercase text-slate-400 mb-1">Hardware Policy Checks Matrix:</div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[11px]">
                    {rec.policy_checks.map((chk, idx) => (
                      <div
                        key={idx}
                        className={`p-1.5 rounded border flex items-center justify-between ${
                          chk.passed ? 'bg-emerald-950/30 border-emerald-500/20 text-emerald-300' : 'bg-rose-950/60 border-rose-500/40 text-rose-300 font-semibold'
                        }`}
                      >
                        <div>
                          <div>{chk.name}</div>
                          <div className="text-[9px] text-slate-400">{chk.measured}</div>
                        </div>
                        <span className={`text-[10px] font-bold ${chk.passed ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {chk.passed ? 'PASS' : 'FAIL'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>
          );
        })}
      </div>

    </div>
  );
};
