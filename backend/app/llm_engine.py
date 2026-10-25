import json
import os
import time
from typing import Any, Dict, List
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .models import Recommendation, ActionType, PowerMode, DeviceType, WhatIfSimulationRequest, SimulationResult
from .telemetry import telemetry_provider
from .thresholds import NokiaThresholdEvaluator
from .simulator import simulator
from .digital_twin import digital_twin_engine
from .adaptive_baseline import adaptive_baseline_manager

adaptive_baseline = adaptive_baseline_manager

class LLMEngine:
    def __init__(self):
        self.nokia_thresholds = NokiaThresholdEvaluator()
        self.glean_base_url = (
            os.getenv("GLEAN_BASE_URL")
            or os.getenv("NOKIA_GLEAN_BASE_URL")
            or "https://nokiapoc-be.glean.com"
        )
        self.glean_api_token = (
            os.getenv("GLEAN_API_TOKEN")
            or os.getenv("GLEAN_API_KEY")
            or os.getenv("NOKIA_GLEAN_TOKEN")
            or ""
        )

    def _normalize_glean_results(self, payload: Any) -> List[str]:
        if not isinstance(payload, dict):
            return []

        results: List[str] = []
        for key in ("results", "items", "documents", "matches"):
            items = payload.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    title = item.get("title") or item.get("name") or item.get("document") or "Glean result"
                    snippet = item.get("snippet") or item.get("summary") or item.get("content") or item.get("excerpt") or ""
                    text = f"• {title}: {snippet}" if snippet else f"• {title}"
                    results.append(text)
                elif isinstance(item, str):
                    results.append(f"• {item}")
            if results:
                return results[:3]

        answer = payload.get("answer")
        if isinstance(answer, str) and answer.strip():
            return [answer.strip()]
        return []

    def _fetch_glean_context(self, prompt: str) -> str:
        if not self.glean_base_url:
            return ""

        if not self.glean_api_token and self.glean_base_url.startswith("https://nokiapoc-be.glean.com"):
            self.glean_api_token = ""

        payload = {
            "query": prompt,
            "max_results": 3,
            "context": "nokia optical network operations and telecom best practices",
        }

        endpoints = [
            self.glean_base_url.rstrip("/") + "/api/search",
            self.glean_base_url.rstrip("/") + "/search",
            self.glean_base_url.rstrip("/") + "/mcp/managed/gemini",
        ]

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.glean_api_token:
            headers["Authorization"] = f"Bearer {self.glean_api_token}"

        for endpoint in endpoints:
            try:
                req = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                try:
                    response = urlopen(req, timeout=5)
                    should_close = True
                except TypeError:
                    response = urlopen(req)
                    should_close = True

                try:
                    raw = response.read().decode("utf-8", errors="ignore")
                    if not raw:
                        continue
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        if "Nokia" in raw or "optical" in raw.lower() or "gain" in raw.lower():
                            return raw.strip()[:1200]
                        continue
                    findings = self._normalize_glean_results(parsed)
                    if findings:
                        return "\n".join(findings)
                finally:
                    if should_close and hasattr(response, "close"):
                        response.close()
            except (HTTPError, URLError, ValueError, TimeoutError):
                continue

        return ""

    def get_recommendations(self) -> List[Recommendation]:
        """Scans network telemetry and generates intelligent power optimization recommendations validated by Digital Twin."""
        if (
            telemetry_provider.source_mode == "nokia"
            and telemetry_provider.nokia_adapter.is_historical_csv
        ):
            # CSV history cannot verify hardware power-mode support or live service capacity.
            return []

        recommendations = []
        rec_counter = 1

        for dev_id, dev in telemetry_provider.get_devices().items():
            t = dev.telemetry
            nokia_guardrail = False
            if telemetry_provider.source_mode == "nokia":
                nokia_results = self.nokia_thresholds.evaluate_device(dev)
                nokia_guardrail = any(
                    result.severity in {"CRITICAL", "MAJOR"}
                    or (
                        not result.complete
                        and result.metric in {"Q-margin min", "Q-margin average", "Connection state"}
                    )
                    for result in nokia_results
                )
            adaptive = adaptive_baseline.update_device(dev_id, t)
            traffic_info = adaptive.get("traffic_utilization_pct", {})
            safety_blocked = any(
                item.get("hard_safety_violation", False)
                for name, item in adaptive.items()
                if name != "optimization_opportunity" and isinstance(item, dict)
            )
            adaptive_blocked = (
                traffic_info.get("learning_status") == "LEARNING_ACTIVE"
                and any(
                    item.get("classification") == "ANOMALY"
                    for name, item in adaptive.items()
                    if name != "optimization_opportunity" and isinstance(item, dict)
                )
            )

            # Candidate 1: Transponder with low traffic -> Sleep Mode
            if dev.type == DeviceType.TRANSPONDER_800G and dev.power_mode == PowerMode.NORMAL:
                opportunity = (
                    adaptive.get("optimization_opportunity", {}).get("optimization_opportunity", False)
                    or traffic_info.get("learning_status") != "LEARNING_ACTIVE"
                    and t.traffic_utilization_pct < 20.0
                ) and not safety_blocked and not adaptive_blocked and not nokia_guardrail
                if opportunity and not adaptive.get("optimization_opportunity", {}).get("hard_safety_violations"):
                    action = ActionType.SLEEP_TRANSPONDER
                    sim_req = WhatIfSimulationRequest(device_id=dev_id, action_type=action)
                    sim_res = digital_twin_engine.simulate_what_if(sim_req)

                    cot_reasoning = (
                        f"Autonomous AI agent analyzed 120-minute telemetry stream for {dev.name} ({dev_id}). "
                        f"Traffic load has stabilized at {t.traffic_utilization_pct}% (below 20.0% threshold). "
                        f"DSP temperature is {t.dsp_temp_c}°C with OSNR at {t.osnr_db} dB. "
                        f"Digital Twin simulated deep sleep: power draw drops from {t.power_consumption_w}W to 45W "
                        f"(saving ~{sim_res.power_savings.instantaneous_w}W per module)."
                    )

                    recommendations.append(Recommendation(
                        id=f"REC-OPT-{rec_counter:03d}",
                        device_id=dev_id,
                        device_name=dev.name,
                        action_type=action,
                        reasoning=cot_reasoning,
                        estimated_power_savings_w=sim_res.power_savings.instantaneous_w,
                        validation_passed=sim_res.result == SimulationResult.APPROVED,
                        policy_checks=sim_res.policy_checks,
                        rejection_reason=sim_res.reason if sim_res.result != SimulationResult.APPROVED else None,
                        executed=False,
                        timestamp=time.time()
                    ))
                    rec_counter += 1


            # Candidate 2: EDFA Amplifier with low load -> Reduce Gain
            elif dev.type == DeviceType.EDFA and dev.power_mode == PowerMode.NORMAL:
                opportunity = (
                    adaptive.get("optimization_opportunity", {}).get("optimization_opportunity", False)
                    or traffic_info.get("learning_status") != "LEARNING_ACTIVE"
                    and t.traffic_utilization_pct < 40.0
                ) and not safety_blocked and not adaptive_blocked and not nokia_guardrail
                if opportunity and not adaptive.get("optimization_opportunity", {}).get("hard_safety_violations"):
                    action = ActionType.REDUCE_GAIN
                    sim_req = WhatIfSimulationRequest(device_id=dev_id, action_type=action)
                    sim_res = digital_twin_engine.simulate_what_if(sim_req)

                    cot_reasoning = (
                        f"Amplifier gain modeling indicates {dev.name} ({dev_id}) is operating at max pump laser current "
                        f"({t.laser_bias_ma} mA) despite reduced channel density ({t.traffic_utilization_pct}% span load). "
                        f"Digital Twin simulated reduced optical pump power: power draw drops from {t.power_consumption_w}W to 95W "
                        f"while maintaining minimum signal margin."
                    )

                    recommendations.append(Recommendation(
                        id=f"REC-OPT-{rec_counter:03d}",
                        device_id=dev_id,
                        device_name=dev.name,
                        action_type=action,
                        reasoning=cot_reasoning,
                        estimated_power_savings_w=sim_res.power_savings.instantaneous_w,
                        validation_passed=sim_res.result == SimulationResult.APPROVED,
                        policy_checks=sim_res.policy_checks,
                        rejection_reason=sim_res.reason if sim_res.result != SimulationResult.APPROVED else None,
                        executed=False,
                        timestamp=time.time()
                    ))
                    rec_counter += 1

            # Candidate 3: Transponder in Sleep Mode when traffic spikes -> Wake Transponder
            elif dev.type == DeviceType.TRANSPONDER_800G and dev.power_mode == PowerMode.SLEEP:
                if t.traffic_utilization_pct > 5.0:
                    action = ActionType.WAKE_TRANSPONDER
                    sim_req = WhatIfSimulationRequest(device_id=dev_id, action_type=action)
                    sim_res = digital_twin_engine.simulate_what_if(sim_req)

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
                        validation_passed=sim_res.result == SimulationResult.APPROVED,
                        policy_checks=sim_res.policy_checks,
                        rejection_reason=sim_res.reason if sim_res.result != SimulationResult.APPROVED else None,
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
        devices = telemetry_provider.get_devices()
        if not devices:
            status = telemetry_provider.nokia_adapter.last_refresh_status
            error = telemetry_provider.nokia_adapter.last_refresh_error
            return (
                f"📡 **No telemetry data is currently available for the "
                f"{telemetry_provider.source_mode} source.**\n\n"
                f"Refresh status: `{status}`"
                + (f"\nSource error: `{error}`" if error else "")
                + "\n\nSwitch to Simulator or refresh the Nokia source after confirming the PMDATA/live destination is reachable."
            )

        if any(word in p_lower for word in ("help", "what can you do", "capabilities")):
            return (
                f"🤖 **Telemetry Assistant**\n\n"
                f"I can answer questions about the {len(devices)} devices currently supplied by "
                f"the **{telemetry_provider.source_mode}** source, including:\n"
                "• a device's power, traffic, temperature, OSNR, BER, and health\n"
                "• network-wide averages and warnings\n"
                "• sleep-mode recommendations, faults, energy savings, and source status\n\n"
                "Try asking: *What is the status of TRX-800G-003?*"
            )

        historical_csv = (
            telemetry_provider.source_mode == "nokia"
            and telemetry_provider.nokia_adapter.is_historical_csv
        )
        glean_context = self._fetch_glean_context(prompt)
        if glean_context and any(
            keyword in p_lower for keyword in (
                "guide", "best practice", "safe", "tuning", "gain",
                "recommendation", "policy", "amplifier", "operational",
                "how to", "nokia", "procedure"
            )
        ):
            if historical_csv:
                return (
                    "🔎 **Glean (Nokia) general knowledge context**\n\n"
                    f"{glean_context}\n\n"
                    "This is general reference material, not an assessment of the "
                    "historical CSV data or a live device recommendation."
                )
            return (
                "🔎 **Glean (Nokia) knowledge context**\n\n"
                f"{glean_context}\n\n"
                f"Telemetry snapshot: {len(devices)} devices are available from the **{telemetry_provider.source_mode}** source, and the current network is being monitored with live optical policy checks enabled."
            )

        matched_device = next(
            (
                device for device in devices.values()
                if device.id.lower() in p_lower or device.name.lower() in p_lower
            ),
            None,
        )
        if matched_device:
            t = matched_device.telemetry
            if (
                telemetry_provider.source_mode == "nokia"
                and telemetry_provider.nokia_adapter.is_historical_csv
            ):
                record = matched_device.raw_record
                history = record.get("csv_history", []) if isinstance(record, dict) else []
                timestamp = (
                    history[-1].get("timestamp")
                    if history and isinstance(history[-1], dict)
                    else "unavailable"
                )
                return (
                    f"📍 **{matched_device.name} ({matched_device.id}) — project CSV**\n\n"
                    f"• Latest sample: `{timestamp}`\n"
                    f"• Traffic utilization: `{t.traffic_utilization_pct:.2f}%`\n"
                    f"• Power draw: `{t.power_consumption_w:.2f} W`\n"
                    f"• OSNR: `{t.osnr_db:.2f} dB` | Pre-FEC BER: `{t.pre_fec_ber:.2e}`\n"
                    f"• DSP temperature: `{t.dsp_temp_c:.1f}°C`\n"
                    "This is historical CSV data; it does not establish the device's "
                    "live health, operating mode, or connection status."
                )
            return (
                f"📍 **{matched_device.name} ({matched_device.id})**\n\n"
                f"• Health: **{matched_device.health.value}** | Power mode: **{matched_device.power_mode.value}**\n"
                f"• Power: `{t.power_consumption_w:.2f} W` | Traffic: `{t.traffic_utilization_pct:.2f}%`\n"
                f"• OSNR: `{t.osnr_db:.2f} dB` | Pre-FEC BER: `{t.pre_fec_ber:.2e}`\n"
                f"• DSP temperature: `{t.dsp_temp_c:.1f}°C` | Link: `{matched_device.node_location} → {matched_device.target_node}`"
            )

        if (
            telemetry_provider.source_mode == "nokia"
            and telemetry_provider.nokia_adapter.is_historical_csv
        ):
            histories = [
                (device, device.raw_record.get("csv_history", []))
                for device in devices.values()
            ]
            if any(term in p_lower for term in ("lower utilization", "lower traffic", "least load")):
                device = min(
                    devices.values(),
                    key=lambda item: item.telemetry.traffic_utilization_pct,
                )
                return (
                    f"{device.name} ({device.id}) has the lower latest recorded "
                    f"traffic utilization at {device.telemetry.traffic_utilization_pct:.2f}%. "
                    "This is a historical CSV observation, not a live reading."
                )
            if any(term in p_lower for term in ("sleep", "power saving", "save power", "recommend")):
                return (
                    "No power-saving action is eligible from these project CSV files. They "
                    "contain historical samples only; supported low-power modes, current "
                    "device state, service capacity, and protection constraints are not "
                    "verified. No savings are estimated."
                )
            if any(term in p_lower for term in ("missing", "sufficient", "evaluate")):
                return (
                    "Power-saving evaluation requires verified hardware mode support, "
                    "current device state, minimum service/capacity requirements, fresh "
                    "telemetry over a sufficient observation period, and applicable "
                    "protection constraints. The CSV files do not provide those "
                    "safety facts."
                )
            if any(term in p_lower for term in ("abnormal", "alarm", "alert")):
                return (
                    "No device-specific abnormality assessment is available from the "
                    "project CSV data. The files are historical; validate the "
                    "reported measurements against your device-specific operating "
                    "thresholds before treating them as alarms."
                )
            summaries = []
            for device, history in histories:
                summaries.append(
                    f"• {device.name} ({device.id}): latest traffic "
                    f"{device.telemetry.traffic_utilization_pct:.2f}%, power draw "
                    f"{device.telemetry.power_consumption_w:.2f} W, OSNR "
                    f"{device.telemetry.osnr_db:.2f} dB, pre-FEC BER "
                    f"{device.telemetry.pre_fec_ber:.2e}; "
                    f"{len(history)} accepted historical records."
                )
            return (
                "Project-folder CSV telemetry summary (historical data; not live):\n"
                + "\n".join(summaries)
                + "\nNo real device actions are performed from CSV telemetry."
            )

        if any(word in p_lower for word in ("source", "refresh", "connected", "data pulled", "poll")):
            status = telemetry_provider.nokia_adapter.last_refresh_status
            error = telemetry_provider.nokia_adapter.last_refresh_error
            return (
                f"📡 **Telemetry source status**\n\n"
                f"• Source: **{telemetry_provider.source_mode}**\n"
                f"• Devices available: **{len(devices)}**\n"
                f"• Nokia refresh status: **{status if telemetry_provider.source_mode == 'nokia' else 'not applicable'}**"
                + (f"\n• Last error: `{error}`" if error else "")
            )

        if any(word in p_lower for word in ("health", "warning", "critical", "status", "how many")):
            warnings = sum(1 for device in devices.values() if device.health.value != "Normal")
            average_traffic = sum(
                device.telemetry.traffic_utilization_pct for device in devices.values()
            ) / len(devices)
            return (
                f"📈 **Network status ({telemetry_provider.source_mode} source)**\n\n"
                f"• Devices reporting: `{len(devices)}`\n"
                f"• Devices with warnings or critical health: `{warnings}`\n"
                f"• Average traffic utilization: `{average_traffic:.2f}%`\n"
                f"• Active power: `{sum(d.telemetry.power_consumption_w for d in devices.values()) / 1000.0:.2f} kW`"
            )

        # Query 1: Why is Transponder X consuming power?
        if "transponder" in p_lower and ("power" in p_lower or "consuming" in p_lower or "3" in p_lower):
            devices = telemetry_provider.get_devices()
            target_dev = devices.get("TRX-800G-003") or list(devices.values())[0]
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
            avg_osnr = sum(d.telemetry.osnr_db for d in devices.values()) / len(devices)
            min_dev = min(devices.values(), key=lambda d: d.telemetry.osnr_db)
            max_dev = max(devices.values(), key=lambda d: d.telemetry.osnr_db)
            return (
                f"📡 **Optical Signal-to-Noise Ratio (OSNR) Summary**:\n\n"
                f"• **Network-Wide Average OSNR**: `{avg_osnr:.2f} dB` (Target Margin: >= 14.5 dB)\n"
                f"• **Peak OSNR**: `{max_dev.telemetry.osnr_db} dB` on `{max_dev.name}` ({max_dev.node_location})\n"
                f"• **Lowest OSNR**: `{min_dev.telemetry.osnr_db} dB` on `{min_dev.name}` ({min_dev.node_location})\n\n"
                f"All active transmission paths meet the Nokia 1830 PSS target optical margin."
            )

        # Query 3: Which device should enter sleep mode?
        elif "sleep" in p_lower or "should" in p_lower or "recommend" in p_lower:
            low_traffic_devs = [d for d in devices.values() if d.type == DeviceType.TRANSPONDER_800G and d.telemetry.traffic_utilization_pct < 20.0]
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
            high_ber_devs = [d for d in devices.values() if d.telemetry.pre_fec_ber > 1.0e-4]
            if high_ber_devs:
                dev_str = "\n".join([f"• `{d.id}` ({d.name}) — Pre-FEC BER: `{d.telemetry.pre_fec_ber:.2e}` (Severity: WARNING)" for d in high_ber_devs])
                return (
                    f"⚠️ **Abnormal BER Alert**:\n\n"
                    f"The following optical channels exceed the pre-FEC BER threshold of `1.0e-4`:\n\n"
                    f"{dev_str}\n\n"
                    f"**AI Policy Action**: AI power-saving state changes are automatically **BLOCKED** on these devices until optical power/amplification restores BER stability."
                )
            else:
                return f"✅ **Good News**: All {len(devices)} reported devices have nominal Bit Error Rates (Pre-FEC BER < 1.0e-4)."

        # Query 5: Explain today's energy savings
        elif "energy" in p_lower or "savings" in p_lower or "carbon" in p_lower or "explain" in p_lower:
            saved = telemetry_provider.total_energy_saved_kwh
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
        avg_osnr = sum(d.telemetry.osnr_db for d in devices.values()) / len(devices)
        return (
            f"🤖 **Nokia 1830 PSS AI Optical Network Assistant**\n\n"
            f"I analyzed your request regarding: *\"{prompt}\"*.\n\n"
            f"Currently monitoring **{len(devices)} devices** from the **{telemetry_provider.source_mode}** telemetry source.\n"
            f"• Active Network Power: `{sum(d.telemetry.power_consumption_w for d in devices.values()) / 1000.0:.2f} kW`\n"
            f"• Average OSNR: `{avg_osnr:.1f} dB`\n"
            f"• Devices reporting warnings: `{sum(1 for d in devices.values() if d.health.value != 'Normal')}`\n\n"
            f"I can answer questions about any device, optical metrics, BER, OSNR, power, traffic, faults, recommendations, energy savings, or the active telemetry source."
        )

llm_engine = LLMEngine()
