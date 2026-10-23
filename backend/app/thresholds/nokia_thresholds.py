from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class NokiaThreshold:
    metric: str
    unit: str
    interval: str
    warning: Optional[float] = None
    major: Optional[float] = None
    critical: Optional[float] = None
    comparison: str = "high"
    requires_baseline: bool = False
    requires_profile: bool = False
    cumulative: bool = False


FIXED_THRESHOLDS = {
    "q_margin": NokiaThreshold("Q-margin", "dB", "instantaneous", warning=2.0, critical=1.0, comparison="low"),
    "fec_ubc": NokiaThreshold("FEC UBC", "count", "15m", warning=1.0, cumulative=True),
    "lane_spread": NokiaThreshold("Lane power spread", "dB", "instantaneous", warning=2.0),
    "utilization": NokiaThreshold("Bandwidth utilization", "%", "15m", warning=70.0, major=85.0, critical=95.0),
    "eth_errors": NokiaThreshold("Ethernet errors", "count", "15m", warning=1.0, cumulative=True),
    "cv_pcs": NokiaThreshold("CV-PCS", "count", "15m", warning=1.0, cumulative=True),
    "es_pcs": NokiaThreshold("ES-PCS", "seconds", "15m", warning=1.0, major=1.0, cumulative=True),
    "sefs_pcs": NokiaThreshold("SEFS-PCS", "seconds", "15m", warning=1.0, cumulative=True),
    "ses_pcs": NokiaThreshold("SES-PCS", "seconds", "15m", warning=1.0, cumulative=True),
    "measured_output": NokiaThreshold("Measured network output", "dB", "instantaneous", warning=1.0, critical=2.0, comparison="absolute"),
    "power": NokiaThreshold("Actual equipment power", "% of rated maximum", "instantaneous", warning=80.0, critical=90.0),
    "fan_speed_mismatch": NokiaThreshold("Fan speed mismatch", "%", "instantaneous", warning=20.0),
}

PROFILE_DEPENDENT_METRICS = {
    "pre_fec_ber": "BERPreFEC route profile and measured baseline",
    "opr": "OPR factory TCA profile 8 or site baseline",
    "lane_limits": "Optical module DDM warning/alarm limits",
    "laser_case_temp": "Equipment/card temperature profile",
    "esnr": "Measured ESNR baseline",
    "voltage_current": "Equipment-specific nominal input limits",
    "ains": "Configured equipment/service AINS timer",
}


def is_unavailable(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip().upper() in {"", "N/A", "NA", "OFF", "UNAVAILABLE", "—"})
