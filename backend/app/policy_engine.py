from typing import List, Tuple
from .models import Device, ActionType, PolicyCheckItem, Recommendation, PowerMode
from .simulator import simulator

class PolicyEngine:
    def validate_action(self, device_id: str, action_type: ActionType) -> Tuple[bool, List[PolicyCheckItem], str]:
        """
        Validates proposed power optimization action against strict optical hardware policies:
        - QoS (Quality of Service >= 99.99%)
        - SLA (Service Level Agreement protection path availability)
        - OSNR (Optical Signal-to-Noise Ratio >= 14.5 dB)
        - BER (Pre-FEC Bit Error Rate <= 1.0e-4)
        - Link Margin (>= 2.5 dB power budget margin)
        - Protection Paths (Redundant protection path confirmation)
        """
        dev = simulator.devices.get(device_id)
        if not dev:
            return False, [], "Device not found in network inventory."

        t = dev.telemetry
        checks: List[PolicyCheckItem] = []
        rejection_reasons = []

        # 1. QoS Check (Quality of Service)
        # Re-routing or sleeping is rejected if traffic is high
        qos_passed = True
        if action_type in [ActionType.SLEEP_TRANSPONDER, ActionType.DISABLE_WAVELENGTH]:
            if t.traffic_utilization_pct > 20.0:
                qos_passed = False
                rejection_reasons.append(f"Traffic load is {t.traffic_utilization_pct}%, exceeding max 20.0% threshold for sleep mode.")
        elif action_type == ActionType.REDUCE_GAIN:
            if t.traffic_utilization_pct > 75.0:
                qos_passed = False
                rejection_reasons.append(f"Traffic load ({t.traffic_utilization_pct}%) is too high for gain reduction without dropping packets.")

        checks.append(PolicyCheckItem(
            name="QoS Availability Guarantee (>= 99.99%)",
            required="Max 20.0% Traffic for Sleep / 75.0% for Eco",
            measured=f"Traffic Utilization: {t.traffic_utilization_pct}%",
            passed=qos_passed
        ))

        # 2. OSNR Check (Optical Signal-to-Noise Ratio)
        osnr_delta = -2.5 if action_type == ActionType.REDUCE_GAIN else (-1.0 if action_type == ActionType.SLEEP_TRANSPONDER else 0.0)
        projected_osnr = t.osnr_db + osnr_delta
        osnr_passed = projected_osnr >= 14.5

        if not osnr_passed:
            rejection_reasons.append(f"Projected OSNR after action is {projected_osnr:.2f} dB, which violates the minimum optical margin threshold of 14.5 dB.")

        checks.append(PolicyCheckItem(
            name="OSNR Optical Margin (>= 14.5 dB)",
            required=">= 14.5 dB",
            measured=f"Current: {t.osnr_db} dB (Projected: {projected_osnr:.2f} dB)",
            passed=osnr_passed
        ))

        # 3. BER Check (Pre-FEC Bit Error Rate)
        ber_passed = t.pre_fec_ber <= 1.0e-4
        if not ber_passed:
            rejection_reasons.append(f"Pre-FEC BER ({t.pre_fec_ber:.2e}) exceeds allowable threshold of 1.0e-4. Cannot alter power mode on degraded link.")

        checks.append(PolicyCheckItem(
            name="Pre-FEC Bit Error Rate (<= 1.0e-4)",
            required="<= 1.0e-4",
            measured=f"Pre-FEC BER: {t.pre_fec_ber:.2e}",
            passed=ber_passed
        ))

        # 4. Link Margin Check
        projected_link_margin = round(t.q_factor_db - 8.0, 2)
        link_margin_passed = projected_link_margin >= 2.5
        if not link_margin_passed:
            rejection_reasons.append(f"Link power budget margin ({projected_link_margin} dB) is lower than required safety margin of 2.5 dB.")

        checks.append(PolicyCheckItem(
            name="Link Margin Safety Buffer (>= 2.5 dB)",
            required=">= 2.5 dB",
            measured=f"Calculated Margin: {projected_link_margin} dB",
            passed=link_margin_passed
        ))

        # 5. SLA & Protection Path Check
        # Ensure redundant protection wavelength is online
        sla_passed = True
        if action_type in [ActionType.SLEEP_TRANSPONDER, ActionType.REROUTE_TRAFFIC]:
            # Simulate backup path check
            if "003" in device_id or "007" in device_id or "015" in device_id: # Specific simulated links lacking secondary protection
                sla_passed = False
                rejection_reasons.append("Secondary protection path on 1+1 Optical Subnetwork Connection (OSC) is currently unassigned or degraded.")

        checks.append(PolicyCheckItem(
            name="SLA 1+1 Protection Path Availability",
            required="Active Redundant Route Confirmed",
            measured="Protection Route Online" if sla_passed else "Protection Route Missing / Degraded",
            passed=sla_passed
        ))

        all_passed = all(c.passed for c in checks)
        reason_summary = " ".join(rejection_reasons) if not all_passed else ""

        return all_passed, checks, reason_summary

policy_engine = PolicyEngine()
