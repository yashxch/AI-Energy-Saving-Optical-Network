import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ..models import Device, NokiaThresholdResult
from .nokia_thresholds import FIXED_THRESHOLDS, PROFILE_DEPENDENT_METRICS, is_unavailable


class NokiaThresholdEvaluator:
    """Evaluates Nokia measurements without applying simulator thresholds."""

    def __init__(self) -> None:
        self._previous: Dict[tuple[str, str], tuple[float, float]] = {}
        self._samples: Dict[tuple[str, str], List[tuple[float, float]]] = defaultdict(list)

    @staticmethod
    def _raw(device: Device) -> Mapping[str, Any]:
        return device.raw_record or {}

    @staticmethod
    def _value(raw: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in raw and not is_unavailable(raw[key]):
                return raw[key]
        return None

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        if is_unavailable(value):
            return None
        try:
            return float(str(value).strip().replace(",", ""))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _result(
        device: Device,
        metric: str,
        value: Any,
        unit: str,
        severity: str,
        explanation: str,
        threshold: Optional[str] = None,
        baseline: Optional[str] = None,
        complete: bool = True,
        quality: str = "measured",
        interval: str = "instantaneous",
    ) -> NokiaThresholdResult:
        return NokiaThresholdResult(
            device_id=device.id,
            device_name=device.name,
            ne_name=device.ne_name,
            shelf_id=device.shelf_id,
            slot_id=device.slot_id,
            port_id=device.port_id,
            metric=metric,
            measured_value=value,
            unit=unit,
            severity=severity,
            explanation=explanation,
            threshold_used=threshold,
            baseline_used=baseline,
            quality=quality,
            complete=complete,
            interval=interval,
            timestamp=time.time(),
        )

    def _counter_delta(self, device: Device, metric: str, value: Optional[float], timestamp: float) -> Optional[float]:
        if value is None:
            return None
        key = (device.id, metric)
        previous = self._previous.get(key)
        self._previous[key] = (value, timestamp)
        if previous is None:
            return None
        old, _ = previous
        if value >= old:
            return value - old
        return value

    def _record_sample(self, device: Device, metric: str, value: Optional[float], timestamp: float) -> List[tuple[float, float]]:
        if value is None:
            return []
        key = (device.id, metric)
        samples = self._samples[key]
        samples.append((timestamp, value))
        self._samples[key] = [(ts, item) for ts, item in samples if timestamp - ts <= 900.0]
        return self._samples[key]

    def evaluate_device(self, device: Device) -> List[NokiaThresholdResult]:
        raw = self._raw(device)
        now = self._number(self._value(raw, "timestamp", "TIMESTAMP")) or device.telemetry.timestamp or time.time()
        if now > 10_000_000_000:
            now /= 1000.0
        results: List[NokiaThresholdResult] = []

        q_values = {
            "Q-margin min": self._number(self._value(raw, "q_margin_min_db", "Q-Margin - Min", "Q_MIN", "q_min")),
            "Q-margin max": self._number(self._value(raw, "q_margin_max_db", "Q-Margin - Max", "Q_MAX", "q_max")),
            "Q-margin average": self._number(self._value(raw, "q_margin_avg_db", "Q-Margin - Average", "Q_AVG", "q_avg")),
        }
        for label, value in q_values.items():
            if value is None:
                continue
            severity = "CRITICAL" if value < 1.0 else "WARNING" if value < 2.0 or (label.endswith("average") and value < 3.0) else "NORMAL"
            results.append(self._result(device, label, value, "dB", severity, f"{label} is {value:g} dB; guide target average is at least 3 dB.", "critical < 1 dB; warning < 2 dB; average target >= 3 dB"))

        fec = self._number(self._value(raw, "fec_ubc", "FEC UBC", "FEC-UBC", "UBC"))
        delta = self._counter_delta(device, "fec_ubc", fec, now)
        if delta is None and fec is not None:
            results.append(self._result(device, "FEC UBC", fec, "count", "UNKNOWN", "A prior 15-minute counter value is required to calculate an interval delta.", "delta >= 1", complete=False, interval="15m"))
        elif delta is not None:
            severity = "CRITICAL" if delta >= 1 else "NORMAL"
            results.append(self._result(device, "FEC UBC", delta, "count", severity, f"15-minute FEC UBC delta is {delta:g}; target is 0.", "delta >= 1", interval="15m"))

        rx = [self._number(self._value(raw, f"rx_lane_power_{i}_dbm", f"RX-LANE-{i}", f"Rx Lane Power {i}")) for i in range(1, 5)]
        tx = [self._number(self._value(raw, f"tx_lane_power_{i}_dbm", f"TX-LANE-{i}", f"Tx Lane Power {i}")) for i in range(1, 5)]
        for label, lanes in (("Rx lane power spread", rx), ("Tx lane power spread", tx)):
            available = [value for value in lanes if value is not None]
            if len(available) >= 2:
                spread = max(available) - min(available)
                results.append(self._result(device, label, spread, "dB", "WARNING" if spread > 2.0 else "NORMAL", f"Lane-to-lane spread is {spread:g} dB.", "> 2 dB investigation"))

        expected = self._number(self._value(raw, "expected_network_output_power_dbm", "Expected Network Output Power", "EXP_NET_OUT"))
        measured = self._number(self._value(raw, "measured_network_output_power_dbm", "Measured Network Output Power", "MEAS_NET_OUT"))
        if expected is not None and measured is not None:
            deviation = abs(measured - expected)
            severity = "CRITICAL" if deviation > 2.0 else "WARNING" if deviation > 1.0 else "NORMAL"
            results.append(self._result(device, "Measured network output", measured, "dBm", severity, f"Measured output differs from expected by {deviation:g} dB.", "warning > 1 dB; critical > 2 dB", baseline=f"expected {expected:g} dBm"))
        elif is_unavailable(self._value(raw, "measured_network_output_power_dbm", "Measured Network Output Power", "MEAS_NET_OUT")):
            results.append(self._result(device, "Measured network output", "N/A", "dBm", "UNKNOWN", "Measured output is unavailable or laser state is Off; no numeric zero was assumed.", "expected OTSi target", complete=False))

        utilization = self._number(self._value(raw, "confirmed_utilization_pct", "UTILIZATION-PCT", "utilization_pct"))
        if utilization is not None:
            samples = self._record_sample(device, "utilization", utilization, now)
            sustained = len(samples) >= 2 and now - samples[0][0] >= 900.0 and all(item >= 95.0 for _, item in samples)
            severity = "CRITICAL" if sustained else "MAJOR" if utilization >= 85.0 else "WARNING" if utilization >= 70.0 else "NORMAL"
            results.append(self._result(device, "Bandwidth utilization", utilization, "%", severity, f"Utilization is {utilization:g}%; critical requires >=95% sustained for 15 minutes.", "warning >= 70%; major >= 85%; critical >= 95% sustained 15m", complete=True, interval="15m"))

        for metric, keys, unit in (
            ("CV-PCS", ("cv_pcs", "CV-PCS"), "count"),
            ("ES-PCS", ("es_pcs", "ES-PCS"), "seconds"),
            ("SEFS-PCS", ("sefs_pcs", "SEFS-PCS"), "seconds"),
            ("SES-PCS", ("ses_pcs", "SES-PCS"), "seconds"),
        ):
            value = self._number(self._value(raw, *keys))
            delta = self._counter_delta(device, metric, value, now)
            if delta is not None:
                severity = "MAJOR" if metric == "CV-PCS" and delta > 0 and (self._number(self._value(raw, "es_pcs", "ES-PCS")) or 0) > 0 else "WARNING" if delta > 0 else "NORMAL"
                if metric in {"ES-PCS", "SEFS-PCS", "SES-PCS"} and delta >= 1:
                    severity = "MAJOR" if metric == "ES-PCS" else "WARNING"
                results.append(self._result(device, metric, delta, unit, severity, f"{metric} interval delta is {delta:g}; target is 0.", "15-minute delta", interval="15m"))
            elif value is not None:
                results.append(self._result(device, metric, value, unit, "UNKNOWN", "A prior counter value is required to calculate the PM interval delta.", "15-minute delta", complete=False, interval="15m"))

        oper = self._value(raw, "connection_state", "Connection State", "oper_state", "OPER-STATE")
        if oper is not None:
            text = str(oper)
            severity = "CRITICAL" if text.strip().lower() in {"down", "failed", "fault", "ains flt"} else "NORMAL"
            results.append(self._result(device, "Connection state", text, "state", severity, f"Operational state is {text}; administrative state is evaluated separately.", "expected operational Up"))

        for metric, reason in PROFILE_DEPENDENT_METRICS.items():
            if metric == "esnr":
                value = self._number(self._value(raw, "esnr_db", "ESNR"))
                if value is not None:
                    results.append(self._result(device, "ESNR", value, "dB", "UNKNOWN", "Measured ESNR is available, but no valid baseline was supplied for degradation evaluation.", "degradation >= 1 dB warning; >= 2 dB major", complete=False, baseline=reason))

        return results

    def evaluate_devices(self, devices: Iterable[Device]) -> List[NokiaThresholdResult]:
        results: List[NokiaThresholdResult] = []
        for device in devices:
            results.extend(self.evaluate_device(device))
        return results

    def has_blocking_guardrail(self, device: Device) -> bool:
        results = self.evaluate_device(device)
        return any(result.severity in {"CRITICAL", "MAJOR"} or (not result.complete and result.metric in {"Q-margin min", "Q-margin average", "Connection state"}) for result in results)
