import math
import time

from typing import List, Dict
import numpy as np
from sklearn.ensemble import IsolationForest
from .models import TrafficPrediction, AnomalyItem
from .simulator import simulator

class MLEngine:
    def __init__(self):
        self.iso_forest = IsolationForest(contamination=0.08, random_state=42)
        self._is_fitted = False

    def predict_traffic(self, horizon: str) -> TrafficPrediction:
        """Generates traffic predictions for 5m, 1h, or 24h horizons."""
        now = time.time()
        diurnal_current = simulator._get_diurnal_factor()
        base_gbps = 800.0 * 50  # 40 Tbps total capacity across transponders

        timestamps = []
        predicted_traffic = []
        upper_bounds = []
        lower_bounds = []

        if horizon == "5m":
            num_points = 10
            step_sec = 30
            dt_fmt = "%H:%M:%S"
        elif horizon == "1h":
            num_points = 12
            step_sec = 300
            dt_fmt = "%H:%M"
        else: # "24h"
            num_points = 24
            step_sec = 3600
            dt_fmt = "%H:00"

        for i in range(1, num_points + 1):
            future_time = now + (i * step_sec)
            t_str = time.strftime(dt_fmt, time.localtime(future_time))
            timestamps.append(t_str)

            # Simulated LSTM harmonic curve
            if horizon == "24h":
                angle = ((future_time - simulator.start_time) / 120.0) * 2 * math.pi
                predicted_factor = max(0.12, min(0.98, 0.2 + 0.75 * ((math.sin(angle) + 1) / 2)))
            else:
                trend = 0.015 * math.sin(i * 0.5)
                predicted_factor = max(0.1, min(0.95, diurnal_current + trend))

            traffic_gbps = round(base_gbps * predicted_factor, 1)
            margin = round(traffic_gbps * (0.05 + 0.005 * i), 1)

            predicted_traffic.append(traffic_gbps)
            upper_bounds.append(round(traffic_gbps + margin, 1))
            lower_bounds.append(round(max(0.0, traffic_gbps - margin), 1))

        return TrafficPrediction(
            horizon=horizon,
            timestamps=timestamps,
            predicted_traffic_gbps=predicted_traffic,
            upper_bound_gbps=upper_bounds,
            lower_bound_gbps=lower_bounds,
            confidence_score=0.96 if horizon == "5m" else (0.91 if horizon == "1h" else 0.85)
        )

    def detect_anomalies(self) -> List[AnomalyItem]:
        """Runs Isolation Forest and heuristic boundary checks across 100 devices."""
        anomalies = []
        features = []
        device_ids = []

        for dev_id, dev in simulator.devices.items():
            t = dev.telemetry
            # Features: [dsp_temp, pre_fec_ber, osnr_db, power_consumption_w]
            features.append([t.dsp_temp_c, math.log10(t.pre_fec_ber + 1e-12), t.osnr_db, t.power_consumption_w])
            device_ids.append(dev_id)

        X = np.array(features)
        
        # Fit or predict Isolation Forest
        if len(X) > 10:
            scores = self.iso_forest.fit_predict(X)
            decision_scores = self.iso_forest.decision_function(X)
        else:
            scores = [1] * len(X)
            decision_scores = [0.5] * len(X)

        timestamp_str = time.strftime("%H:%M:%S")

        for idx, dev_id in enumerate(device_ids):
            dev = simulator.devices[dev_id]
            t = dev.telemetry
            iso_flagged = scores[idx] == -1
            dec_score = round(float(decision_scores[idx]), 3)

            # Check explicit bounds or ML anomaly flags
            if t.dsp_temp_c > 80.0:
                anomalies.append(AnomalyItem(
                    id=f"ANO-{dev_id}-TEMP",
                    device_id=dev_id,
                    device_name=dev.name,
                    anomaly_type="Abnormal Temperature",
                    severity="Critical",
                    score=abs(dec_score) + 0.4,
                    details=f"DSP temperature reached critical level of {t.dsp_temp_c}°C (Threshold: 75°C). Risk of thermal throttling.",
                    timestamp=timestamp_str
                ))
            elif t.pre_fec_ber > 5e-4:
                anomalies.append(AnomalyItem(
                    id=f"ANO-{dev_id}-BER",
                    device_id=dev_id,
                    device_name=dev.name,
                    anomaly_type="Abnormal BER Spike",
                    severity="Warning" if t.pre_fec_ber < 1e-3 else "Critical",
                    score=abs(dec_score) + 0.35,
                    details=f"Pre-FEC BER degraded to {t.pre_fec_ber:.2e} (Threshold: 1.0e-4). Forward Error Correction limit near exhaustion.",
                    timestamp=timestamp_str
                ))
            elif t.osnr_db < 15.0:
                anomalies.append(AnomalyItem(
                    id=f"ANO-{dev_id}-OSNR",
                    device_id=dev_id,
                    device_name=dev.name,
                    anomaly_type="Low OSNR Margin",
                    severity="Warning",
                    score=abs(dec_score) + 0.25,
                    details=f"Optical Signal-to-Noise Ratio degraded to {t.osnr_db} dB (Min limit: 14.5 dB). Link quality compromised.",
                    timestamp=timestamp_str
                ))
            elif iso_flagged and t.power_consumption_w > 340.0:
                anomalies.append(AnomalyItem(
                    id=f"ANO-{dev_id}-PWR",
                    device_id=dev_id,
                    device_name=dev.name,
                    anomaly_type="Excessive Power Draw",
                    severity="Warning",
                    score=abs(dec_score),
                    details=f"Isolation Forest flagged anomaly: Unusually high power draw of {t.power_consumption_w}W relative to traffic load ({t.traffic_utilization_pct}%).",
                    timestamp=timestamp_str
                ))

        return sorted(anomalies, key=lambda a: a.score, reverse=True)

ml_engine = MLEngine()
