import time
import math
from typing import List, Dict
from .models import FCAPSAlarm, FCAPSEnergyAccounting, FCAPSSecurityLog, PowerMode
from .simulator import simulator

class FCAPSManager:
    def __init__(self):
        self.acknowledged_alarms: set = set()
        self.security_logs: List[FCAPSSecurityLog] = [
            FCAPSSecurityLog(
                id="SEC-001",
                timestamp=time.strftime("%H:%M:%S", time.localtime(time.time() - 3600)),
                user="admin_nokia",
                event="API Token Authentication",
                ip_address="192.168.1.104",
                status="SUCCESS"
            ),
            FCAPSSecurityLog(
                id="SEC-002",
                timestamp=time.strftime("%H:%M:%S", time.localtime(time.time() - 1800)),
                user="ai_agent_service",
                event="Power Mode Change Trigger (TRX-800G-012)",
                ip_address="127.0.0.1",
                status="SUCCESS"
            ),
            FCAPSSecurityLog(
                id="SEC-003",
                timestamp=time.strftime("%H:%M:%S", time.localtime(time.time() - 600)),
                user="unknown_guest",
                event="Unauthorized REST API Endpoint Access (/admin/override)",
                ip_address="10.0.4.88",
                status="DENIED"
            )
        ]

    def get_fault_alarms(self) -> List[FCAPSAlarm]:
        """Generates dynamic active alarms based on device health and fault injections."""
        alarms = []
        for dev_id, dev in simulator.devices.items():
            t = dev.telemetry
            alarm_id = f"ALM-{dev_id}"
            
            if t.dsp_temp_c > 80.0:
                alarms.append(FCAPSAlarm(
                    id=alarm_id + "-TEMP",
                    device_id=dev_id,
                    device_name=dev.name,
                    severity="Critical",
                    message=f"Thermal Alarm: DSP temperature {t.dsp_temp_c}°C exceeds critical threshold (80°C).",
                    timestamp=time.strftime("%H:%M:%S"),
                    acknowledged=alarm_id + "-TEMP" in self.acknowledged_alarms
                ))
            elif t.pre_fec_ber > 5e-4:
                alarms.append(FCAPSAlarm(
                    id=alarm_id + "-BER",
                    device_id=dev_id,
                    device_name=dev.name,
                    severity="Major",
                    message=f"Signal Degradation: Pre-FEC BER {t.pre_fec_ber:.2e} on wavelength {dev.wavelength_nm}nm.",
                    timestamp=time.strftime("%H:%M:%S"),
                    acknowledged=alarm_id + "-BER" in self.acknowledged_alarms
                ))
            elif t.osnr_db < 15.0:
                alarms.append(FCAPSAlarm(
                    id=alarm_id + "-OSNR",
                    device_id=dev_id,
                    device_name=dev.name,
                    severity="Minor",
                    message=f"OSNR Degradation: OSNR level {t.osnr_db} dB is approaching receiver threshold (14.5 dB).",
                    timestamp=time.strftime("%H:%M:%S"),
                    acknowledged=alarm_id + "-OSNR" in self.acknowledged_alarms
                ))

        return alarms

    def acknowledge_alarm(self, alarm_id: str):
        self.acknowledged_alarms.add(alarm_id)

    def get_energy_accounting(self) -> FCAPSEnergyAccounting:
        """Calculates live energy consumption, savings, carbon offset, and 24-hour curve."""
        active_kw = round(sum(d.telemetry.power_consumption_w for d in simulator.devices.values()) / 1000.0, 2)
        base_kw = simulator.baseline_power_kw
        saved_kwh = round(simulator.total_energy_saved_kwh, 2)
        savings_pct = round(max(0.0, ((base_kw - active_kw) / base_kw) * 100), 1)
        co2_kg = round(saved_kwh * 0.42, 2)
        cost_usd = round(saved_kwh * 0.14, 2)

        # 24h historical power curve
        now = time.time()
        power_history = []
        for hour in range(24, 0, -1):
            h_time = time.strftime("%H:00", time.localtime(now - hour * 3600))
            # Simulate historical power reduction trend
            h_base = base_kw + (15.0 * math.sin(hour * 0.3))
            h_opt = h_base - (28.0 if hour < 14 else 12.0)
            power_history.append({
                "time": h_time,
                "Baseline_kW": round(h_base, 1),
                "AI_Optimized_kW": round(h_opt, 1)
            })

        return FCAPSEnergyAccounting(
            total_power_kw=active_kw,
            baseline_power_kw=base_kw,
            energy_saved_kwh=saved_kwh,
            power_savings_pct=savings_pct,
            carbon_reduced_kg=co2_kg,
            cost_savings_usd=cost_usd,
            power_history=power_history
        )

    def log_security_event(self, user: str, event: str, ip: str, status: str):
        sec_id = f"SEC-{len(self.security_logs) + 1:03d}"
        self.security_logs.insert(0, FCAPSSecurityLog(
            id=sec_id,
            timestamp=time.strftime("%H:%M:%S"),
            user=user,
            event=event,
            ip_address=ip,
            status=status
        ))

fcaps_manager = FCAPSManager()
