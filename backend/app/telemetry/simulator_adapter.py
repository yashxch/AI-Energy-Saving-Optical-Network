from typing import Dict, Optional

from ..models import Device, PowerMode
from ..simulator import simulator
from .interface import BaseTelemetryAdapter


class SimulatorAdapter(BaseTelemetryAdapter):
    def initialize(self) -> None:
        pass

    def tick(self) -> None:
        simulator.tick()

    def get_devices(self) -> Dict[str, Device]:
        return simulator.devices

    def get_device(self, device_id: str) -> Optional[Device]:
        return simulator.devices.get(device_id)

    def set_device_power_mode(self, device_id: str, mode: PowerMode) -> bool:
        if device_id not in simulator.devices:
            return False
        simulator.set_device_power_mode(device_id, mode)
        return True

    @property
    def baseline_power_kw(self) -> float:
        return simulator.baseline_power_kw

    @property
    def total_energy_saved_kwh(self) -> float:
        return simulator.total_energy_saved_kwh

    def inject_fault(self, device_id: str, fault_type: str) -> bool:
        if device_id not in simulator.devices:
            return False
        simulator.inject_fault(device_id, fault_type)
        return True

    def clear_fault(self, device_id: str) -> bool:
        simulator.clear_fault(device_id)
        return device_id not in simulator.fault_injections
