import json
import os
from pathlib import Path
from typing import Dict, Optional

from ..models import Device, PowerMode
from ..simulator import simulator
from .interface import BaseTelemetryAdapter
from .nokia_adapter import NokiaTelemetryAdapter
from .simulator_adapter import SimulatorAdapter
from .nokia_topology import NokiaTopology


class TelemetryProvider:
    def __init__(self):
        self._config = self._load_config()
        self.simulator_adapter = SimulatorAdapter()
        self.nokia_adapter = NokiaTelemetryAdapter(self._config)
        self.nokia_topology = NokiaTopology()
        self._source_mode = ""
        self.adapter: BaseTelemetryAdapter = self.simulator_adapter
        self.set_source_mode(os.getenv("TELEMETRY_SOURCE", self._config.get("telemetry_source", "simulator")))

    @staticmethod
    def _load_config() -> dict:
        path = Path(__file__).resolve().parent.parent / "config" / "policies.json"
        try:
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    @property
    def source_mode(self) -> str:
        return self._source_mode

    @property
    def topology_engine(self):
        return simulator.topology_engine

    def get_topology_state(self) -> dict:
        if self._source_mode == "nokia":
            return self.nokia_topology.get_topology_state(self.get_devices().values())
        return self.topology_engine.get_topology_state()

    def set_source_mode(self, mode: str) -> str:
        normalized = mode.lower().strip()
        if normalized not in {"simulator", "nokia"}:
            raise ValueError("Telemetry source must be 'simulator' or 'nokia'.")
        self._source_mode = normalized
        self.adapter = self.simulator_adapter if normalized == "simulator" else self.nokia_adapter
        if normalized == "nokia":
            self.nokia_adapter.initialize()
        return self._source_mode

    def refresh(self) -> None:
        if self._source_mode == "nokia":
            self.nokia_adapter.refresh()
        else:
            self.simulator_adapter.initialize()

    def initialize(self) -> None:
        self.adapter.initialize()

    def tick(self) -> None:
        self.adapter.tick()

    def get_devices(self) -> Dict[str, Device]:
        return self.adapter.get_devices()

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.adapter.get_device(device_id)

    def set_device_power_mode(self, device_id: str, mode: PowerMode) -> bool:
        return self.adapter.set_device_power_mode(device_id, mode)

    @property
    def baseline_power_kw(self) -> float:
        return self.adapter.baseline_power_kw

    @property
    def total_energy_saved_kwh(self) -> float:
        return self.adapter.total_energy_saved_kwh

    def inject_fault(self, device_id: str, fault_type: str) -> bool:
        if self._source_mode != "simulator":
            return False
        return self.simulator_adapter.inject_fault(device_id, fault_type)

    def clear_fault(self, device_id: str) -> bool:
        if self._source_mode != "simulator":
            return False
        return self.simulator_adapter.clear_fault(device_id)


telemetry_provider = TelemetryProvider()
