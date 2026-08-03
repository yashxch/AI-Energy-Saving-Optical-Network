'use client';

import React, { useState } from 'react';
import { Network, Server, Cpu, Radio, Shield, Zap } from 'lucide-react';
import { Device } from '../lib/types';

interface NetworkTopologyProps {
  devices: Device[];
  onSelectNode: (nodeName: string) => void;
}

interface NodeCoord {
  name: string;
  x: number;
  y: number;
  region: string;
}

const NODES: NodeCoord[] = [
  { name: 'BOS', x: 740, y: 120, region: 'East Coast' },
  { name: 'NYC', x: 690, y: 180, region: 'East Hub' },
  { name: 'WDC', x: 630, y: 240, region: 'Capital' },
  { name: 'ATL', x: 570, y: 340, region: 'Southeast' },
  { name: 'DAL', x: 400, y: 350, region: 'Central' },
  { name: 'CHI', x: 500, y: 170, region: 'Midwest Hub' },
  { name: 'SFO', x: 120, y: 220, region: 'West Coast' },
  { name: 'LAX', x: 170, y: 330, region: 'Pacific Hub' },
];

const LINKS = [
  { from: 'BOS', to: 'NYC' },
  { from: 'NYC', to: 'WDC' },
  { from: 'WDC', to: 'ATL' },
  { from: 'ATL', to: 'DAL' },
  { from: 'DAL', to: 'LAX' },
  { from: 'LAX', to: 'SFO' },
  { from: 'SFO', to: 'CHI' },
  { from: 'CHI', to: 'NYC' },
  { from: 'CHI', to: 'DAL' },
  { from: 'WDC', to: 'CHI' },
  { from: 'SFO', to: 'DAL' },
];

