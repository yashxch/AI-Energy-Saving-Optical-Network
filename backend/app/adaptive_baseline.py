"""Device-specific online telemetry baselines."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Optional

ADAPTIVE_K = 3.0
ADAPTIVE_WARNING_SIGMA = 2.0
ADAPTIVE_ANOMALY_SIGMA = 3.0
ADAPTIVE_MIN_SAMPLES = 30
ADAPTIVE_WARNING_UPDATE_WEIGHT = 0.1
ADAPTIVE_UPDATE_ANOMALIES = False
POLICY_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "policies.json")

NUMERIC_TELEMETRY_FIELDS = (
    "tx_power_dbm", "rx_power_dbm", "laser_bias_ma", "laser_temp_c",
    "dsp_temp_c", "module_temp_c", "ber", "pre_fec_ber", "post_fec_ber",
    "q_factor_db", "osnr_db", "chromatic_dispersion", "voltage_v",
    "current_a", "fan_rpm", "traffic_utilization_pct", "power_consumption_w",
)

HARD_SAFETY_LIMITS = {
    "dsp_temp_c": {"max": 80.0, "name": "maximum DSP temperature"},
    "pre_fec_ber": {"max": 1.0e-4, "name": "maximum pre-FEC BER"},
    "osnr_db": {"min": 14.5, "name": "minimum OSNR"},
}


@dataclass
class RunningStatistic:
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    minimum: Optional[float] = None
    maximum: Optional[float] = None

    @property
    def variance(self) -> float:
        return self.m2 / (self.count - 1) if self.count > 1 else 0.0

    @property
    def standard_deviation(self) -> float:
        return self.variance ** 0.5

    def update(self, value: float, weight: float = 1.0) -> None:
        if weight <= 0:
            return
        if self.count == 0:
            self.count, self.mean, self.m2 = 1, value, 0.0
            self.minimum = self.maximum = value
            return
        effective_count = self.count + weight
        delta = value - self.mean
        self.mean += (weight / effective_count) * delta
        self.m2 += weight * delta * (value - self.mean)
        self.count = int(round(effective_count))
        self.minimum = min(self.minimum, value) if self.minimum is not None else value
        self.maximum = max(self.maximum, value) if self.maximum is not None else value


@dataclass
class DeviceBaseline:
    fields: Dict[str, RunningStatistic] = field(default_factory=dict)


class AdaptiveBaselineManager:
    def __init__(self, k: Optional[float] = None, min_samples: Optional[int] = None,
                 warning_sigma: Optional[float] = None,
                 anomaly_sigma: Optional[float] = None,
                 warning_update_weight: Optional[float] = None,
                 update_anomalies: Optional[bool] = None,
                 persistence_path: Optional[str] = None) -> None:
        config = self._load_config()
        self.k = k if k is not None else config["adaptive_k"]
        self.min_samples = min_samples if min_samples is not None else config["adaptive_min_samples"]
        self.warning_sigma = warning_sigma if warning_sigma is not None else config["adaptive_warning_sigma"]
        self.anomaly_sigma = anomaly_sigma if anomaly_sigma is not None else config["adaptive_anomaly_sigma"]
        self.warning_update_weight = (warning_update_weight if warning_update_weight is not None
                                      else config["adaptive_warning_update_weight"])
        self.update_anomalies = (update_anomalies if update_anomalies is not None
                                 else config["adaptive_update_anomalies"])
        self.persistence_path = persistence_path
        self._devices: Dict[str, DeviceBaseline] = {}
        self.load()

    @staticmethod
    def _load_config() -> Dict[str, Any]:
        config = {
            "adaptive_k": ADAPTIVE_K,
            "adaptive_min_samples": ADAPTIVE_MIN_SAMPLES,
            "adaptive_warning_sigma": ADAPTIVE_WARNING_SIGMA,
            "adaptive_anomaly_sigma": ADAPTIVE_ANOMALY_SIGMA,
            "adaptive_warning_update_weight": ADAPTIVE_WARNING_UPDATE_WEIGHT,
            "adaptive_update_anomalies": ADAPTIVE_UPDATE_ANOMALIES,
        }
        try:
            with open(POLICY_CONFIG_PATH, "r", encoding="utf-8") as handle:
                config.update(json.load(handle))
        except (OSError, ValueError):
            pass
        return config

    def _stat(self, device_id: str, parameter: str) -> RunningStatistic:
        device = self._devices.setdefault(device_id, DeviceBaseline())
        return device.fields.setdefault(parameter, RunningStatistic())

    @staticmethod
    def _read(telemetry: Any, parameter: str) -> Optional[float]:
        value = getattr(telemetry, parameter, None)
        if value is None and isinstance(telemetry, Mapping):
            value = telemetry.get(parameter)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _hard_limit_violation(parameter: str, value: float) -> bool:
        limit = HARD_SAFETY_LIMITS.get(parameter)
        return bool(limit and (("max" in limit and value > limit["max"]) or
                               ("min" in limit and value < limit["min"])))

    def classify(self, device_id: str, parameter: str, value: Optional[float]) -> Dict[str, Any]:
        stat = self._stat(device_id, parameter)
        if value is None:
            return {"device_id": device_id, "parameter": parameter, "current_value": None,
                    "classification": "MISSING", "samples": stat.count,
                    "learning_status": self._status(stat)}
        safety_violation = self._hard_limit_violation(parameter, value)
        std = stat.standard_deviation
        if stat.count < self.min_samples:
            classification = "ANOMALY" if safety_violation else "WARMING_UP"
        elif safety_violation:
            classification = "ANOMALY"
        elif std == 0.0:
            classification = "NORMAL" if value == stat.mean else "ANOMALY"
        elif abs(value - stat.mean) > self.anomaly_sigma * std:
            classification = "ANOMALY"
        elif abs(value - stat.mean) > self.warning_sigma * std:
            classification = "WARNING"
        else:
            classification = "NORMAL"
        return {
            "device_id": device_id, "parameter": parameter, "current_value": value,
            "learned_mean": stat.mean if stat.count else None,
            "learned_variance": stat.variance if stat.count else None,
            "learned_std": std if stat.count else None,
            "minimum": stat.minimum, "maximum": stat.maximum,
            "lower_threshold": stat.mean - self.k * std if stat.count else None,
            "upper_threshold": stat.mean + self.k * std if stat.count else None,
            "classification": classification, "samples": stat.count,
            "learning_status": self._status(stat),
            "hard_safety_violation": safety_violation,
            "hard_safety_limit": HARD_SAFETY_LIMITS.get(parameter),
        }

    def _status(self, stat: RunningStatistic) -> str:
        return "LEARNING_ACTIVE" if stat.count >= self.min_samples else "WARMING_UP"

    def update_device(self, device_id: str, telemetry: Any) -> Dict[str, Any]:
        results = {}
        for parameter in NUMERIC_TELEMETRY_FIELDS:
            value = self._read(telemetry, parameter)
            before = self.classify(device_id, parameter, value)
            if value is None:
                results[parameter] = before
                continue
            if before["classification"] != "ANOMALY" or self.update_anomalies:
                weight = self.warning_update_weight if before["classification"] == "WARNING" else 1.0
                self._stat(device_id, parameter).update(value, weight)
            results[parameter] = self.classify(device_id, parameter, value)
        results["optimization_opportunity"] = self.optimization_opportunity(device_id, telemetry)
        if self.persistence_path:
            self.save()
        return results

    def optimization_opportunity(self, device_id: str, telemetry: Any) -> Dict[str, Any]:
        traffic = self._read(telemetry, "traffic_utilization_pct")
        traffic_info = self.classify(device_id, "traffic_utilization_pct", traffic)
        hard_violations = []
        for parameter in ("dsp_temp_c", "pre_fec_ber", "osnr_db"):
            value = self._read(telemetry, parameter)
            if value is not None and self._hard_limit_violation(parameter, value):
                hard_violations.append(parameter)
        eligible = bool(traffic_info.get("learning_status") == "LEARNING_ACTIVE"
                        and traffic_info.get("classification") == "NORMAL"
                        and traffic is not None and traffic_info.get("learned_mean") is not None
                        and traffic < traffic_info["learned_mean"] and not hard_violations)
        return {"optimization_opportunity": eligible,
                "reason": "low learned-normal traffic and no hard safety violation" if eligible
                else "adaptive or hard-safety conditions are not eligible",
                "traffic": traffic_info, "hard_safety_violations": hard_violations}

    def device_snapshot(self, device_id: str, telemetry: Any = None) -> Dict[str, Any]:
        fields = {}
        for parameter in self._devices.get(device_id, DeviceBaseline()).fields:
            value = self._read(telemetry, parameter) if telemetry is not None else None
            fields[parameter] = self.classify(device_id, parameter, value)
        result = {"device_id": device_id, "parameters": fields}
        if telemetry is not None:
            result["optimization_opportunity"] = self.optimization_opportunity(device_id, telemetry)
        return result

    def all_snapshots(self, devices: Mapping[str, Any]) -> Dict[str, Any]:
        return {device_id: self.device_snapshot(device_id, device.telemetry)
                for device_id, device in devices.items()}

    def save(self) -> None:
        if not self.persistence_path:
            return
        os.makedirs(os.path.dirname(self.persistence_path) or ".", exist_ok=True)
        payload = {device_id: {name: asdict(stat) for name, stat in device.fields.items()}
                   for device_id, device in self._devices.items()}
        with open(self.persistence_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def load(self) -> None:
        if not self.persistence_path or not os.path.exists(self.persistence_path):
            return
        with open(self.persistence_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self._devices = {device_id: DeviceBaseline({parameter: RunningStatistic(**values)
                       for parameter, values in fields.items()})
                         for device_id, fields in payload.items()}

    def reset(self) -> None:
        self._devices.clear()


adaptive_baseline_manager = AdaptiveBaselineManager()
