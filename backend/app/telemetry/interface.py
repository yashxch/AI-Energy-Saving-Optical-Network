from abc import ABC, abstractmethod
from typing import Dict, Optional

from ..models import Device, PowerMode


class BaseTelemetryAdapter(ABC):
    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def tick(self) -> None:
        pass

    @abstractmethod
    def get_devices(self) -> Dict[str, Device]:
        pass

    @abstractmethod
    def get_device(self, device_id: str) -> Optional[Device]:
        pass

    @abstractmethod
    def set_device_power_mode(self, device_id: str, mode: PowerMode) -> bool:
        pass

    @property
    @abstractmethod
    def baseline_power_kw(self) -> float:
        pass

    @property
    @abstractmethod
    def total_energy_saved_kwh(self) -> float:
        pass
