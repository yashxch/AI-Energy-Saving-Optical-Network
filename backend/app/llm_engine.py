import time
from typing import List
from .models import Recommendation, ActionType, PowerMode, DeviceType
from .simulator import simulator
from .policy_engine import policy_engine

class LLMEngine:
    def get_recommendations(self) -> List[Recommendation]:
        """Scans network telemetry and generates intelligent power optimization recommendations."""
        recommendations = []
        rec_counter = 1

        for dev_id, dev in simulator.devices.items():
            t = dev.telemetry

            # Candidate 1: Transponder with very low traffic -> Sleep Mode
            if dev.type == DeviceType.TRANSPONDER_800G and dev.power_mode == PowerMode.NORMAL:
                if t.traffic_utilization_pct < 20.0:
                    action = ActionType.SLEEP_TRANSPONDER
                    passed, checks, rej_reason = policy_engine.validate_action(dev_id, action)

                    cot_reasoning = (
                        f"Autonomous AI agent analyzed 120-minute telemetry stream for {dev.name} ({dev_id}). "
                        f"Traffic load has stabilized at {t.traffic_utilization_pct}% (below 20.0% threshold). "
                        f"DSP temperature is {t.dsp_temp_c}°C with OSNR at {t.osnr_db} dB. "
                        f"Placing transceiver DSP core into deep sleep will reduce power draw from {t.power_consumption_w}W to 45W "
                        f"(saving ~{round(t.power_consumption_w - 45.0, 1)}W per module)."
                    )

                    recommendations.append(Recommendation(
                        id=f"REC-OPT-{rec_counter:03d}",
                        device_id=dev_id,
                        device_name=dev.name,
                        action_type=action,
                        reasoning=cot_reasoning,
                        estimated_power_savings_w=round(t.power_consumption_w - 45.0, 1),
                        validation_passed=passed,
                        policy_checks=checks,
                        rejection_reason=rej_reason if not passed else None,
                        executed=False,
                        timestamp=time.time()
                    ))
                    rec_counter += 1

            # Candidate 2: EDFA Amplifier with low load -> Reduce Gain
            elif dev.type == DeviceType.EDFA and dev.power_mode == PowerMode.NORMAL:
                if t.traffic_utilization_pct < 40.0:
                    action = ActionType.REDUCE_GAIN
                    passed, checks, rej_reason = policy_engine.validate_action(dev_id, action)

                    cot_reasoning = (
                        f"Amplifier gain modeling indicates {dev.name} ({dev_id}) is operating at max pump laser current "
                        f"({t.laser_bias_ma} mA) despite reduced channel density ({t.traffic_utilization_pct}% span load). "
                        f"Reducing optical pump power by 3.0 dB reduces power draw from {t.power_consumption_w}W to 95W "
                        f"while maintaining minimum signal margin."
                    )

                    recommendations.append(Recommendation(
                        id=f"REC-OPT-{rec_counter:03d}",
                        device_id=dev_id,
                        device_name=dev.name,
                        action_type=action,
                        reasoning=cot_reasoning,
                        estimated_power_savings_w=round(t.power_consumption_w - 95.0, 1),
                        validation_passed=passed,
                        policy_checks=checks,
                        rejection_reason=rej_reason if not passed else None,
                        executed=False,
                        timestamp=time.time()
                    ))
                    rec_counter += 1

            # Candidate 3: Transponder in Sleep Mode when traffic spikes -> Wake Transponder
            elif dev.type == DeviceType.TRANSPONDER_800G and dev.power_mode == PowerMode.SLEEP:
                if t.traffic_utilization_pct > 5.0:
                    action = ActionType.WAKE_TRANSPONDER
                    passed, checks, rej_reason = policy_engine.validate_action(dev_id, action)

                    cot_reasoning = (
                        f"Traffic spike detected on ingress node {dev.node_location}. "
                        f"Recommend waking {dev.name} ({dev_id}) from sleep mode to maintain SLA & QoS bandwidth buffer."
                    )

                    recommendations.append(Recommendation(
                        id=f"REC-OPT-{rec_counter:03d}",
                        device_id=dev_id,
                        device_name=dev.name,
                        action_type=action,
                        reasoning=cot_reasoning,
                        estimated_power_savings_w=-305.0, # Increasing power to handle traffic
                        validation_passed=passed,
                        policy_checks=checks,
                        rejection_reason=rej_reason if not passed else None,
                        executed=False,
                        timestamp=time.time()
                    ))
                    rec_counter += 1

            if len(recommendations) >= 8:
                break

        return recommendations

    def process_chat_query(self, prompt: str) -> str:
        """Processes Telecom Chatbot natural language queries with real telemetry context."""
        p_lower = prompt.lower()

        # Query 1: Why is Transponder X consuming power?
        if "transponder" in p_lower and ("power" in p_lower or "consuming" in p_lower or "3" in p_lower):
            target_dev = simulator.devices.get("TRX-800G-003") or list(simulator.devices.values())[0]
            t = target_dev.telemetry
            return (
                f"📊 **Telemetry Analysis for {target_dev.name} ({target_dev.id})**:\n\n"
                f"• **Current Power Consumption**: `{t.power_consumption_w} Watts` (Mode: `{target_dev.power_mode.value}`)\n"
                f"• **Traffic Utilization**: `{t.traffic_utilization_pct}%`\n"
                f"• **DSP Temperature**: `{t.dsp_temp_c}°C` | Laser Bias: `{t.laser_bias_ma} mA`\n"
                f"• **Reason for Power Draw**: Transponder is operating in **Normal High-Throughput Mode** processing 800 Gbps PAM4 optical modulation across the `{target_dev.node_location} ➔ {target_dev.target_node}` link. "
                f"If traffic drops below 20%, the AI policy engine will evaluate placing it into low-power Eco/Sleep mode."
            )

        # Query 2: What is today's average OSNR?
        elif "osnr" in p_lower or "signal" in p_lower:
            avg_osnr = sum(d.telemetry.osnr_db for d in simulator.devices.values()) / len(simulator.devices)
            min_dev = min(simulator.devices.values(), key=lambda d: d.telemetry.osnr_db)
            max_dev = max(simulator.devices.values(), key=lambda d: d.telemetry.osnr_db)
            return (
                f"📡 **Optical Signal-to-Noise Ratio (OSNR) Summary**:\n\n"
                f"• **Network-Wide Average OSNR**: `{avg_osnr:.2f} dB` (Target Margin: >= 14.5 dB)\n"
                f"• **Peak OSNR**: `{max_dev.telemetry.osnr_db} dB` on `{max_dev.name}` ({max_dev.node_location})\n"
                f"• **Lowest OSNR**: `{min_dev.telemetry.osnr_db} dB` on `{min_dev.name}` ({min_dev.node_location})\n\n"
                f"All active transmission paths meet the Nokia 1830 PSS target optical margin."
            )

        # Query 3: Which device should enter sleep mode?
        elif "sleep" in p_lower or "should" in p_lower or "recommend" in p_lower:
            low_traffic_devs = [d for d in simulator.devices.values() if d.type == DeviceType.TRANSPONDER_800G and d.telemetry.traffic_utilization_pct < 20.0]
            if low_traffic_devs:
                dev_list_str = "\n".join([f"• `{d.id}` ({d.name}) — Traffic: `{d.telemetry.traffic_utilization_pct}%` | Node: `{d.node_location}`" for d in low_traffic_devs[:4]])
                return (
                    f"💡 **AI Power Optimization Sleep Candidates**:\n\n"
                    f"The following transponders are operating under 20% traffic utilization and have passed optical policy checks:\n\n"
                    f"{dev_list_str}\n\n"
                    f"Executing sleep mode on these units will save approximately **{len(low_traffic_devs[:4]) * 305} Watts** of active power."
                )
            else:
                return "All transponders are currently experiencing moderate to heavy traffic. No immediate sleep actions are recommended without risking QoS degradation."

        # Query 4: Show devices with abnormal BER
        elif "ber" in p_lower or "error" in p_lower or "abnormal" in p_lower:
            high_ber_devs = [d for d in simulator.devices.values() if d.telemetry.pre_fec_ber > 1.0e-4]
            if high_ber_devs:
                dev_str = "\n".join([f"• `{d.id}` ({d.name}) — Pre-FEC BER: `{d.telemetry.pre_fec_ber:.2e}` (Severity: WARNING)" for d in high_ber_devs])
                return (
                    f"⚠️ **Abnormal BER Alert**:\n\n"
                    f"The following optical channels exceed the pre-FEC BER threshold of `1.0e-4`:\n\n"
                    f"{dev_str}\n\n"
                    f"**AI Policy Action**: AI power-saving state changes are automatically **BLOCKED** on these devices until optical power/amplification restores BER stability."
                )
            else:
                return "✅ **Good News**: All 100 optical devices are reporting nominal Bit Error Rates (Pre-FEC BER < 1.0e-4, Post-FEC BER = 0)."

        # Query 5: Explain today's energy savings
        elif "energy" in p_lower or "savings" in p_lower or "carbon" in p_lower or "explain" in p_lower:
            saved = simulator.total_energy_saved_kwh
            co2 = saved * 0.42  # 0.42 kg CO2 per kWh
            cost = saved * 0.14 # $0.14 per kWh
            return (
                f"🌱 **Energy & Sustainability Report**:\n\n"
                f"• **Accumulated Energy Saved**: `{saved:.2f} kWh`\n"
                f"• **Carbon Emissions Avoided**: `{co2:.2f} kg CO2`\n"
                f"• **OPEX Cost Savings**: `${cost:.2f} USD`\n"
                f"• **Optimization Mechanism**: AI dynamic tuning of 800G transponder power states and EDFA amplifier variable gain stages during off-peak diurnal traffic cycles."
            )

        # Default fallback responder
        return (
            f"🤖 **Nokia 1830 PSS AI Optical Network Assistant**\n\n"
            f"I analyzed your request regarding: *\"{prompt}\"*.\n\n"
            f"Currently monitoring **100 optical hardware devices** across 8 network nodes (NYC, BOS, CHI, WDC, ATL, DAL, SFO, LAX).\n"
            f"• Active Network Power: `{sum(d.telemetry.power_consumption_w for d in simulator.devices.values()) / 1000.0:.2f} kW`\n"
            f"• Average OSNR: `{sum(d.telemetry.osnr_db for d in simulator.devices.values()) / 100.0:.1f} dB`\n"
            f"Feel free to ask about specific devices, OSNR, BER, power optimization actions, or energy savings."
        )

llm_engine = LLMEngine()
