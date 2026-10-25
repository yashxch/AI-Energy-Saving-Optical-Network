import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from ..models import Device, DeviceType, HealthState, PowerMode, Telemetry


class NokiaTelemetryNormalizer:
    """Converts Nokia PM counters into the application's stable telemetry schema."""

    _fields = {
        "tx_power_dbm": ("OPT-AVG", "OPT-PWR-TX", "OPT", "tx_power_dbm"),
        "rx_power_dbm": ("OPR-AVG", "OPT-PWR-RX", "OPR", "rx_power_dbm"),
        "dsp_temp_c": ("TEMP-DSP", "TEMP", "dsp_temp_c"),
        "pre_fec_ber": ("PRE-FEC-BER", "BERPreFEC", "PRE-FEC", "BER", "pre_fec_ber"),
        "post_fec_ber": ("POST-FEC-BER", "BERPostFEC", "POST-FEC", "post_fec_ber"),
        "osnr_db": ("OSNR", "OSNR-DB", "osnr_db"),
        "esnr_db": ("ESNR", "ESNR-DB", "ESNR-AVG", "esnr_db"),
        "traffic_utilization_pct": ("UTILIZATION-PCT", "BANDWIDTHUTILIZATION", "traffic_utilization_pct"),
        "power_consumption_w": ("POWER-W", "power_consumption_w"),
        "laser_bias_ma": ("LASER-BIAS", "laser_bias_ma"),
        "q_factor_db": ("Q-FACTOR", "QFACTOR-AVG", "q_factor_db"),
        "timestamp": ("TIMESTAMP", "From", "timestamp"),
    }
    _metric_aliases = {
        "OPT-PWR-RX": ("OPR-AVG", "OPT-PWR-RX", "OPR"),
        "OPT-PWR-TX": ("OPT-AVG", "OPT-PWR-TX", "OPT"),
        "PRE-FEC-BER": ("PRE-FEC-BER", "BERPreFEC", "PRE-FEC", "BER"),
        "OSNR": ("OSNR", "OSNR-DB"),
        "Q-FACTOR": ("Q-FACTOR",),
        "TEMP-DSP": ("TEMP-DSP", "TEMP"),
        "POWER-W": ("POWER-W",),
        "UTILIZATION-PCT": ("UTILIZATION-PCT", "BANDWIDTHUTILIZATION"),
    }

    @staticmethod
    def _number(value: Any, default: float) -> float:
        if value is None or value == "":
            return default
        try:
            return float(str(value).strip().replace(",", ""))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _text(raw: Mapping[str, Any], *keys: str, default: str = "") -> str:
        for key in keys:
            if raw.get(key) not in (None, ""):
                return str(raw[key])
        return default

    @staticmethod
    def _nested_identity_maps(raw: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
        maps = []
        for key in ("identity", "identifiers", "equipment", "card", "interface", "node"):
            value = raw.get(key)
            if isinstance(value, Mapping):
                maps.append(value)
        return tuple(maps)

    def _identity_text(self, raw: Mapping[str, Any], *keys: str, default: str = "") -> str:
        value = self._text(raw, *keys, default="")
        if value:
            return value
        for identity_map in self._nested_identity_maps(raw):
            value = self._text(identity_map, *keys, default="")
            if value:
                return value
        return default

    def _number_from(self, raw: Mapping[str, Any], keys: tuple[str, ...], default: Optional[float] = None) -> Optional[float]:
        value = next((raw[key] for key in keys if raw.get(key) not in (None, "")), None)
        return None if value is None and default is None else self._number(value, default or 0.0)

    def _integer_from(self, raw: Mapping[str, Any], keys: tuple[str, ...]) -> Optional[int]:
        value = self._number_from(raw, keys)
        return None if value is None else int(value)

    @classmethod
    def _standard_metric_name(cls, name: Any) -> str:
        text = str(name).strip()
        normalized = text.upper()
        for standard_name, aliases in cls._metric_aliases.items():
            if normalized in aliases:
                return standard_name
        return text

    @classmethod
    def _flatten_wavesuite_metrics(cls, port: Mapping[str, Any]) -> dict:
        flattened = {}
        groups = port.get("mgs", {})
        if isinstance(groups, Mapping):
            groups = groups.values()
        elif not isinstance(groups, list):
            return flattened

        for group in groups:
            if not isinstance(group, Mapping):
                continue
            metrics = group.get("metrics", {})
            if isinstance(metrics, Mapping):
                metric_items = metrics.items()
            elif isinstance(metrics, list):
                metric_items = ((None, metric) for metric in metrics)
            else:
                continue

            for key, metric in metric_items:
                if isinstance(metric, Mapping):
                    name = next(
                        (
                            metric[field]
                            for field in ("name", "metric", "metricName", "metricId", "id", "key")
                            if metric.get(field) not in (None, "")
                        ),
                        key,
                    )
                    value = metric.get("val")
                else:
                    name = key
                    value = metric
                if name not in (None, "") and value is not None:
                    flattened[cls._standard_metric_name(name)] = value
        return flattened

    @classmethod
    def extract_pm_records(cls, payload: Any) -> List[dict]:
        if isinstance(payload, list):
            return [record for record in payload if isinstance(record, dict)]
        if not isinstance(payload, Mapping):
            return []

        op_result_args = payload.get("opResultArgs")
        if "respCtx" in payload and op_result_args is not None:
            if isinstance(op_result_args, Mapping):
                op_result_args = [op_result_args]
            if not isinstance(op_result_args, list):
                return []
            records = []
            for item in op_result_args:
                if not isinstance(item, Mapping):
                    continue
                ne_id = item.get("neId")
                raw_timestamp = item.get("dtis")
                timestamp = None
                if raw_timestamp not in (None, ""):
                    try:
                        timestamp = float(raw_timestamp)
                        if timestamp > 10_000_000_000:
                            timestamp /= 1000.0
                    except (TypeError, ValueError):
                        timestamp = raw_timestamp

                ports = item.get("ports", {})
                if isinstance(ports, Mapping):
                    if "mgs" in ports:
                        port_items = [(None, ports)]
                    else:
                        port_items = list(ports.items())
                elif isinstance(ports, list):
                    port_items = list(enumerate(ports))
                else:
                    continue

                for port_key, port in port_items:
                    if not isinstance(port, Mapping):
                        continue
                    record = dict(port)
                    record["chassis_id"] = ne_id
                    record["ne_id"] = ne_id
                    if timestamp is not None:
                        record["timestamp"] = timestamp
                    port_id = cls._text(
                        port,
                        "port_id",
                        "portId",
                        "port-id",
                        "id",
                        "name",
                        default=port_key if isinstance(port_key, str) else "",
                    )
                    if port_id:
                        record.setdefault("port_id", port_id)
                        record.setdefault("device_id", port_id)
                    record.update(cls._flatten_wavesuite_metrics(port))
                    records.append(record)
            return records

        for key in (
            "response",
            "data",
            "devices",
            "records",
            "currentPmData",
            "currentpmdata",
            "objCurrentPmData",
        ):
            if key in payload:
                return cls.extract_pm_records(payload[key])
        if len(payload) == 1:
            return cls.extract_pm_records(next(iter(payload.values())))
        return [dict(payload)]

    def normalize_telemetry(self, raw: Mapping[str, Any]) -> Telemetry:
        def value(name: str, default: float) -> float:
            keys = self._fields[name]
            return self._number(next((raw[k] for k in keys if raw.get(k) not in (None, "")), None), default)

        raw_timestamp = next(
            (raw[key] for key in self._fields["timestamp"] if raw.get(key) not in (None, "")),
            None,
        )
        if raw_timestamp is None:
            timestamp = time.time()
        else:
            try:
                timestamp = float(str(raw_timestamp).strip())
                if timestamp > 10_000_000_000:
                    timestamp /= 1000.0
            except ValueError:
                parsed_timestamp = datetime.fromisoformat(
                    str(raw_timestamp).strip().replace("Z", "+00:00")
                )
                if parsed_timestamp.tzinfo is None:
                    parsed_timestamp = parsed_timestamp.replace(tzinfo=timezone.utc)
                timestamp = parsed_timestamp.timestamp()
        power = value("power_consumption_w", 0.0)
        voltage = self._number(raw.get("VOLTAGE-V", raw.get("voltage_v")), 12.0)
        current = self._number(raw.get("CURRENT-A", raw.get("current_a")), power / voltage if voltage else 0.0)
        return Telemetry(
            tx_power_dbm=value("tx_power_dbm", 3.5),
            rx_power_dbm=value("rx_power_dbm", -11.8),
            laser_bias_ma=value("laser_bias_ma", 52.0),
            laser_temp_c=self._number(raw.get("TEMP-LASER", raw.get("laser_temp_c")), 28.5),
            dsp_temp_c=value("dsp_temp_c", 54.0),
            module_temp_c=self._number(raw.get("TEMP-MODULE", raw.get("module_temp_c")), 38.0),
            ber=self._number_from(raw, ("BER", "ber")),
            pre_fec_ber=value("pre_fec_ber", 2.4e-5),
            post_fec_ber=value("post_fec_ber", 0.0),
            q_factor_db=value("q_factor_db", 14.8),
            osnr_db=value("osnr_db", 26.4),
            chromatic_dispersion=self._number(raw.get("CHROMATIC-DISPERSION", raw.get("chromatic_dispersion")), 320.0),
            voltage_v=voltage,
            current_a=current,
            fan_rpm=int(self._number(raw.get("FAN-RPM", raw.get("fan_rpm")), 3200)),
            traffic_utilization_pct=value("traffic_utilization_pct", 0.0),
            power_consumption_w=power,
            timestamp=timestamp,
            fec_ubc=self._integer_from(raw, ("fec_ubc", "FEC UBC", "FEC-UBC", "FECUBC", "UBC")),
            q_margin_min_db=self._number_from(raw, ("q_margin_min_db", "Q-Margin - Min", "Q_MIN", "q_min")),
            q_margin_max_db=self._number_from(raw, ("q_margin_max_db", "Q-Margin - Max", "Q_MAX", "q_max")),
            q_margin_avg_db=self._number_from(raw, ("q_margin_avg_db", "Q-Margin - Average", "QMARGIN-AVG", "Q_AVG", "q_avg")),
            rx_lane_power_1_dbm=self._number_from(raw, ("rx_lane_power_1_dbm", "RX-LANE-1", "Rx Lane Power 1")),
            rx_lane_power_2_dbm=self._number_from(raw, ("rx_lane_power_2_dbm", "RX-LANE-2", "Rx Lane Power 2")),
            rx_lane_power_3_dbm=self._number_from(raw, ("rx_lane_power_3_dbm", "RX-LANE-3", "Rx Lane Power 3")),
            rx_lane_power_4_dbm=self._number_from(raw, ("rx_lane_power_4_dbm", "RX-LANE-4", "Rx Lane Power 4")),
            tx_lane_power_1_dbm=self._number_from(raw, ("tx_lane_power_1_dbm", "TX-LANE-1", "Tx Lane Power 1")),
            tx_lane_power_2_dbm=self._number_from(raw, ("tx_lane_power_2_dbm", "TX-LANE-2", "Tx Lane Power 2")),
            tx_lane_power_3_dbm=self._number_from(raw, ("tx_lane_power_3_dbm", "TX-LANE-3", "Tx Lane Power 3")),
            tx_lane_power_4_dbm=self._number_from(raw, ("tx_lane_power_4_dbm", "TX-LANE-4", "Tx Lane Power 4")),
            opr_min_dbm=self._number_from(raw, ("opr_min_dbm", "OPR - Min", "OPR_MIN", "opr_min")),
            opr_max_dbm=self._number_from(raw, ("opr_max_dbm", "OPR - Max", "OPR_MAX", "opr_max")),
            opr_avg_dbm=self._number_from(raw, ("opr_avg_dbm", "OPR - Average", "OPR-AVG", "OPR_AVG", "opr_avg")),
            expected_network_output_power_dbm=self._number_from(raw, ("expected_network_output_power_dbm", "Expected Network Output Power", "EXP_NET_OUT")),
            measured_network_output_power_dbm=self._number_from(raw, ("measured_network_output_power_dbm", "Measured Network Output Power", "MEAS_NET_OUT")),
            laser_case_temp_c=self._number_from(raw, ("laser_case_temp_c", "Laser Case Temperature", "TEMP_CASE_LASER")),
            admin_state=self._text(raw, "admin_state", "Admin State", "ADMIN_STATE", default=""),
            state_qualifier=self._text(raw, "state_qualifier", "State Qualifier", "Secondary State", "Avail State", default=""),
            status_led=self._text(raw, "status_led", "Status LED", "Status LED Color", default=""),
            oper_capability=self._text(raw, "oper_capability", "Oper Capability", "Oper State", default=""),
            module_type=self._text(raw, "module_type", "Module Type", "Pluggable Module Type", default=""),
            max_port_rate=self._text(raw, "max_port_rate", "Max Port Rate", default=""),
            signal_rate=self._text(raw, "signal_rate", "Signal Rate", default=""),
            odu_rate=self._text(raw, "odu_rate", "ODU Rate", default=""),
            channel_tx_frequency_thz=self._number_from(raw, ("channel_tx_frequency_thz", "Channel Tx Frequency", "Frequency")),
            channel_rx_frequency_thz=self._number_from(raw, ("channel_rx_frequency_thz", "Channel Rx Frequency")),
            channel_tx_offset_ghz=self._number_from(raw, ("channel_tx_offset_ghz", "Channel Tx Offset")),
            channel_rx_offset_ghz=self._number_from(raw, ("channel_rx_offset_ghz", "Channel Rx Offset")),
            grid_step_size_ghz=self._number_from(raw, ("grid_step_size_ghz", "Grid Step Size")),
            link_span_km=self._number_from(raw, ("link_span_km", "Link Span")),
            otsig_id=self._text(raw, "otsig_id", "OTSiG ID", "OTSIG", default=""),
            eth_octets_rx=self._integer_from(raw, ("eth_octets_rx", "ETHOCTETS-RX", "OCTETS-RX", "ETHOCTETS")),
            eth_octets_tx=self._integer_from(raw, ("eth_octets_tx", "ETHOCTETS-TX", "OCTETS-TX")),
            eth_errors_rx=self._integer_from(raw, ("eth_errors_rx", "ETH-ERRORS-RX", "Ethernet Errors Rx")),
            eth_errors_tx=self._integer_from(raw, ("eth_errors_tx", "ETH-ERRORS-TX", "Ethernet Errors Tx")),
            eth_packets_rx=self._integer_from(raw, ("eth_packets_rx", "ETHPACKETS-RX", "Ethernet Packets Rx")),
            eth_packets_tx=self._integer_from(raw, ("eth_packets_tx", "ETHPACKETS-TX", "Ethernet Packets Tx")),
            eth_error_rate_pct=self._number_from(raw, ("eth_error_rate_pct", "ETH-ERROR-RATE-PCT", "Ethernet Error Rate")),
            bandwidth_gbps=self._number_from(raw, ("bandwidth_gbps", "BANDWIDTH", "Bandwidth")),
            confirmed_utilization_pct=self._number_from(raw, ("confirmed_utilization_pct", "CONFIRMED-UTILIZATION-PCT", "Confirmed Utilization")),
            opt_min_dbm=self._number_from(raw, ("opt_min_dbm", "OPT - Min", "OPT_MIN")),
            opt_max_dbm=self._number_from(raw, ("opt_max_dbm", "OPT - Max", "OPT_MAX")),
            opt_avg_dbm=self._number_from(raw, ("opt_avg_dbm", "OPT - Average", "OPT-AVG", "OPT_AVG")),
            opr_high_dbm=self._number_from(raw, ("opr_high_dbm", "OPR - High", "OPR_HIGH")),
            opr_low_dbm=self._number_from(raw, ("opr_low_dbm", "OPR - Low", "OPR_LOW")),
            opt_high_dbm=self._number_from(raw, ("opt_high_dbm", "OPT - High", "OPT_HIGH")),
            opt_low_dbm=self._number_from(raw, ("opt_low_dbm", "OPT - Low", "OPT_LOW")),
            cv_pcs=self._integer_from(raw, ("cv_pcs", "CV-PCS")),
            es_pcs=self._integer_from(raw, ("es_pcs", "ES-PCS")),
            sefs_pcs=self._integer_from(raw, ("sefs_pcs", "SEFS-PCS")),
            ses_pcs=self._integer_from(raw, ("ses_pcs", "SES-PCS")),
            esnr_db=self._number_from(raw, ("esnr_db", "ESNR-AVG", "ESNR")),
            esnr_min_db=self._number_from(raw, ("esnr_min_db", "ESNR - Min", "ESNR_MIN")),
            esnr_max_db=self._number_from(raw, ("esnr_max_db", "ESNR - Max", "ESNR_MAX")),
            esnr_avg_db=self._number_from(raw, ("esnr_avg_db", "ESNR - Average", "ESNR-AVG", "ESNR_AVG")),
            connection_state=self._text(raw, "connection_state", "Connection State", default=""),
            connection_type=self._text(raw, "connection_type", "Connection Type", default=""),
            connection_rate=self._text(raw, "connection_rate", "Connection Rate", default=""),
            endpoint_source=self._text(raw, "endpoint_source", "Source", "Source Endpoint", default=""),
            endpoint_target=self._text(raw, "endpoint_target", "Target", "Target Endpoint", default=""),
            ains_state=self._text(raw, "ains_state", "AINS state", "AINS State", default=""),
            ains_timer_sec=self._integer_from(raw, ("ains_timer_sec", "AINS timer", "AINS Timer")),
            fan_status=self._text(raw, "fan_status", "Fan Status", default=""),
            device_power_w=self._number_from(raw, ("device_power_w", "DEVICE-POWER-W", "Device Power")),
            card_power_w=self._number_from(raw, ("card_power_w", "CARD-POWER-W", "Card Power")),
            port_utilization_pct=self._number_from(raw, ("port_utilization_pct", "PORT-UTILIZATION-PCT", "Port Utilization")),
            module_health=self._text(raw, "module_health", "MODULE-HEALTH", "Module Health", default=""),
            ambient_temp_c=self._number_from(raw, ("ambient_temp_c", "AMBIENT-TEMP", "Ambient Temperature")),
            humidity_pct=self._number_from(raw, ("humidity_pct", "HUMIDITY-PCT", "Humidity")),
        )

    def normalize_device(self, raw: Mapping[str, Any], fallback_id: Optional[str] = None) -> Device:
        raw = dict(raw)
        if not raw.get("chassis_id"):
            chassis_id = raw.get("IpAddress") or raw.get("userLabel") or raw.get("neId") or raw.get("NE")
            if chassis_id:
                raw["chassis_id"] = chassis_id
        if not raw.get("product"):
            product = raw.get("nodeType") or raw.get("productName")
            if product:
                raw["product"] = product

        device_id = self._identity_text(
            raw,
            "device_id",
            "deviceId",
            "DEVICE-ID",
            "id",
            "ID",
            "NE",
            "neId",
            "identifier",
            "IDENTIFIER",
            default=fallback_id or "NOKIA-UNKNOWN",
        )
        type_text = self._text(
            raw,
            "equipment_type",
            "EQUIPMENT-TYPE",
            "type",
            "TYPE",
            "product",
            "nodeType",
            "productName",
            default="Transponder-800G",
        ).lower()
        type_map = {
            "s4x400": DeviceType.TRANSPONDER,
            "smf6": DeviceType.SMF6,
            "transponder-800g": DeviceType.TRANSPONDER_800G,
            "transponder": DeviceType.TRANSPONDER_800G,
            "edfa": DeviceType.EDFA,
            "edfa amplifier": DeviceType.EDFA,
            "roadm": DeviceType.ROADM,
            "roadm wss": DeviceType.ROADM,
            "filter card": DeviceType.FILTER_CARD,
            "filter": DeviceType.FILTER_CARD,
            "network element": DeviceType.NETWORK_ELEMENT,
        }
        device_type = next(
            (v for k, v in type_map.items() if k in type_text),
            DeviceType.UNKNOWN if "csv_history" in raw else DeviceType.TRANSPONDER_800G,
        )
        default_mode = PowerMode.UNKNOWN if "csv_history" in raw else PowerMode.NORMAL
        mode_text = self._text(raw, "power_mode", "POWER-MODE", default=default_mode.value).lower()
        mode = next((m for m in PowerMode if m.value.lower() == mode_text), default_mode)
        health_text = self._text(raw, "health", "HEALTH", default=HealthState.NORMAL.value).lower()
        health = next((h for h in HealthState if h.value.lower() == health_text), HealthState.NORMAL)
        return Device(
            id=device_id,
            name=self._identity_text(
                raw,
                "name",
                "NAME",
                "device_name",
                "deviceName",
                "DEVICE-NAME",
                "displayName",
                "DISPLAY-NAME",
                "NE",
                "userLabel",
                "neId",
                "equipment_name",
                "equipmentName",
                "EQUIPMENT-NAME",
                "card_name",
                "cardName",
                "CARD-NAME",
                "description",
                "DESCRIPTION",
                default="Name unavailable",
            ),
            type=device_type,
            node_location=self._identity_text(
                raw,
                "node_location",
                "nodeName",
                "NODE",
                "LOCATION",
                "NE",
                "userLabel",
                "neId",
                default="UNKNOWN",
            ),
            target_node=self._identity_text(raw, "target_node", "targetNode", "TARGET-NODE", default="UNKNOWN"),
            wavelength_nm=self._number_from(raw, ("wavelength_nm", "WAVELENGTH-NM")),
            power_mode=mode,
            health=health,
            telemetry=self.normalize_telemetry(raw),
            ne_name=self._identity_text(
                raw, "ne_name", "neName", "NE-NAME", "NE name", "NE", "userLabel", "neId", default=""
            ),
            shelf_id=self._identity_text(
                raw, "shelf_id", "shelfId", "shelf-id", "SHELF", "Shelf", "shelf", default=""
            ),
            slot_id=self._identity_text(
                raw, "slot_id", "slotId", "slot-id", "SLOT", "Slot", "slot", default=""
            ),
            port_id=self._identity_text(
                raw, "port_id", "portId", "port-id", "PORT", "Port", "port", default=""
            ),
            description=self._identity_text(raw, "description", "DESCRIPTION", default=""),
            equipment_name=self._identity_text(
                raw,
                "equipment_name",
                "equipmentName",
                "EQUIPMENT-NAME",
                default="",
            ),
            card_name=self._identity_text(
                raw, "card_name", "cardName", "card-type", "CARD-NAME", "card", "Card", default=""
            ),
            interface_name=self._identity_text(
                raw,
                "interface_name",
                "interfaceName",
                "INTERFACE-NAME",
                default="",
            ),
            chassis_id=self._identity_text(
                raw,
                "chassis_id",
                "chassisId",
                "CHASSIS-ID",
                "chassis",
                "Chassis",
                "IpAddress",
                "NE",
                "userLabel",
                "neId",
                default="",
            ),
            raw_record=dict(raw),
        )
