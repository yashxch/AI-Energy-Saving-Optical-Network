import math
import random
import time
from typing import Dict, List, Optional
from .models import Device, DeviceType, PowerMode, HealthState, Telemetry
from .multi_angular_topology import MultiAngularTopologyEngine, TopologyPattern

NODES = ["NYC", "BOS", "CHI", "WDC", "ATL", "DAL", "SFO", "LAX"]

class NetworkSimulator:
    def __init__(self):
        self.devices: Dict[str, Device] = {}
        self.topology_engine = MultiAngularTopologyEngine(NODES)
        self.start_time = time.time()
        self.total_energy_saved_kwh = 142.5
        self.baseline_power_kw = 125.0
        self.fault_injections: Dict[str, str] = {}  # device_id -> fault_type
        self._init_devices()


    def _init_devices(self):
        device_count = 0

        # 1. 50 800G Transponders
        for i in range(1, 51):
            src_node = NODES[(i - 1) % len(NODES)]
            dst_node = NODES[i % len(NODES)]
            dev_id = f"TRX-800G-{i:03d}"
            wl = 1530.0 + (i * 0.8)
            
            # Make some transponders start in low-traffic/eco state for variety
            initial_mode = PowerMode.ECO if i in [5, 12, 18, 27, 34, 42] else PowerMode.NORMAL

            self.devices[dev_id] = Device(
                id=dev_id,
                name=f"800G Muxponder Unit {i}",
                type=DeviceType.TRANSPONDER_800G,
                node_location=src_node,
                target_node=dst_node,
                wavelength_nm=round(wl, 2),
                power_mode=initial_mode,
                health=HealthState.NORMAL,
                telemetry=self._generate_initial_telemetry(DeviceType.TRANSPONDER_800G, initial_mode, i)
            )
            device_count += 1

        # 2. 20 EDFA Amplifiers
        for i in range(1, 21):
            node = NODES[(i - 1) % len(NODES)]
            dev_id = f"EDFA-AMP-{i:03d}"
            initial_mode = PowerMode.LOW_GAIN if i in [3, 9, 14] else PowerMode.NORMAL

            self.devices[dev_id] = Device(
                id=dev_id,
                name=f"Variable Gain Optical Amp {i}",
                type=DeviceType.EDFA,
                node_location=node,
                target_node=NODES[i % len(NODES)],
                wavelength_nm=1550.12,
                power_mode=initial_mode,
                health=HealthState.NORMAL,
                telemetry=self._generate_initial_telemetry(DeviceType.EDFA, initial_mode, i)
            )
            device_count += 1

        # 3. 15 ROADMs
        for i in range(1, 16):
            node = NODES[(i - 1) % len(NODES)]
            dev_id = f"ROADM-WSS-{i:03d}"

            self.devices[dev_id] = Device(
                id=dev_id,
                name=f"Directionless ROADM Node {i}",
                type=DeviceType.ROADM,
                node_location=node,
                target_node=NODES[(i + 1) % len(NODES)],
                wavelength_nm=1545.32,
                power_mode=PowerMode.NORMAL,
                health=HealthState.NORMAL,
                telemetry=self._generate_initial_telemetry(DeviceType.ROADM, PowerMode.NORMAL, i)
            )
            device_count += 1

        # 4. 15 Filter Cards
        for i in range(1, 16):
            node = NODES[(i - 1) % len(NODES)]
            dev_id = f"FLT-CARD-{i:03d}"

            self.devices[dev_id] = Device(
                id=dev_id,
                name=f"Optical Mux/Demux Filter {i}",
                type=DeviceType.FILTER_CARD,
                node_location=node,
                target_node=NODES[(i + 2) % len(NODES)],
                wavelength_nm=1555.75,
                power_mode=PowerMode.NORMAL,
                health=HealthState.NORMAL,
                telemetry=self._generate_initial_telemetry(DeviceType.FILTER_CARD, PowerMode.NORMAL, i)
            )
            device_count += 1

    def _get_diurnal_factor(self) -> float:
        """Simulates 24-hour network traffic wave."""
        elapsed = time.time() - self.start_time
        # Speed up 24h cycle so 120 seconds = 1 day for dynamic demo
        time_of_day_angle = (elapsed / 120.0) * 2 * math.pi
        # Peak at ~0.85, valley at ~0.15
        base_wave = (math.sin(time_of_day_angle) + 1) / 2
        return max(0.12, min(0.98, 0.2 + 0.75 * base_wave))

    def _generate_initial_telemetry(self, dev_type: DeviceType, power_mode: PowerMode, index: int) -> Telemetry:
        diurnal = self._get_diurnal_factor()
        noise = random.uniform(-0.03, 0.03)
        traffic_pct = max(5.0, min(99.0, (diurnal + noise) * 100))
        if index % 6 == 0:
            traffic_pct = random.uniform(8.0, 18.0)

        if power_mode == PowerMode.SLEEP:
            traffic_pct = 0.0
            power_w = 45.0
        elif power_mode == PowerMode.ECO:
            traffic_pct = min(traffic_pct, 25.0)
            power_w = 180.0
        elif power_mode == PowerMode.LOW_GAIN:
            power_w = 90.0
        else: # NORMAL
            power_w = 350.0 if dev_type == DeviceType.TRANSPONDER_800G else (
                160.0 if dev_type == DeviceType.EDFA else (
                220.0 if dev_type == DeviceType.ROADM else 85.0
            ))

        return Telemetry(
            tx_power_dbm=round(3.5 + random.uniform(-0.2, 0.2), 2),
            rx_power_dbm=round(-11.8 + random.uniform(-0.5, 0.5), 2),
            laser_bias_ma=round(52.0 + random.uniform(-2.0, 2.0), 1),
            laser_temp_c=round(28.5 + random.uniform(-1.0, 1.0), 1),
            dsp_temp_c=round(54.0 + random.uniform(-2.0, 2.0), 1),
            module_temp_c=round(38.0 + random.uniform(-1.5, 1.5), 1),
            ber=1.2e-9,
            pre_fec_ber=2.4e-5,
            post_fec_ber=0.0,
            q_factor_db=round(14.8 + random.uniform(-0.3, 0.3), 2),
            osnr_db=round(26.4 + random.uniform(-0.6, 0.6), 2),
            chromatic_dispersion=round(320.0 + random.uniform(-10.0, 10.0), 1),
            voltage_v=round(12.02 + random.uniform(-0.05, 0.05), 2),
            current_a=round(power_w / 12.0, 2),
            fan_rpm=int(3200 + (power_w * 4) + random.randint(-100, 100)),
            traffic_utilization_pct=round(traffic_pct, 1),
            power_consumption_w=round(power_w, 1)
        )

    def tick(self):
        """Main update tick called periodically."""
        diurnal = self._get_diurnal_factor()
        
        for dev_id, dev in self.devices.items():
            t = dev.telemetry
            fault = self.fault_injections.get(dev_id)

            # Base traffic from diurnal wave
            if dev.power_mode == PowerMode.SLEEP:
                target_traffic = 0.0
                base_power = 45.0
            elif dev.power_mode == PowerMode.ECO:
                target_traffic = min(22.0, (diurnal * 100) * 0.3)
                base_power = 180.0
            elif dev.power_mode == PowerMode.LOW_GAIN:
                target_traffic = (diurnal * 100) * 0.7
                base_power = 95.0
            else:
                base_traffic = diurnal * 100 + random.uniform(-4, 4)
                if hash(dev_id) % 6 == 0:
                    base_traffic = random.uniform(8.0, 18.0)
                target_traffic = max(5.0, min(98.0, base_traffic))
                base_power = 350.0 if dev.type == DeviceType.TRANSPONDER_800G else (
                    160.0 if dev.type == DeviceType.EDFA else (
                    220.0 if dev.type == DeviceType.ROADM else 85.0
                ))

            # Apply faults if injected
            health = HealthState.NORMAL
            osnr_base = 26.5
            pre_fec_base = 2.5e-5
            dsp_temp_base = 54.0 + (target_traffic * 0.15)

            if fault == "BER_SPIKE":
                pre_fec_base = 8.5e-4
                health = HealthState.WARNING
            elif fault == "OVERHEAT":
                dsp_temp_base = 86.5
                health = HealthState.CRITICAL
            elif fault == "OSNR_DROP":
                osnr_base = 13.2
                health = HealthState.WARNING

            # Update telemetry values smoothly
            t.traffic_utilization_pct = round(max(0.0, min(100.0, target_traffic)), 1)
            t.power_consumption_w = round(max(30.0, base_power + random.uniform(-3, 3)), 1)
            t.osnr_db = round(max(10.0, osnr_base + random.uniform(-0.4, 0.4)), 2)
            t.pre_fec_ber = float(f"{pre_fec_base * random.uniform(0.8, 1.2):.2e}")
            t.ber = float(f"{t.pre_fec_ber * 1e-4:.2e}")
            t.q_factor_db = round(max(8.0, min(20.0, 10.0 + (t.osnr_db * 0.25))), 2)
            t.dsp_temp_c = round(dsp_temp_base + random.uniform(-0.5, 0.5), 1)
            t.laser_temp_c = round(28.0 + (t.dsp_temp_c * 0.15) + random.uniform(-0.3, 0.3), 1)
            t.module_temp_c = round(32.0 + (t.dsp_temp_c * 0.2) + random.uniform(-0.3, 0.3), 1)
            t.current_a = round(t.power_consumption_w / t.voltage_v, 2)
            t.fan_rpm = int(max(2000, 2400 + (t.dsp_temp_c * 40) + random.randint(-50, 50)))
            t.timestamp = time.time()
            dev.health = health

        # Energy saved accumulation
        active_kw = sum(d.telemetry.power_consumption_w for d in self.devices.values()) / 1000.0
        saved_kw = max(0.0, self.baseline_power_kw - active_kw)
        self.total_energy_saved_kwh += (saved_kw * (1.0 / 3600.0))

    def inject_fault(self, device_id: str, fault_type: str):
        if device_id in self.devices:
            self.fault_injections[device_id] = fault_type

    def clear_fault(self, device_id: str):
        if device_id in self.fault_injections:
            del self.fault_injections[device_id]

    def set_device_power_mode(self, device_id: str, mode: PowerMode):
        if device_id in self.devices:
            self.devices[device_id].power_mode = mode

    def set_topology_pattern(self, pattern_name: str) -> dict:
        try:
            pattern_enum = TopologyPattern(pattern_name.lower())
        except ValueError:
            valid = [p.value for p in TopologyPattern]
            raise ValueError(f"Invalid topology pattern '{pattern_name}'. Valid options: {valid}")

        self.topology_engine.pattern = pattern_enum
        self.update_device_targets_from_topology()
        return self.topology_engine.get_topology_state()

    def rotate_topology(self, delta_deg: float, node_name: Optional[str] = None) -> dict:
        if node_name:
            self.topology_engine.rotate_single_node(node_name, delta_deg)
        else:
            self.topology_engine.rotate_network(delta_deg)
        self.update_device_targets_from_topology()
        return self.topology_engine.get_topology_state()

    def update_device_targets_from_topology(self):
        links = self.topology_engine.generate_links()
        if not links:
            return
        # Dynamically map device target nodes to topology active links
        for idx, (dev_id, dev) in enumerate(self.devices.items()):
            active_link = links[idx % len(links)]
            dev.node_location = active_link.src
            dev.target_node = active_link.dst

# Global simulator instance

simulator = NetworkSimulator()
