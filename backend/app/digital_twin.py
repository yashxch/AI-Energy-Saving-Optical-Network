import time
import copy
import uuid
import networkx as nx
from typing import Dict, List, Optional, Tuple, Any

from .models import (
    Device, DeviceType, PowerMode, HealthState, PolicyCheckItem, ActionType,
    SyncStatus, SimulationResult, DigitalTwinDevice, DigitalTwinGraphNode,
    DigitalTwinGraphEdge, DigitalTwinTopologyGraph, DigitalTwinStateSummary,
    PowerSavingsMetric, WhatIfSimulationRequest, WhatIfSimulationResponse,
    SimulationHistoryItem, DemoScenarioInfo
)
from .simulator import NODES
from .telemetry import telemetry_provider
from .policy_engine import policy_engine

class DigitalTwinEngine:
    """
    Centralized, lightweight Digital Twin Engine for Optical Networks.
    Provides real-time state synchronization, NetworkX graph topology modeling,
    on-demand What-If simulation, configurable policy validation, and audit logging.
    Scheduled synchronization acts as the single source of truth, with cached state
    returned for API calls and on-demand synchronization triggered only when stale.
    """
    def __init__(self, stale_threshold_sec: float = 2.0):
        self.device_states: Dict[str, DigitalTwinDevice] = {}
        self.graph = nx.DiGraph()
        self.last_sync_timestamp: float = 0.0
        self.stale_threshold_sec: float = stale_threshold_sec
        self.cached_summary: Optional[DigitalTwinStateSummary] = None
        self.cached_topology: Optional[DigitalTwinTopologyGraph] = None
        self.simulation_history: List[SimulationHistoryItem] = []
        self._init_digital_twin()

    def _init_digital_twin(self):
        """Initializes twin state objects and NetworkX graph topology."""
        self.synchronize()

    def is_stale(self, threshold_sec: Optional[float] = None) -> bool:
        """Checks if the cached Digital Twin state is stale or uninitialized."""
        if self.cached_summary is None or not self.device_states:
            return True
        timeout = threshold_sec if threshold_sec is not None else self.stale_threshold_sec
        return (time.time() - self.last_sync_timestamp) >= timeout

    def ensure_synced(self, force: bool = False, threshold_sec: Optional[float] = None) -> DigitalTwinStateSummary:
        """
        On-demand synchronization check.
        Only triggers state synchronization if the cached twin state is stale or force=True.
        Otherwise, returns the cached state summary immediately with zero overhead.
        """
        if force or self.is_stale(threshold_sec):
            return self.synchronize()
        return self.cached_summary

    def synchronize(self) -> DigitalTwinStateSummary:
        """
        Real-time event/interval-driven synchronization from existing simulator telemetry.
        Only updates changed fields and maintains telemetry freshness timestamps.
        """
        now = time.time()
        stale_timeout = policy_engine.config.get("telemetry_stale_timeout_sec", 5.0)

        # 1. Update lightweight device twin states
        synced_count = 0
        stale_count = 0
        offline_count = 0
        active_count = 0
        sleep_count = 0

        current_devices = telemetry_provider.get_devices()
        for stale_device_id in self.device_states.keys() - current_devices.keys():
            del self.device_states[stale_device_id]

        for dev_id, dev in current_devices.items():
            t = dev.telemetry
            freshness = round(now - t.timestamp, 2)
            
            # Determine sync status
            if dev.health == HealthState.CRITICAL:
                sync_st = SyncStatus.OFFLINE
                offline_count += 1
            elif freshness > stale_timeout:
                sync_st = SyncStatus.STALE
                stale_count += 1
            else:
                sync_st = SyncStatus.SYNCED
                synced_count += 1

            # Determine device status string
            if dev.power_mode == PowerMode.SLEEP:
                status_str = "SLEEP"
                sleep_count += 1
            elif dev.power_mode == PowerMode.LOW_GAIN or dev.power_mode == PowerMode.ECO:
                status_str = dev.power_mode.value.upper()
                active_count += 1
            elif dev.health == HealthState.WARNING:
                status_str = "WARNING"
                active_count += 1
            elif dev.health == HealthState.CRITICAL:
                status_str = "CRITICAL"
            else:
                status_str = "ACTIVE"
                active_count += 1

            capacity = 800.0 if dev.type == DeviceType.TRANSPONDER_800G else (
                4000.0 if dev.type == DeviceType.ROADM else 1600.0
            )

            # Assign primary vs backup protection role
            idx = int(dev_id.split("-")[-1]) if dev_id.split("-")[-1].isdigit() else 1
            protection_role = "backup" if idx % 4 == 0 else "primary"

            twin_dev = DigitalTwinDevice(
                device_id=dev_id,
                name=dev.name,
                type=dev.type,
                status=status_str,
                power_mode=dev.power_mode,
                node_location=dev.node_location,
                target_node=dev.target_node,
                traffic_utilization_pct=t.traffic_utilization_pct,
                power_consumption_w=t.power_consumption_w,
                tx_power_dbm=t.tx_power_dbm,
                rx_power_dbm=t.rx_power_dbm,
                osnr_db=t.osnr_db,
                ber=t.ber,
                pre_fec_ber=t.pre_fec_ber,
                q_factor_db=t.q_factor_db,
                temperature_c=t.dsp_temp_c,
                capacity_gbps=capacity,
                protection_role=protection_role,
                last_updated=t.timestamp,
                sync_status=sync_st,
                telemetry_freshness_sec=freshness
            )

            self.device_states[dev_id] = twin_dev

        self.last_sync_timestamp = now
        self._build_networkx_graph()

        # Power metrics
        baseline_kw = telemetry_provider.baseline_power_kw
        current_kw = sum(d.power_consumption_w for d in self.device_states.values()) / 1000.0
        instant_savings_w = max(0.0, (baseline_kw - current_kw) * 1000.0)
        daily_kwh = (instant_savings_w / 1000.0) * 24.0
        monthly_kwh = daily_kwh * 30.0
        savings_pct = max(0.0, ((baseline_kw - current_kw) / baseline_kw) * 100.0) if baseline_kw else 0.0
        co2_factor = policy_engine.config.get("co2_kg_per_kwh", 0.42)
        co2_kg = round(daily_kwh * co2_factor, 2)

        health_str = "EXCELLENT" if offline_count == 0 and stale_count < 5 else (
            "DEGRADED" if offline_count < 3 else "CRITICAL"
        )

        overall_sync = SyncStatus.SYNCED if stale_count < 10 and offline_count == 0 else (
            SyncStatus.STALE if offline_count == 0 else SyncStatus.OFFLINE
        )

        self.cached_summary = DigitalTwinStateSummary(
            total_devices=len(self.device_states),
            active_devices=active_count,
            sleeping_devices=sleep_count,
            devices_under_simulation=0,
            synchronized_devices=synced_count,
            stale_devices=stale_count,
            offline_devices=offline_count,
            network_health=health_str,
            sync_status=overall_sync,
            last_sync_timestamp=now,
            baseline_power_kw=baseline_kw,
            current_power_kw=round(current_kw, 2),
            instantaneous_savings_w=round(instant_savings_w, 1),
            estimated_daily_savings_kwh=round(daily_kwh, 2),
            estimated_monthly_savings_kwh=round(monthly_kwh, 2),
            savings_percentage=round(savings_pct, 1),
            co2_reduction_kg=co2_kg
        )

        self._refresh_cached_topology()
        return self.cached_summary

    def _build_networkx_graph(self):
        """Constructs NetworkX DiGraph representing physical nodes, device interfaces, and optical links."""
        self.graph.clear()

        # Add network nodes
        for node in NODES:
            self.graph.add_node(node, type="NetworkNode", location=node, active=True)

        # Add link edges between adjacent nodes
        topo_state = telemetry_provider.topology_engine.get_topology_state()
        for link in topo_state["links"]:
            src = link["src"]
            dst = link["dst"]
            dist = link["distance_km"]
            active = link["active"]

            # Calculate link utilization from associated transponders
            transponders_on_link = [
                d for d in self.device_states.values()
                if d.type == DeviceType.TRANSPONDER_800G and d.node_location == src and d.target_node == dst
            ]
            if transponders_on_link:
                avg_util = sum(d.traffic_utilization_pct for d in transponders_on_link) / len(transponders_on_link)
                avg_osnr = sum(d.osnr_db for d in transponders_on_link) / len(transponders_on_link)
            else:
                avg_util = 25.0
                avg_osnr = 26.5

            total_cap = 4000.0  # 4 Tbps link capacity
            avail_bw = max(0.0, total_cap * (1.0 - (avg_util / 100.0)))

            self.graph.add_edge(
                src, dst,
                capacity_gbps=total_cap,
                available_bandwidth_gbps=round(avail_bw, 1),
                distance_km=dist,
                osnr_margin_db=round(avg_osnr - 14.5, 2),
                utilization_pct=round(avg_util, 1),
                protection_relationship="1+1 Optical Subnetwork Connection",
                active=active
            )

    def _refresh_cached_topology(self):
        """Constructs Pydantic topology graph from the current NetworkX graph."""
        nodes_list = []
        for n, data in self.graph.nodes(data=True):
            nodes_list.append(DigitalTwinGraphNode(
                id=n,
                name=f"Optical Node {n}",
                node_type=data.get("type", "NetworkNode"),
                location=n,
                status="ACTIVE" if data.get("active", True) else "OFFLINE",
                active=data.get("active", True)
            ))

        edges_list = []
        for u, v, data in self.graph.edges(data=True):
            edges_list.append(DigitalTwinGraphEdge(
                source=u,
                target=v,
                capacity_gbps=data.get("capacity_gbps", 4000.0),
                available_bandwidth_gbps=data.get("available_bandwidth_gbps", 3000.0),
                distance_km=data.get("distance_km", 250.0),
                osnr_margin_db=data.get("osnr_margin_db", 12.0),
                utilization_pct=data.get("utilization_pct", 25.0),
                protection_relationship=data.get("protection_relationship", "1+1 Redundant"),
                active=data.get("active", True)
            ))

        self.cached_topology = DigitalTwinTopologyGraph(
            nodes=nodes_list,
            edges=edges_list,
            total_nodes=len(nodes_list),
            total_edges=len(edges_list)
        )

    def get_state_summary(self, force: bool = False) -> DigitalTwinStateSummary:
        """Returns cached Digital Twin state summary, synchronizing on-demand only if stale."""
        return self.ensure_synced(force=force)

    def get_devices(self, force: bool = False) -> List[DigitalTwinDevice]:
        """Returns cached list of Digital Twin devices, synchronizing on-demand only if stale."""
        self.ensure_synced(force=force)
        return list(self.device_states.values())

    def get_device(self, device_id: str, force: bool = False) -> Optional[DigitalTwinDevice]:
        """Returns cached Digital Twin device by ID, synchronizing on-demand only if stale."""
        self.ensure_synced(force=force)
        return self.device_states.get(device_id)

    def get_topology_graph(self, force: bool = False) -> DigitalTwinTopologyGraph:
        """Returns Pydantic representation of the NetworkX graph for API/UI, synchronizing on-demand only if stale."""
        self.ensure_synced(force=force)
        if self.cached_topology is None:
            self._refresh_cached_topology()
        return self.cached_topology

    def simulate_what_if(self, req: WhatIfSimulationRequest) -> WhatIfSimulationResponse:
        """
        Executes an on-demand What-If simulation on a temporary, cloned Digital Twin state.
        Calculates traffic redistribution, link capacity, optical margins, protection path utilization,
        validates against policy configuration, and discards the temporary state.
        Uses cached Digital Twin state, synchronizing on-demand only if stale.
        """
        self.ensure_synced()
        target_dev = self.device_states.get(req.device_id)

        if not target_dev:
            return WhatIfSimulationResponse(
                simulation_id=f"SIM-{uuid.uuid4().hex[:6]}",
                timestamp=time.time(),
                device_id=req.device_id,
                device_name="Unknown Device",
                action_type=req.action_type,
                result=SimulationResult.REJECTED,
                reason=f"Device {req.device_id} not found in Digital Twin state inventory.",
                current_state={},
                simulated_state={},
                policy_checks=[],
                power_savings=PowerSavingsMetric(instantaneous_w=0.0, daily_kwh=0.0, monthly_kwh=0.0, percentage_reduction=0.0, co2_reduction_kg=0.0),
                traffic_redistribution={},
                discarded=True
            )

        # 1. Clone temporary Digital Twin state (TEMPORARY COPY)
        temp_device_state = copy.deepcopy(target_dev)
        temp_graph = copy.deepcopy(self.graph)

        # Fail-safe check 1: Stale or offline telemetry
        if target_dev.sync_status == SyncStatus.STALE:
            return WhatIfSimulationResponse(
                simulation_id=f"SIM-{uuid.uuid4().hex[:6]}",
                timestamp=time.time(),
                device_id=target_dev.device_id,
                device_name=target_dev.name,
                action_type=req.action_type,
                result=SimulationResult.REQUIRES_OPERATOR_APPROVAL,
                reason="FAIL-SAFE TRIGGERED: Telemetry for this device is STALE. Automatic validation blocked; operator review required.",
                current_state=target_dev.dict(),
                simulated_state=target_dev.dict(),
                policy_checks=[],
                power_savings=PowerSavingsMetric(instantaneous_w=0.0, daily_kwh=0.0, monthly_kwh=0.0, percentage_reduction=0.0, co2_reduction_kg=0.0),
                traffic_redistribution={},
                discarded=True
            )

        # 2. Apply simulated action to temporary clone
        curr_power = temp_device_state.power_consumption_w
        curr_traffic = temp_device_state.traffic_utilization_pct
        curr_osnr = temp_device_state.osnr_db

        if req.action_type == ActionType.SLEEP_TRANSPONDER:
            sim_power = req.custom_power_w if req.custom_power_w is not None else 45.0
            sim_traffic = 0.0
            sim_status = "SLEEP"
            sim_power_mode = PowerMode.SLEEP
            sim_osnr = max(10.0, curr_osnr - 0.8)
        elif req.action_type == ActionType.REDUCE_GAIN:
            sim_power = req.custom_power_w if req.custom_power_w is not None else 95.0
            sim_traffic = min(curr_traffic, 25.0)
            sim_status = "LOW_GAIN"
            sim_power_mode = PowerMode.LOW_GAIN
            sim_osnr = max(10.0, curr_osnr - 2.5)
        elif req.action_type in [ActionType.WAKE_TRANSPONDER, ActionType.RESTORE_DEVICE]:
            sim_power = 350.0 if temp_device_state.type == DeviceType.TRANSPONDER_800G else 160.0
            sim_traffic = max(curr_traffic, 45.0)
            sim_status = "ACTIVE"
            sim_power_mode = PowerMode.NORMAL
            sim_osnr = round(curr_osnr + 1.2, 2)
        else: # REROUTE_TRAFFIC or DISABLE_WAVELENGTH
            sim_power = 45.0
            sim_traffic = 0.0
            sim_status = "SLEEP"
            sim_power_mode = PowerMode.SLEEP
            sim_osnr = curr_osnr

        sim_telemetry = {
            "traffic_utilization_pct": curr_traffic,  # Evaluate current load before sleeping
            "power_consumption_w": sim_power,
            "osnr_db": curr_osnr,
            "pre_fec_ber": temp_device_state.pre_fec_ber,
            "q_factor_db": temp_device_state.q_factor_db
        }

        # 3. Simulate Traffic Redistribution & Protection Path Utilization on Temporary Graph
        src_node = temp_device_state.node_location
        dst_node = temp_device_state.target_node
        
        # Calculate backup route utilization
        protection_util = 42.0
        protection_avail = True

        if temp_graph.has_edge(src_node, dst_node):
            edge_data = temp_graph[src_node][dst_node]
            curr_util = edge_data.get("utilization_pct", 25.0)
            if req.action_type == ActionType.SLEEP_TRANSPONDER:
                # Offload traffic to protection path
                protection_util = round(curr_util + (curr_traffic * 0.8), 1)
                if temp_device_state.device_id in ["TRX-800G-003", "TRX-800G-007", "TRX-800G-015"]:
                    protection_avail = False

        # 4. Policy Engine Validation on Simulated Parameters
        passed, policy_checks, rej_reason = policy_engine.validate_action(
            device_id=temp_device_state.device_id,
            action_type=req.action_type,
            sim_telemetry=sim_telemetry,
            protection_path_util_pct=protection_util,
            protection_available=protection_avail
        )

        result_enum = SimulationResult.APPROVED if passed else SimulationResult.REJECTED

        # 5. Power Savings Calculation
        saved_w = round(curr_power - sim_power, 1)
        daily_kwh = round((max(0.0, saved_w) / 1000.0) * 24.0, 2)
        monthly_kwh = round(daily_kwh * 30.0, 2)
        pct_reduction = round((saved_w / curr_power * 100.0) if curr_power > 0 else 0.0, 1)
        co2_factor = policy_engine.config.get("co2_kg_per_kwh", 0.42)
        co2_kg = round(daily_kwh * co2_factor, 2)

        power_metrics = PowerSavingsMetric(
            instantaneous_w=saved_w,
            daily_kwh=daily_kwh,
            monthly_kwh=monthly_kwh,
            percentage_reduction=pct_reduction,
            co2_reduction_kg=co2_kg
        )

        sim_state_dict = temp_device_state.dict()
        sim_state_dict.update({
            "status": sim_status,
            "power_mode": sim_power_mode,
            "power_consumption_w": sim_power,
            "traffic_utilization_pct": sim_traffic,
            "osnr_db": sim_osnr
        })

        traffic_redistribution_summary = {
            "source_node": src_node,
            "target_node": dst_node,
            "offloaded_traffic_gbps": round(800.0 * (curr_traffic / 100.0), 1) if req.action_type == ActionType.SLEEP_TRANSPONDER else 0.0,
            "protection_path_utilization_pct": protection_util,
            "protection_path_status": "OK" if protection_util <= 85.0 and protection_avail else "OVERLOADED / MISSING"
        }

        # Detailed explainability string
        if passed:
            reason_str = (
                f"APPROVED: {target_dev.device_id} ({target_dev.name}) can enter {sim_status} mode. "
                f"Traffic load ({curr_traffic}%) is below maximum threshold ({policy_engine.config.get('sleep_max_traffic_pct')}%), "
                f"OSNR margin ({curr_osnr} dB) is sufficient, protection path utilization ({protection_util}%) remains within safe limits, "
                f"and estimated energy saving is {saved_w} W."
            )
        else:
            reason_str = f"REJECTED: {rej_reason}"

        sim_id = f"SIM-{uuid.uuid4().hex[:6].upper()}"

        # Audit History Logging (Lightweight record)
        history_item = SimulationHistoryItem(
            id=sim_id,
            timestamp=time.strftime("%H:%M:%S"),
            device_id=target_dev.device_id,
            device_name=target_dev.name,
            action_type=req.action_type.value,
            result=result_enum.value,
            energy_saving_w=saved_w,
            reason=reason_str
        )
        self.simulation_history.insert(0, history_item)
        if len(self.simulation_history) > 50:
            self.simulation_history.pop()

        # 6. Return response (Temporary clone discarded when method scope ends!)
        return WhatIfSimulationResponse(
            simulation_id=sim_id,
            timestamp=time.time(),
            device_id=target_dev.device_id,
            device_name=target_dev.name,
            action_type=req.action_type,
            result=result_enum,
            reason=reason_str,
            current_state=target_dev.dict(),
            simulated_state=sim_state_dict,
            policy_checks=policy_checks,
            power_savings=power_metrics,
            traffic_redistribution=traffic_redistribution_summary,
            discarded=True
        )

    def validate_quantum_solution(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a complete quantum-optimization solution as one
        temporary Digital Twin scenario.

        Each action is applied to a deep-copied device state. The real
        simulator and persistent Digital Twin state are never modified.

        Parameters
        ----------
        actions:
            List of dictionaries containing:
              {
                  "device_id": "...",
                  "action_type": ActionType.SLEEP_TRANSPONDER
              }

        Returns
        -------
        Dict containing per-device validation, aggregate savings,
        and an overall APPROVED/REJECTED result.
        """

        self.ensure_synced()

        if not actions:
            return {
                "status": "REJECTED",
                "all_actions_approved": False,
                "action_count": 0,
                "approved_count": 0,
                "total_power_saving_w": 0.0,
                "total_power_saving_kw": 0.0,
                "actions": [],
                "state_changed": False,
                "temporary_state_discarded": True,
                "reason": "No quantum actions were supplied."
            }

        # Protect the existing twin state.
        temp_devices = copy.deepcopy(self.device_states)
        temp_graph = copy.deepcopy(self.graph)

        results = []
        all_approved = True
        total_saving_w = 0.0

        # Track affected links so simultaneous actions can be reflected
        # in the temporary topology before the final validation summary.
        affected_links = {}

        for action in actions:
            device_id = action.get("device_id")
            action_type = action.get("action_type")

            if isinstance(action_type, str):
                try:
                    action_type = ActionType(action_type)
                except ValueError:
                    results.append({
                        "device_id": device_id,
                        "action": str(action_type),
                        "result": "REJECTED",
                        "saving_w": 0.0,
                        "reason": f"Unsupported action type: {action_type}"
                    })
                    all_approved = False
                    continue

            device = temp_devices.get(device_id)

            if device is None:
                results.append({
                    "device_id": device_id,
                    "action": (
                        action_type.value
                        if isinstance(action_type, ActionType)
                        else str(action_type)
                    ),
                    "result": "REJECTED",
                    "saving_w": 0.0,
                    "reason": f"Device {device_id} not found in Digital Twin state."
                })
                all_approved = False
                continue

            if device.sync_status in [SyncStatus.STALE, SyncStatus.OFFLINE]:
                result_name = (
                    "REQUIRES_OPERATOR_APPROVAL"
                    if device.sync_status == SyncStatus.STALE
                    else "REJECTED"
                )
                results.append({
                    "device_id": device_id,
                    "action": action_type.value,
                    "result": result_name,
                    "saving_w": 0.0,
                    "reason": (
                        "Telemetry is stale; automatic validation is blocked."
                        if device.sync_status == SyncStatus.STALE
                        else "Device telemetry is offline; validation is blocked."
                    )
                })
                all_approved = False
                continue

            current_power = device.power_consumption_w
            current_traffic = device.traffic_utilization_pct
            current_osnr = device.osnr_db

            if action_type == ActionType.SLEEP_TRANSPONDER:
                if device.type != DeviceType.TRANSPONDER_800G:
                    results.append({
                        "device_id": device_id,
                        "action": action_type.value,
                        "result": "REJECTED",
                        "saving_w": 0.0,
                        "reason": "SLEEP_TRANSPONDER is only valid for 800G transponders."
                    })
                    all_approved = False
                    continue

                simulated_power = 45.0
                simulated_traffic = 0.0
                simulated_osnr = max(10.0, current_osnr - 0.8)

            elif action_type == ActionType.REDUCE_GAIN:
                if device.type != DeviceType.EDFA:
                    results.append({
                        "device_id": device_id,
                        "action": action_type.value,
                        "result": "REJECTED",
                        "saving_w": 0.0,
                        "reason": "REDUCE_GAIN is only valid for EDFAs."
                    })
                    all_approved = False
                    continue

                simulated_power = 95.0
                simulated_traffic = min(current_traffic, 25.0)
                simulated_osnr = max(10.0, current_osnr - 2.5)

            else:
                results.append({
                    "device_id": device_id,
                    "action": action_type.value,
                    "result": "REJECTED",
                    "saving_w": 0.0,
                    "reason": (
                        "Combined quantum validation currently supports "
                        "SLEEP_TRANSPONDER and REDUCE_GAIN only."
                    )
                })
                all_approved = False
                continue

            src_node = device.node_location
            dst_node = device.target_node

            protection_util = 42.0
            protection_available = True

            if temp_graph.has_edge(src_node, dst_node):
                edge_data = temp_graph[src_node][dst_node]
                protection_util = edge_data.get("utilization_pct", 25.0)

                if action_type == ActionType.SLEEP_TRANSPONDER:
                    protection_util = round(
                        protection_util + (current_traffic * 0.8),
                        1
                    )

                    if device_id in [
                        "TRX-800G-003",
                        "TRX-800G-007",
                        "TRX-800G-015"
                    ]:
                        protection_available = False

                affected_links[(src_node, dst_node)] = protection_util

            sim_telemetry = {
                "traffic_utilization_pct": current_traffic,
                "power_consumption_w": simulated_power,
                "osnr_db": current_osnr,
                "pre_fec_ber": device.pre_fec_ber,
                "q_factor_db": device.q_factor_db
            }

            passed, policy_checks, rejection_reason = (
                policy_engine.validate_action(
                    device_id=device_id,
                    action_type=action_type,
                    sim_telemetry=sim_telemetry,
                    protection_path_util_pct=protection_util,
                    protection_available=protection_available
                )
            )

            saving_w = round(
                max(0.0, current_power - simulated_power),
                1
            )

            if passed:
                device.power_consumption_w = simulated_power
                device.traffic_utilization_pct = simulated_traffic
                device.osnr_db = simulated_osnr

                if action_type == ActionType.SLEEP_TRANSPONDER:
                    device.status = "SLEEP"
                    device.power_mode = PowerMode.SLEEP
                elif action_type == ActionType.REDUCE_GAIN:
                    device.status = "LOW_GAIN"
                    device.power_mode = PowerMode.LOW_GAIN

                total_saving_w += saving_w
            else:
                all_approved = False

            results.append({
                "device_id": device_id,
                "action": action_type.value,
                "result": "APPROVED" if passed else "REJECTED",
                "saving_w": saving_w if passed else 0.0,
                "traffic_pct": current_traffic,
                "osnr_db": current_osnr,
                "protection_utilization_pct": protection_util,
                "protection_available": protection_available,
                "policy_checks": [
                    {
                        "name": check.name,
                        "required": check.required,
                        "measured": check.measured,
                        "passed": check.passed
                    }
                    for check in policy_checks
                ],
                "reason": (
                    "All policy checks passed in the temporary combined scenario."
                    if passed
                    else rejection_reason
                )
            })

        approved_count = sum(
            1 for item in results
            if item["result"] == "APPROVED"
        )

        return {
            "status": "APPROVED" if all_approved else "REJECTED",
            "all_actions_approved": all_approved,
            "action_count": len(actions),
            "approved_count": approved_count,
            "total_power_saving_w": round(total_saving_w, 1),
            "total_power_saving_kw": round(total_saving_w / 1000.0, 3),
            "actions": results,
            "affected_links": [
                {
                    "source": src,
                    "target": dst,
                    "protection_utilization_pct": util
                }
                for (src, dst), util in affected_links.items()
            ],
            "state_changed": False,
            "temporary_state_discarded": True,
            "reason": (
                "All quantum-selected actions passed combined "
                "Digital Twin and policy validation."
                if all_approved
                else "One or more quantum-selected actions failed combined "
                     "Digital Twin or policy validation."
            )
        }

    def evaluate_proactive_wakeup(self) -> Optional[WhatIfSimulationResponse]:
        """
        Proactively monitors traffic trends and predicted congestion.
        Triggers wake-up evaluation for sleeping transponders if traffic is increasing.
        Uses cached Digital Twin state, synchronizing on-demand only if stale.
        """
        self.ensure_synced()
        sleeping_devs = [d for d in self.device_states.values() if d.power_mode == PowerMode.SLEEP]
        if not sleeping_devs:
            return None

        # Check if any active link is experiencing high traffic
        for dev_id, dev in self.device_states.items():
            if dev.power_mode == PowerMode.NORMAL and dev.traffic_utilization_pct > 70.0:
                # Find sleeping transponder on same node link
                target_sleep = next((s for s in sleeping_devs if s.node_location == dev.node_location), None)
                if target_sleep:
                    req = WhatIfSimulationRequest(
                        device_id=target_sleep.device_id,
                        action_type=ActionType.WAKE_TRANSPONDER
                    )
                    return self.simulate_what_if(req)
        return None

    def get_demo_scenarios(self) -> List[DemoScenarioInfo]:
        """Returns metadata for 5 realistic optical network demo scenarios."""
        return [
            DemoScenarioInfo(
                scenario_id="SCENARIO-1",
                title="Scenario 1: Low Traffic Transponder Sleep (Approved)",
                description="Transponder TRX-800G-005 reports 12% traffic during off-peak hours. Policy check validates OSNR and protection paths.",
                device_id="TRX-800G-005",
                action_type=ActionType.SLEEP_TRANSPONDER,
                expected_result=SimulationResult.APPROVED
            ),
            DemoScenarioInfo(
                scenario_id="SCENARIO-2",
                title="Scenario 2: Low Traffic but Degraded OSNR (Rejected)",
                description="Transponder TRX-800G-012 has low traffic (14%) but OSNR is degraded to 13.8 dB. Sleep action is REJECTED due to signal margin violation.",
                device_id="TRX-800G-012",
                action_type=ActionType.SLEEP_TRANSPONDER,
                expected_result=SimulationResult.REJECTED
            ),
            DemoScenarioInfo(
                scenario_id="SCENARIO-3",
                title="Scenario 3: Traffic Spike Proactive Wake-Up (Approved)",
                description="Ingress traffic surge detected on NYC link. Digital Twin simulates waking sleeping transponder TRX-800G-018 to prevent congestion.",
                device_id="TRX-800G-018",
                action_type=ActionType.WAKE_TRANSPONDER,
                expected_result=SimulationResult.APPROVED
            ),
            DemoScenarioInfo(
                scenario_id="SCENARIO-4",
                title="Scenario 4: Missing Protection Path (Rejected)",
                description="Transponder TRX-800G-007 reports 15% load, but secondary protection path is missing/degraded. Action REJECTED to maintain SLA.",
                device_id="TRX-800G-007",
                action_type=ActionType.SLEEP_TRANSPONDER,
                expected_result=SimulationResult.REJECTED
            ),
            DemoScenarioInfo(
                scenario_id="SCENARIO-5",
                title="Scenario 5: Fiber Link Degraded & Topology Recalculation",
                description="Fiber span degradation simulated on EDFA-AMP-003. Digital Twin recalculates available graph paths and power margins.",
                device_id="EDFA-AMP-003",
                action_type=ActionType.REDUCE_GAIN,
                expected_result=SimulationResult.REJECTED
            )
        ]

    def run_demo_scenario(self, scenario_id: str) -> WhatIfSimulationResponse:
        """Executes a specific preset realistic demo scenario."""
        self.synchronize()

        if scenario_id == "SCENARIO-1":
            # Set TRX-800G-005 to ideal low traffic
            if "TRX-800G-005" in telemetry_provider.get_devices():
                telemetry_provider.get_devices()["TRX-800G-005"].telemetry.traffic_utilization_pct = 12.0
                telemetry_provider.get_devices()["TRX-800G-005"].telemetry.osnr_db = 26.5
                telemetry_provider.get_devices()["TRX-800G-005"].power_mode = PowerMode.NORMAL
            req = WhatIfSimulationRequest(device_id="TRX-800G-005", action_type=ActionType.SLEEP_TRANSPONDER)
            return self.simulate_what_if(req)

        elif scenario_id == "SCENARIO-2":
            # Set TRX-800G-012 to low traffic but degraded OSNR
            if "TRX-800G-012" in telemetry_provider.get_devices():
                telemetry_provider.get_devices()["TRX-800G-012"].telemetry.traffic_utilization_pct = 14.0
                telemetry_provider.get_devices()["TRX-800G-012"].telemetry.osnr_db = 13.8  # Degraded below 14.5 dB
                telemetry_provider.get_devices()["TRX-800G-012"].power_mode = PowerMode.NORMAL
            req = WhatIfSimulationRequest(device_id="TRX-800G-012", action_type=ActionType.SLEEP_TRANSPONDER)
            return self.simulate_what_if(req)

        elif scenario_id == "SCENARIO-3":
            # Set TRX-800G-018 in sleep mode, prepare wake request
            if "TRX-800G-018" in telemetry_provider.get_devices():
                telemetry_provider.get_devices()["TRX-800G-018"].power_mode = PowerMode.SLEEP
                telemetry_provider.get_devices()["TRX-800G-018"].telemetry.traffic_utilization_pct = 0.0
            req = WhatIfSimulationRequest(device_id="TRX-800G-018", action_type=ActionType.WAKE_TRANSPONDER)
            return self.simulate_what_if(req)

        elif scenario_id == "SCENARIO-4":
            # Target TRX-800G-007 which has missing protection path flag
            if "TRX-800G-007" in telemetry_provider.get_devices():
                telemetry_provider.get_devices()["TRX-800G-007"].telemetry.traffic_utilization_pct = 15.0
                telemetry_provider.get_devices()["TRX-800G-007"].power_mode = PowerMode.NORMAL
            req = WhatIfSimulationRequest(device_id="TRX-800G-007", action_type=ActionType.SLEEP_TRANSPONDER)
            return self.simulate_what_if(req)

        elif scenario_id == "SCENARIO-5":
            # Target EDFA-AMP-003 with high traffic span
            if "EDFA-AMP-003" in telemetry_provider.get_devices():
                telemetry_provider.get_devices()["EDFA-AMP-003"].telemetry.traffic_utilization_pct = 82.0
                telemetry_provider.get_devices()["EDFA-AMP-003"].power_mode = PowerMode.NORMAL
            req = WhatIfSimulationRequest(device_id="EDFA-AMP-003", action_type=ActionType.REDUCE_GAIN)
            return self.simulate_what_if(req)

        else:
            # Default fallback
            req = WhatIfSimulationRequest(device_id="TRX-800G-001", action_type=ActionType.SLEEP_TRANSPONDER)
            return self.simulate_what_if(req)

    def execute_simulation(self, device_id: str, action_type: ActionType) -> Dict[str, Any]:
        """Applies a validated simulation result to the physical/simulated network controller."""
        self.ensure_synced()
        dev = telemetry_provider.get_device(device_id)
        if not dev:
            return {"status": "error", "message": f"Device {device_id} not found."}

        # Run validation first
        req = WhatIfSimulationRequest(device_id=device_id, action_type=action_type)
        sim_res = self.simulate_what_if(req)

        if sim_res.result != SimulationResult.APPROVED:
            return {
                "status": "blocked",
                "message": f"Execution BLOCKED by Digital Twin Safety Validation: {sim_res.reason}",
                "result": sim_res.result.value
            }

        # Apply to network simulator
        if action_type == ActionType.SLEEP_TRANSPONDER:
            simulator.set_device_power_mode(device_id, PowerMode.SLEEP)
        elif action_type == ActionType.REDUCE_GAIN:
            simulator.set_device_power_mode(device_id, PowerMode.LOW_GAIN)
        elif action_type in [ActionType.WAKE_TRANSPONDER, ActionType.RESTORE_DEVICE]:
            simulator.set_device_power_mode(device_id, PowerMode.NORMAL)

        return {
            "status": "success",
            "message": f"Digital Twin successfully applied '{action_type.value}' to {dev.name} ({device_id}).",
            "device_id": device_id,
            "new_power_mode": telemetry_provider.get_device(device_id).power_mode.value
        }

# Global Digital Twin Engine Instance
digital_twin_engine = DigitalTwinEngine()
