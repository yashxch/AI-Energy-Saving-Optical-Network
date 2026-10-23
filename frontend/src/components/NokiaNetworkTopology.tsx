'use client';

import React, { useEffect, useState } from 'react';
import { Network } from 'lucide-react';
import { Device } from '../lib/types';

interface NokiaNetworkTopologyProps {
  devices: Device[];
  onSelectNode: (nodeName: string) => void;
}

interface NokiaTopologyState {
  pattern: string;
  total_nodes: number;
  total_links: number;
  nodes: Record<string, { name: string }>;
  links: Array<{ src: string; dst: string }>;
}

export const NokiaNetworkTopology: React.FC<NokiaNetworkTopologyProps> = ({ devices, onSelectNode }) => {
  const [topology, setTopology] = useState<NokiaTopologyState | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('http://127.0.0.1:8000/api/topology')
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('Unable to load Nokia topology')))
      .then((data: NokiaTopologyState) => {
        if (!cancelled) {
          setTopology(data);
          setSelectedNode(Object.keys(data.nodes)[0] ?? null);
        }
      })
      .catch(() => {
        if (!cancelled) setTopology({ pattern: 'unavailable', total_nodes: 0, total_links: 0, nodes: {}, links: [] });
      });
    return () => { cancelled = true; };
  }, []);

  const nodeDevices = (node: string) => devices.filter((device) => device.node_location === node || device.ne_name === node);

  if (!topology) {
    return <div className="glass-card rounded-2xl p-5 border border-white/10 text-slate-400">Loading Nokia topology...</div>;
  }

  if (topology.total_nodes === 0) {
    return (
      <div className="glass-card rounded-2xl p-5 border border-white/10">
        <h2 className="text-base font-bold text-white flex items-center gap-2"><Network className="w-5 h-5 text-cyan-400" /> Nokia Network Inventory</h2>
        <p className="mt-4 text-sm text-amber-300">Nokia topology data is unavailable. No simulated nodes or links are shown.</p>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-2xl p-5 border border-white/10">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2"><Network className="w-5 h-5 text-cyan-400" /> Nokia Network Inventory</h2>
        <span className="text-xs font-mono text-cyan-300">{topology.pattern}</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {Object.keys(topology.nodes).map((node) => {
          const nodeDevicesList = nodeDevices(node);
          const selected = selectedNode === node;
          return (
            <button
              key={node}
              type="button"
              className={`text-left rounded-lg border p-3 ${selected ? 'border-cyan-400 bg-cyan-950/30' : 'border-white/10 bg-slate-900/50'}`}
              onClick={() => { setSelectedNode(node); onSelectNode(node); }}
            >
              <div className="font-mono font-bold text-cyan-300">{node}</div>
              <div className="text-xs text-slate-400 mt-1">{nodeDevicesList.length} device(s)</div>
              <div className="mt-2 space-y-1">
                {nodeDevicesList.map((device) => (
                  <div key={device.id} className="text-xs text-slate-200">
                    {device.name} <span className="text-slate-500">({device.equipment_name ?? device.card_name ?? device.id})</span>
                  </div>
                ))}
              </div>
            </button>
          );
        })}
      </div>
      <p className="mt-4 text-xs text-slate-500">
        {topology.total_links > 0
          ? `${topology.total_links} verified connection(s) from Nokia endpoint data.`
          : 'Connectivity unavailable in the Nokia payload; no assumed links are displayed.'}
      </p>
    </div>
  );
};