export const NetworkTopology: React.FC<NetworkTopologyProps> = ({ devices, onSelectNode }) => {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string>('NYC');

  const getNodeDevices = (nodeName: string) => {
    return devices.filter(d => d.node_location === nodeName);
  };

  const selectedDevs = getNodeDevices(selectedNode);
  const activeCount = selectedDevs.filter(d => d.power_mode === 'Normal').length;
  const ecoCount = selectedDevs.filter(d => d.power_mode === 'Eco' || d.power_mode === 'Low Gain').length;
  const sleepCount = selectedDevs.filter(d => d.power_mode === 'Sleep').length;

  return (
    <div className="glass-card rounded-2xl p-5 border border-white/10 relative overflow-hidden">
      
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Network className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide">Optical Mesh Topology</h2>
          <span className="text-xs text-slate-400 font-mono pl-2 border-l border-white/10">
            Nokia 1830 PSS DWDM Network (8 Regional Nodes)
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#00f0ff]" />
            <span className="text-slate-300">Active Path</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-400 shadow-[0_0_8px_#a855f7]" />
            <span className="text-slate-300">Eco Mode Link</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 shadow-[0_0_8px_#f59e0b]" />
            <span className="text-slate-300">High Load Span</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        
        {/* SVG Mesh Map */}
        <div className="lg:col-span-3 relative bg-[#060910] rounded-xl border border-white/5 p-4 min-h-[380px] flex items-center justify-center">
          <svg viewBox="0 0 850 450" className="w-full h-full max-h-[420px]">
            
            <defs>
              <linearGradient id="linkGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#00f0ff" stopOpacity="0.8" />
                <stop offset="50%" stopColor="#a855f7" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#00f0ff" stopOpacity="0.8" />
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>

            {/* Fiber Optic Links */}
            {LINKS.map((link, idx) => {
              const n1 = NODES.find(n => n.name === link.from)!;
              const n2 = NODES.find(n => n.name === link.to)!;
              const isSelected = selectedNode === link.from || selectedNode === link.to;

              return (
                <g key={idx}>
                  {/* Outer glow line */}
                  <line
                    x1={n1.x}
                    y1={n1.y}
                    x2={n2.x}
                    y2={n2.y}
                    stroke={isSelected ? '#00f0ff' : 'rgba(255,255,255,0.12)'}
                    strokeWidth={isSelected ? '3' : '1.5'}
                    strokeDasharray={isSelected ? 'none' : '4 4'}
                    filter={isSelected ? 'url(#glow)' : undefined}
                  />
                  
                  {/* Animated fiber optical pulse */}
                  {isSelected && (
                    <circle r="4" fill="#00f0ff" filter="url(#glow)">
                      <animateMotion
                        path={`M ${n1.x} ${n1.y} L ${n2.x} ${n2.y}`}
                        dur={`${2.5 + (idx % 3)}s`}
                        repeatCount="indefinite"
                      />
                    </circle>
                  )}
                </g>
              );
            })}

            {/* Optical Nodes */}
            {NODES.map((node) => {
              const nodeDevs = getNodeDevices(node.name);
              const isSelected = selectedNode === node.name;
              const isHovered = hoveredNode === node.name;
              const hasWarning = nodeDevs.some(d => d.health !== 'Normal');

              return (
                <g
                  key={node.name}
                  transform={`translate(${node.x}, ${node.y})`}
                  className="cursor-pointer transition-all duration-300"
                  onClick={() => {
                    setSelectedNode(node.name);
                    onSelectNode(node.name);
                  }}
                  onMouseEnter={() => setHoveredNode(node.name)}
                  onMouseLeave={() => setHoveredNode(null)}
                >
                  {/* Pulse ring for selected */}
                  {isSelected && (
                    <circle
                      r="26"
                      className="animate-ping fill-none stroke-cyan-400 stroke-1 opacity-75"
                    />
                  )}

                  {/* Outer Node Ring */}
                  <circle
                    r="20"
                    fill={hasWarning ? 'rgba(244, 63, 94, 0.2)' : isSelected ? 'rgba(0, 240, 255, 0.2)' : 'rgba(15, 23, 42, 0.8)'}
                    stroke={hasWarning ? '#f43f5e' : isSelected ? '#00f0ff' : '#475569'}
                    strokeWidth={isSelected || isHovered ? '2.5' : '1.5'}
                    filter={isSelected ? 'url(#glow)' : undefined}
                  />

                  {/* Center Node Icon */}
                  <circle
                    r="8"
                    fill={hasWarning ? '#f43f5e' : isSelected ? '#00f0ff' : '#0ea5e9'}
                  />

                  {/* Node Label */}
                  <text
                    y="36"
                    textAnchor="middle"
                    fill={isSelected ? '#00f0ff' : '#e2e8f0'}
                    className="text-[11px] font-bold font-mono tracking-widest pointer-events-none"
                  >
                    {node.name}
                  </text>
                  <text
                    y="48"
                    textAnchor="middle"
                    fill="#64748b"
                    className="text-[9px] font-sans pointer-events-none"
                  >
                    {nodeDevs.length} Devs
                  </text>
                </g>
              );
            })}

          </svg>

          {/* Overlay Helper */}
          <div className="absolute bottom-3 left-3 text-[10px] font-mono text-slate-400 bg-slate-900/80 px-2.5 py-1 rounded border border-white/10">
            Click node to view transponders & power state
          </div>
        </div>

        {/* Selected Node Details Side Panel */}
        <div className="bg-[#0b101d] rounded-xl border border-white/10 p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-3">
              <div>
                <span className="text-[10px] font-mono uppercase text-slate-400">Node Location</span>
                <h3 className="text-lg font-bold text-white tracking-wide">{selectedNode} Exchange</h3>
              </div>
              <span className="px-2 py-0.5 text-xs font-mono bg-cyan-950 text-cyan-400 border border-cyan-500/30 rounded">
                100GbE / 800G
              </span>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Total Optical Devices:</span>
                <span className="font-mono font-bold text-white">{selectedDevs.length}</span>
              </div>
              
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Power Mode Distribution</span>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden flex">
                  <div style={{ width: `${(activeCount / (selectedDevs.length || 1)) * 100}%` }} className="bg-cyan-400 h-full" title="Normal Power Mode" />
                  <div style={{ width: `${(ecoCount / (selectedDevs.length || 1)) * 100}%` }} className="bg-purple-400 h-full" title="Eco / Low Gain Mode" />
                  <div style={{ width: `${(sleepCount / (selectedDevs.length || 1)) * 100}%` }} className="bg-emerald-400 h-full" title="Sleep Mode" />
                </div>
                <div className="flex justify-between text-[10px] font-mono text-slate-400 pt-1">
                  <span className="text-cyan-400">Normal: {activeCount}</span>
                  <span className="text-purple-400">Eco: {ecoCount}</span>
                  <span className="text-emerald-400">Sleep: {sleepCount}</span>
                </div>
              </div>

              {/* Sample Hardware List for Selected Node */}
              <div className="mt-4 pt-3 border-t border-white/10">
                <div className="text-[10px] font-mono text-slate-400 uppercase mb-2">Hardware Modules</div>
                <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
                  {selectedDevs.map(dev => (
                    <div key={dev.id} className="p-2 rounded bg-slate-900/60 border border-white/5 flex items-center justify-between text-xs">
                      <div>
                        <div className="font-mono text-cyan-300 font-semibold">{dev.id}</div>
                        <div className="text-[10px] text-slate-400">{dev.type}</div>
                      </div>
                      <div className="text-right">
                        <span className={`px-1.5 py-0.5 text-[9px] font-mono rounded ${
                          dev.power_mode === 'Normal' ? 'bg-cyan-950 text-cyan-400 border border-cyan-500/30' :
                          dev.power_mode === 'Sleep' ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30' :
                          'bg-purple-950 text-purple-400 border border-purple-500/30'
                        }`}>
                          {dev.power_mode}
                        </span>
                        <div className="text-[10px] font-mono text-slate-400 mt-1">{dev.telemetry.power_consumption_w}W</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          </div>

          <button
            onClick={() => onSelectNode(selectedNode)}
            className="w-full mt-4 py-2 bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-500/40 text-cyan-300 rounded-lg text-xs font-mono font-semibold transition"
          >
            Filter Telemetry Matrix ({selectedNode})
          </button>

        </div>

      </div>

    </div>
  );
};
