'use client';

import React, { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, AlertOctagon, Activity, Clock, ShieldAlert } from 'lucide-react';
import { TrafficPrediction, AnomalyItem } from '../lib/types';
import { getPredictions } from '../lib/api';

interface PredictionChartsProps {
  anomalies: AnomalyItem[];
}

export const PredictionCharts: React.FC<PredictionChartsProps> = ({ anomalies }) => {
  const [horizon, setHorizon] = useState<'5m' | '1h' | '24h'>('5m');
  const [predictionData, setPredictionData] = useState<TrafficPrediction | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadPredictions() {
      setLoading(true);
      const res = await getPredictions(horizon);
      setPredictionData(res);
      setLoading(false);
    }
    loadPredictions();
  }, [horizon]);

  const chartData = predictionData?.timestamps.map((t, i) => ({
    time: t,
    Predicted_Gbps: predictionData.predicted_traffic_gbps[i],
    Upper_Bound: predictionData.upper_bound_gbps[i],
    Lower_Bound: predictionData.lower_bound_gbps[i],
  })) || [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      {/* 1. Traffic Prediction Graph (2 cols) */}
      <div className="lg:col-span-2 glass-card rounded-2xl p-5 border border-white/10 flex flex-col justify-between">
        
        <div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-cyan-400" />
                <h2 className="text-base font-bold text-white tracking-wide">LSTM Traffic Prediction Engine</h2>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                AI optical bandwidth forecasting for energy saving planning
              </p>
            </div>

            {/* Horizon Horizon Selector Buttons */}
            <div className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-xl border border-white/10 text-xs font-mono">
              <button
                onClick={() => setHorizon('5m')}
                className={`px-3 py-1 rounded-lg transition ${
                  horizon === '5m' ? 'bg-cyan-500 text-black font-bold shadow-md' : 'text-slate-400 hover:text-white'
                }`}
              >
                Next 5 Min
              </button>
              <button
                onClick={() => setHorizon('1h')}
                className={`px-3 py-1 rounded-lg transition ${
                  horizon === '1h' ? 'bg-cyan-500 text-black font-bold shadow-md' : 'text-slate-400 hover:text-white'
                }`}
              >
                Next 1 Hour
              </button>
              <button
                onClick={() => setHorizon('24h')}
                className={`px-3 py-1 rounded-lg transition ${
                  horizon === '24h' ? 'bg-cyan-500 text-black font-bold shadow-md' : 'text-slate-400 hover:text-white'
                }`}
              >
                Next 24 Hours
              </button>
            </div>

          </div>

          {/* Chart Container */}
          <div className="h-64 w-full pt-2">
            {chartData.length === 0 ? (
              <div className="h-full flex items-center justify-center rounded-xl border border-white/5 bg-slate-950/40 text-xs font-mono text-slate-500">
                {loading ? 'Loading telemetry…' : 'No telemetry data available for the selected source.'}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="predGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00f0ff" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#00f0ff" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="boundGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#a855f7" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#a855f7" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis stroke="#64748b" tick={{ fontSize: 10, fill: '#94a3b8' }} unit=" Gbps" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: 'rgba(0,240,255,0.3)', borderRadius: '8px', fontSize: '12px' }}
                />
                <Area type="monotone" dataKey="Upper_Bound" stroke="#a855f7" fill="url(#boundGrad)" strokeDasharray="3 3" name="Upper Confidence Limit" />
                <Area type="monotone" dataKey="Predicted_Gbps" stroke="#00f0ff" strokeWidth={2.5} fill="url(#predGrad)" name="Predicted Throughput (Gbps)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between text-xs font-mono text-slate-400 border-t border-white/10 pt-3 mt-2">
          <span>Model Horizon: <strong className="text-cyan-300">{horizon.toUpperCase()} Forecast</strong></span>
          <span>Confidence Score: <strong className="text-emerald-400">
            {predictionData ? `${predictionData.confidence_score * 100}%` : '—'}
          </strong></span>
        </div>

      </div>

      {/* 2. Isolation Forest Anomaly Feed (1 col) */}
      <div className="glass-card rounded-2xl p-5 border border-white/10 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between mb-3 border-b border-white/10 pb-3">
            <div className="flex items-center gap-2">
              <AlertOctagon className="w-5 h-5 text-rose-400" />
              <h2 className="text-base font-bold text-white tracking-wide">Isolation Forest Anomalies</h2>
            </div>
            <span className="px-2 py-0.5 text-xs font-mono bg-rose-950/80 text-rose-300 border border-rose-500/30 rounded">
              {anomalies.length} Flagged
            </span>
          </div>

          {/* Anomalies List */}
          <div className="space-y-3 max-h-[250px] overflow-y-auto pr-1">
            {anomalies.length > 0 ? (
              anomalies.map((ano) => (
                <div
                  key={ano.id}
                  className={`p-3 rounded-xl border text-xs font-mono ${
                    ano.severity === 'Critical'
                      ? 'bg-rose-950/50 border-rose-500/40 text-rose-200'
                      : 'bg-amber-950/40 border-amber-500/30 text-amber-200'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-white">{ano.device_name} ({ano.device_id})</span>
                    <span className={`px-1.5 py-0.5 text-[9px] uppercase font-bold rounded ${
                      ano.severity === 'Critical' ? 'bg-rose-600 text-white' : 'bg-amber-600 text-white'
                    }`}>
                      {ano.severity}
                    </span>
                  </div>
                  <div className="text-cyan-300 font-semibold text-[11px] mb-1">{ano.anomaly_type}</div>
                  <p className="text-[10px] text-slate-300 font-sans leading-tight">{ano.details}</p>
                </div>
              ))
            ) : (
              <div className="p-6 text-center text-xs font-mono text-slate-400 bg-slate-900/60 rounded-xl border border-white/5">
                {predictionData
                  ? '✅ No telemetry anomalies detected by Isolation Forest. Network parameters nominal.'
                  : 'No telemetry data available for the selected source.'}
              </div>
            )}
          </div>
        </div>

        <div className="text-[10px] font-mono text-slate-400 border-t border-white/10 pt-3 mt-3">
          Multi-variable Isolation Forest evaluating Temperature, BER, OSNR & Power Draw
        </div>

      </div>

    </div>
  );
};
