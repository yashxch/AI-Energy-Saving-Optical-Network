'use client';

import React, { useState, useEffect } from 'react';
import { Network, RotateCw, Compass, Layers, Zap } from 'lucide-react';
import { Device } from '../lib/types';
import { NokiaNetworkTopology } from './NokiaNetworkTopology';

interface NetworkTopologyProps {
  devices: Device[];
  onSelectNode: (nodeName: string) => void;
  telemetrySource?: 'simulator' | 'nokia' | null;
}

interface NodeSpatial {
  name: string;
  x: number;
  y: number;
  z: number;
  radius: number;
  azimuth_deg: number;
  orientation_deg: number;
}

interface TopologyLink {
  src: string;
  dst: string;
  distance_km: number;
  bearing_deg: number;
  active: boolean;
}

interface TopologyState {
  pattern: string;
  global_rotation_deg: number;
  total_nodes: number;
  total_links: number;
  active_links: number;
  nodes: Record<string, NodeSpatial>;
  links: TopologyLink[];
}

const DEFAULT_NODES = [
  { name: 'BOS', x: 740, y: 120 },
  { name: 'NYC', x: 690, y: 180 },
  { name: 'WDC', x: 630, y: 240 },
  { name: 'ATL', x: 570, y: 340 },
  { name: 'DAL', x: 400, y: 350 },
  { name: 'CHI', x: 500, y: 170 },
  { name: 'SFO', x: 120, y: 220 },
  { name: 'LAX', x: 170, y: 330 },
];

