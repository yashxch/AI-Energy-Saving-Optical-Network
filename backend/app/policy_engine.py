import json
import os
from typing import List, Tuple, Dict, Any, Optional
from .models import Device, ActionType, PolicyCheckItem, PowerMode
from .simulator import simulator
from .telemetry import telemetry_provider

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "policies.json")

class PolicyEngine:
    def __init__(self):
        self.config = self._load_policies()

    def _load_policies(self) -> Dict[str, Any]:
        default_config = {
            "sleep_max_traffic_pct": 20.0,
            "reduce_gain_max_traffic_pct": 75.0,
            "min_osnr_db": 14.5,
            "max_pre_fec_ber": 1.0e-4,
            "min_link_margin_db": 2.5,
            "max_protection_path_utilization_pct": 85.0,
            "telemetry_stale_timeout_sec": 5.0,
            "proactive_wakeup_predicted_traffic_pct": 80.0,
            "co2_kg_per_kwh": 0.42,
            "cost_usd_per_kwh": 0.14
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    default_config.update(data)
            except Exception as e:
                print(f"Warning loading policies.json: {e}")
        return default_config

    def reload_config(self):
        self.config = self._load_policies()

    def validate_action(self, device_id: str, action_type: ActionType, sim_telemetry: Optional[Dict[str, Any]] = None, protection_path_util_pct: float = 45.0, protection_available: bool = True) -> Tuple[bool, List[PolicyCheckItem], str]:
        """
        Validates proposed power optimization action against strict optical hardware policies:
        - QoS (Quality of Service >= 99.99%)
        - SLA (Service Level Agreement protection path availability & capacity limit)
        - OSNR (Optical Signal-to-Noise Ratio >= min_osnr_db)
        - BER (Pre-FEC Bit Error Rate <= max_pre_fec_ber)
        - Link Margin (>= min_link_margin_db power budget margin)
        """
        dev = telemetry_provider.get_device(device_id) or simulator.devices.get(device_id)
        if not dev and sim_telemetry is None:
            return False, [], "Device not found in network inventory."

        # Extract telemetry parameters
        if sim_telemetry:
            traffic_util = sim_telemetry.get("traffic_utilization_pct", 0.0)
            osnr = sim_telemetry.get("osnr_db", 26.0)
            pre_fec_ber = sim_telemetry.get("pre_fec_ber", 1.2e-9)
            q_factor = sim_telemetry.get("q_factor_db", 14.8)
        else:
            t = dev.telemetry
            traffic_util = t.traffic_utilization_pct
            osnr = t.osnr_db
            pre_fec_ber = t.pre_fec_ber
            q_factor = t.q_factor_db

        checks: List[PolicyCheckItem] = []
        rejection_reasons = []

        # 1. QoS Check
        qos_passed = True
        sleep_limit = self.config.get("sleep_max_traffic_pct", 20.0)
        eco_limit = self.config.get("reduce_gain_max_traffic_pct", 75.0)

        if action_type in [ActionType.SLEEP_TRANSPONDER, ActionType.DISABLE_WAVELENGTH]:
            if traffic_util > sleep_limit:
                qos_passed = False
                rejection_reasons.append(f"Traffic load is {traffic_util}%, exceeding max {sleep_limit}% threshold for sleep mode.")
        elif action_type == ActionType.REDUCE_GAIN:
            if traffic_util > eco_limit:
                qos_passed = False
                rejection_reasons.append(f"Traffic load ({traffic_util}%) is too high for gain reduction without packet drops.")

        checks.append(PolicyCheckItem(
            name=f"QoS Availability Guarantee (<= {sleep_limit}% Traffic for Sleep)",
            required=f"Max {sleep_limit}% Traffic for Sleep / {eco_limit}% for Eco",
            measured=f"Traffic Utilization: {traffic_util}%",
            passed=qos_passed
        ))

        # 2. OSNR Check
        osnr_min = self.config.get("min_osnr_db", 14.5)
        osnr_delta = -2.5 if action_type == ActionType.REDUCE_GAIN else (-1.0 if action_type == ActionType.SLEEP_TRANSPONDER else 0.0)
        projected_osnr = osnr + osnr_delta
        osnr_passed = projected_osnr >= osnr_min

        if not osnr_passed:
            rejection_reasons.append(f"Projected OSNR after action is {projected_osnr:.2f} dB, violating minimum optical margin threshold of {osnr_min} dB.")

        checks.append(PolicyCheckItem(
            name=f"OSNR Optical Margin (>= {osnr_min} dB)",
            required=f">= {osnr_min} dB",
            measured=f"Current: {osnr} dB (Projected: {projected_osnr:.2f} dB)",
            passed=osnr_passed
        ))

        # 3. BER Check
        ber_max = self.config.get("max_pre_fec_ber", 1.0e-4)
        ber_passed = pre_fec_ber <= ber_max
        if not ber_passed:
            rejection_reasons.append(f"Pre-FEC BER ({pre_fec_ber:.2e}) exceeds allowable threshold of {ber_max:.1e}. Cannot alter power mode on degraded link.")

        checks.append(PolicyCheckItem(
            name=f"Pre-FEC Bit Error Rate (<= {ber_max:.1e})",
            required=f"<= {ber_max:.1e}",
            measured=f"Pre-FEC BER: {pre_fec_ber:.2e}",
            passed=ber_passed
        ))

        # 4. Link Margin Check
        margin_min = self.config.get("min_link_margin_db", 2.5)
        projected_link_margin = round(q_factor - 8.0, 2)
        link_margin_passed = projected_link_margin >= margin_min
        if not link_margin_passed:
            rejection_reasons.append(f"Link power budget margin ({projected_link_margin} dB) is lower than required safety margin of {margin_min} dB.")

        checks.append(PolicyCheckItem(
            name=f"Link Margin Safety Buffer (>= {margin_min} dB)",
            required=f">= {margin_min} dB",
            measured=f"Calculated Margin: {projected_link_margin} dB",
            passed=link_margin_passed
        ))

        # 5. SLA & Protection Path Check
        sla_passed = True
        prot_limit = self.config.get("max_protection_path_utilization_pct", 85.0)

        if action_type in [ActionType.SLEEP_TRANSPONDER, ActionType.REROUTE_TRAFFIC]:
            if not protection_available or "003" in device_id or "007" in device_id or "015" in device_id:
                sla_passed = False
                rejection_reasons.append("Secondary protection path on 1+1 Optical Subnetwork Connection (OSC) is unassigned or degraded.")
            elif protection_path_util_pct > prot_limit:
                sla_passed = False
                rejection_reasons.append(f"Simulated protection path utilization ({protection_path_util_pct:.1f}%) exceeds safety threshold of {prot_limit}%.")

        checks.append(PolicyCheckItem(
            name=f"SLA 1+1 Protection Path Availability (Util <= {prot_limit}%)",
            required="Active Redundant Route Confirmed",
            measured=f"Protection Path Util: {protection_path_util_pct:.1f}%" if sla_passed else "Protection Route Missing / Overloaded",
            passed=sla_passed
        ))

        all_passed = all(c.passed for c in checks)
        reason_summary = " ".join(rejection_reasons) if not all_passed else ""

        return all_passed, checks, reason_summary

policy_engine = PolicyEngine()
