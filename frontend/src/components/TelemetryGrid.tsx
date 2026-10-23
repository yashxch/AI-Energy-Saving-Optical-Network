'use client';

import React from 'react';
import { Cpu } from 'lucide-react';
import { SimulatorTelemetryGrid } from './SimulatorTelemetryGrid';
import { NokiaTelemetryGrid } from './NokiaTelemetryGrid';
import { Device, TelemetrySourceStatus } from '../lib/types';

interface TelemetryGridProps {
  devices: Device[];
  selectedNodeFilter: string | null;
  onClearNodeFilter: () => void;
  telemetrySource: TelemetrySourceStatus['source'] | null;
}

export const TelemetryGrid: React.FC<TelemetryGridProps> = ({
  devices,
  selectedNodeFilter,
  onClearNodeFilter,
  telemetrySource,
}) => {
  if (telemetrySource === 'simulator') {
    return (
      <SimulatorTelemetryGrid
        devices={devices}
        selectedNodeFilter={selectedNodeFilter}
        onClearNodeFilter={onClearNodeFilter}
      />
    );
  }

  if (telemetrySource === 'nokia') {
    return (
      <NokiaTelemetryGrid
        devices={devices}
        selectedNodeFilter={selectedNodeFilter}
        onClearNodeFilter={onClearNodeFilter}
      />
    );
  }

  return (
    <div className="glass-card rounded-2xl p-5 border border-white/10 flex items-center gap-3 text-sm text-slate-400">
      <Cpu className="w-5 h-5 text-cyan-400 animate-pulse" />
      Loading telemetry source...
    </div>
  );
};