const SimulatorNetworkTopology: React.FC<NetworkTopologyProps> = ({ devices, onSelectNode }) => {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string>('NYC');
  const [topology, setTopology] = useState<TopologyState | null>(null);
  const [pattern, setPattern] = useState<string>('hybrid');
  const [rotationDeg, setRotationDeg] = useState<number>(0);
  const [isRotating, setIsRotating] = useState<boolean>(false);

  const fetchTopology = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/topology');
      if (res.ok) {
        const data = await res.json();
        setTopology(data);
        setPattern(data.pattern);
        setRotationDeg(data.global_rotation_deg);
      }
    } catch (e) {
      console.log("Backend offline or topology loading...");
    }
  };

  useEffect(() => {
    fetchTopology();
    const interval = setInterval(fetchTopology, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSetPattern = async (newPattern: string) => {
    setPattern(newPattern);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/topology/pattern', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pattern: newPattern })
      });
      if (res.ok) {
        const data = await res.json();
        setTopology(data.topology);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRotate = async (deltaDeg: number) => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/topology/rotate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delta_deg: deltaDeg })
      });
      if (res.ok) {
        const data = await res.json();
        setTopology(data.topology);
        setRotationDeg(data.topology.global_rotation_deg);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const getNodeDevices = (nodeName: string) => {
    return devices.filter(d => d.node_location === nodeName);
  };

  const selectedDevs = getNodeDevices(selectedNode);
  const activeCount = selectedDevs.filter(d => d.power_mode === 'Normal').length;
  const ecoCount = selectedDevs.filter(d => d.power_mode === 'Eco' || d.power_mode === 'Low Gain').length;
  const sleepCount = selectedDevs.filter(d => d.power_mode === 'Sleep').length;

  // Convert normalized/backend coordinates to SVG layout coordinates
  const getSvgCoords = (nodeName: string) => {
    if (topology && topology.nodes[nodeName]) {
      const node = topology.nodes[nodeName];
      const cx = 425;
      const cy = 210;
      // Map x, y scaled to fit SVG canvas
      const svgX = cx + (node.x * 0.55);
      const svgY = cy + (node.y * 0.35);
      return { x: svgX, y: svgY, nodeSpatial: node };
    }
    const def = DEFAULT_NODES.find(n => n.name === nodeName) || { x: 400, y: 200 };
    return { x: def.x, y: def.y, nodeSpatial: null };
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-white/10 relative overflow-hidden">
      
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-2">
          <Network className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base font-bold text-white tracking-wide">Multi-Angular Node Topology</h2>
          <span className="text-xs text-cyan-400/90 font-mono px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/30">
            360° Rotational Engine
          </span>
        </div>

        {/* Pattern & Rotational Controls */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-white/10 text-xs font-mono">
            <Layers className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-slate-400">Pattern:</span>
            <select
              value={pattern}
              onChange={(e) => handleSetPattern(e.target.value)}
              className="bg-slate-800 text-cyan-300 font-bold border border-cyan-500/40 rounded px-2 py-0.5 text-xs focus:outline-none"
            >
              <option value="hybrid">Hybrid</option>
              <option value="ring">Ring</option>
              <option value="full_mesh">Full Mesh</option>
              <option value="partial_mesh">Partial Mesh</option>
              <option value="star">Star Hub</option>
              <option value="tree">Tree Branching</option>
              <option value="directional_sector">Directional Sector</option>
              <option value="rotational_sweep">Rotational Sweep</option>
            </select>
          </div>

          <div className="flex items-center gap-2 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-white/10 text-xs font-mono">
            <Compass className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-300">{rotationDeg.toFixed(0)}°</span>
            <button
              onClick={() => handleRotate(15)}
              className="px-2 py-1 bg-cyan-600/30 hover:bg-cyan-600/50 text-cyan-300 rounded border border-cyan-500/40 transition flex items-center gap-1"
            >
              <RotateCw className="w-3 h-3" /> +15°
            </button>
            <button
              onClick={() => handleRotate(45)}
              className="px-2 py-1 bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 rounded border border-purple-500/40 transition"
            >
              +45°
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        
        {/* SVG Multi-Angular Interactive Canvas */}
        <div className="lg:col-span-3 relative bg-[#060910] rounded-xl border border-white/5 p-4 min-h-[380px] flex items-center justify-center overflow-hidden">
          <svg viewBox="0 0 850 450" className="w-full h-full max-h-[420px]">
            
            <defs>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>

            {/* Angular Compass Grid Background */}
            <circle cx="425" cy="210" r="180" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="1" strokeDasharray="4 4" />
            <circle cx="425" cy="210" r="120" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="1" strokeDasharray="4 4" />
            <line x1="425" y1="20" x2="425" y2="400" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />
            <line x1="150" y1="210" x2="700" y2="210" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />

            {/* Dynamic Multi-Angular Links */}
            {topology?.links.map((link, idx) => {
              const srcCoord = getSvgCoords(link.src);
              const dstCoord = getSvgCoords(link.dst);
              const isSelected = selectedNode === link.src || selectedNode === link.dst;

              return (
                <g key={`${link.src}-${link.dst}-${idx}`}>
                  <line
                    x1={srcCoord.x}
                    y1={srcCoord.y}
                    x2={dstCoord.x}
                    y2={dstCoord.y}
                    stroke={link.active ? (isSelected ? '#00f0ff' : 'rgba(0, 240, 255, 0.35)') : 'rgba(255, 255, 255, 0.08)'}
                    strokeWidth={isSelected ? '2.5' : '1.5'}
                    strokeDasharray={link.active ? 'none' : '3 3'}
                    filter={isSelected ? 'url(#glow)' : undefined}
                  />
                  {link.active && isSelected && (
                    <circle r="3.5" fill="#00f0ff" filter="url(#glow)">
                      <animateMotion
                        path={`M ${srcCoord.x} ${srcCoord.y} L ${dstCoord.x} ${dstCoord.y}`}
                        dur={`${2.0 + (idx % 3)}s`}
                        repeatCount="indefinite"
                      />
                    </circle>
                  )}
                </g>
              );
            })}

            {/* Multi-Angular Node Visualizer */}
            {DEFAULT_NODES.map((defNode) => {
              const { x, y, nodeSpatial } = getSvgCoords(defNode.name);
              const nodeDevs = getNodeDevices(defNode.name);
              const isSelected = selectedNode === defNode.name;
              const isHovered = hoveredNode === defNode.name;
              const hasWarning = nodeDevs.some(d => d.health !== 'Normal');

              return (
                <g
                  key={defNode.name}
                  transform={`translate(${x}, ${y})`}
                  className="cursor-pointer transition-all duration-300"
                  onClick={() => {
                    setSelectedNode(defNode.name);
                    onSelectNode(defNode.name);
                  }}
                  onMouseEnter={() => setHoveredNode(defNode.name)}
                  onMouseLeave={() => setHoveredNode(null)}
                >
                  {isSelected && (
                    <circle r="26" className="animate-ping fill-none stroke-cyan-400 stroke-1 opacity-75" />
                  )}

                  {/* Angular Bearing Sector Indicator */}
                  {nodeSpatial && (
                    <line
                      x1="0"
                      y1="0"
                      x2={22 * mathCos(nodeSpatial.orientation_deg)}
                      y2={22 * mathSin(nodeSpatial.orientation_deg)}
                      stroke="#a855f7"
                      strokeWidth="2"
                    />
                  )}

                  <circle
                    r="18"
                    fill={hasWarning ? 'rgba(244, 63, 94, 0.2)' : isSelected ? 'rgba(0, 240, 255, 0.2)' : 'rgba(15, 23, 42, 0.8)'}
                    stroke={hasWarning ? '#f43f5e' : isSelected ? '#00f0ff' : '#475569'}
                    strokeWidth={isSelected || isHovered ? '2.5' : '1.5'}
                    filter={isSelected ? 'url(#glow)' : undefined}
                  />

                  <circle
                    r="7"
                    fill={hasWarning ? '#f43f5e' : isSelected ? '#00f0ff' : '#0ea5e9'}
                  />

                  <text
                    y="32"
                    textAnchor="middle"
                    fill={isSelected ? '#00f0ff' : '#e2e8f0'}
                    className="text-[11px] font-bold font-mono tracking-widest pointer-events-none"
                  >
                    {defNode.name}
                  </text>
                  <text
                    y="44"
                    textAnchor="middle"
                    fill="#64748b"
                    className="text-[9px] font-sans pointer-events-none"
                  >
                    {nodeSpatial ? `${nodeSpatial.azimuth_deg.toFixed(0)}°` : `${nodeDevs.length} Devs`}
                  </text>
                </g>
              );
            })}

          </svg>

          <div className="absolute bottom-3 left-3 text-[10px] font-mono text-slate-400 bg-slate-900/80 px-2.5 py-1 rounded border border-white/10 flex items-center gap-2">
            <span>Pattern: <strong className="text-cyan-300 font-bold uppercase">{pattern}</strong></span>
            <span className="text-slate-600">|</span>
            <span>Rotation: <strong className="text-purple-300 font-bold">{rotationDeg.toFixed(1)}°</strong></span>
          </div>
        </div>

        {/* Node Spatial & Telemetry Details Panel */}
        <div className="bg-[#0b101d] rounded-xl border border-white/10 p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-3">
              <div>
                <span className="text-[10px] font-mono uppercase text-slate-400">Selected Node</span>
                <h3 className="text-lg font-bold text-white tracking-wide">{selectedNode} Exchange</h3>
              </div>
              <span className="px-2 py-0.5 text-xs font-mono bg-cyan-950 text-cyan-400 border border-cyan-500/30 rounded">
                Multi-Angular
              </span>
            </div>

            <div className="space-y-3">
              {/* Polar Coordinates Display */}
              {topology?.nodes[selectedNode] && (
                <div className="p-2.5 rounded bg-slate-900/70 border border-purple-500/30 font-mono text-xs space-y-1">
                  <div className="text-[10px] text-purple-400 uppercase font-bold">Polar Angular Vector</div>
                  <div className="flex justify-between text-slate-300">
                    <span>Azimuth ($\theta$):</span>
                    <span className="text-cyan-300 font-bold">{topology.nodes[selectedNode].azimuth_deg}°</span>
                  </div>
                  <div className="flex justify-between text-slate-300">
                    <span>Bearing ($\alpha$):</span>
                    <span className="text-purple-300 font-bold">{topology.nodes[selectedNode].orientation_deg}°</span>
                  </div>
                  <div className="flex justify-between text-slate-300">
                    <span>Spatial Dist ($r$):</span>
                    <span className="text-slate-200">{topology.nodes[selectedNode].radius} km</span>
                  </div>
                </div>
              )}

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

              {/* Hardware List for Selected Node */}
              <div className="mt-3 pt-3 border-t border-white/10">
                <div className="text-[10px] font-mono text-slate-400 uppercase mb-2">Hardware Modules</div>
                <div className="space-y-2 max-h-[140px] overflow-y-auto pr-1">
                  {selectedDevs.map(dev => (
                    <div key={dev.id} className="p-2 rounded bg-slate-900/60 border border-white/5 flex items-center justify-between text-xs">
                      <div>
                        <div className="font-mono text-cyan-300 font-semibold">{dev.id}</div>
                        <div className="text-[10px] text-slate-200">{dev.name}</div>
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
            className="w-full mt-3 py-2 bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-500/40 text-cyan-300 rounded-lg text-xs font-mono font-semibold transition"
          >
            Filter Telemetry Matrix ({selectedNode})
          </button>

        </div>

      </div>

    </div>
  );
};

function mathCos(deg: number): number {
  return Math.cos((deg * Math.PI) / 180);
}

function mathSin(deg: number): number {
  return Math.sin((deg * Math.PI) / 180);
}

export const NetworkTopology: React.FC<NetworkTopologyProps> = (props) => {
  if (props.telemetrySource === 'nokia') {
    return <NokiaNetworkTopology devices={props.devices} onSelectNode={props.onSelectNode} />;
  }
  return <SimulatorNetworkTopology {...props} />;
};
