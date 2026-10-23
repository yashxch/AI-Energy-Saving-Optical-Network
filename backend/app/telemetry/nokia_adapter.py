import csv
import json
import math
import os
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from ..models import Device, PowerMode
from .interface import BaseTelemetryAdapter
from .normalizer import NokiaTelemetryNormalizer

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_DIR = BACKEND_DIR.parent
CREDENTIALS_PATH = BACKEND_DIR / "app" / "config" / "nokia_credentials.json"
DOTENV_PATH = BACKEND_DIR / ".env"
DOTENV_TEXT_PATH = BACKEND_DIR / ".env.txt"


class NokiaTelemetryAdapter(BaseTelemetryAdapter):
    def __init__(self, config: Optional[dict] = None):
        config = config or {}
        load_dotenv(REPOSITORY_DIR / ".env", override=False)
        load_dotenv(DOTENV_PATH, override=False)
        if not DOTENV_PATH.exists():
            load_dotenv(DOTENV_TEXT_PATH, override=False)
        credentials = self._load_credentials()
        self.destination_url = config.get("nokia_destination_url", "")
        self.pmdata_url = config.get("nokia_pmdata_url", "")
        self.auth_url = config.get("nokia_auth_url", "")
        self.client_id = (
            os.getenv("NOKIA_CLIENT_ID")
            or credentials.get("client_id", "")
        )
        self.client_secret = (
            os.getenv("NOKIA_CLIENT_SECRET")
            or credentials.get("client_secret", "")
        )
        self.username = (
            os.getenv("NOKIA_USERNAME")
            or os.getenv("NOKIA_USER")
            or credentials.get("username", "")
        )
        self.password = (
            os.getenv("NOKIA_PASSWORD")
            or os.getenv("NOKIA_PASS")
            or credentials.get("password", "")
        )
        self.static_token = config.get("nokia_auth_token", "")
        self.ne_ip = config.get("nokia_ne_ip", "")
        self.poll_interval_sec = float(config.get("nokia_poll_interval_sec", 4.0))
        self.request_timeout_sec = float(config.get("nokia_request_timeout_sec", 10.0))
        ca_bundle = os.getenv("NOKIA_CA_BUNDLE") or config.get("nokia_ca_bundle", "")
        self.pmdata_path = Path(config.get("nokia_pmdata_path", "./nokia_pmdata"))
        if not self.pmdata_path.is_absolute():
            self.pmdata_path = BACKEND_DIR / self.pmdata_path
        self.nokia_execution_enabled = bool(config.get("nokia_execution_enabled", False))
        self.devices: Dict[str, Device] = {}
        self._baseline_power_kw = 0.0
        self._total_energy_saved_kwh = 0.0
        self.normalizer = NokiaTelemetryNormalizer()
        self.last_refresh_status = "not_refreshed"
        self.last_refresh_error: Optional[str] = None
        self.data_origin = "none"
        ca_path = Path(ca_bundle) if ca_bundle else None
        if ca_path is not None and not ca_path.is_absolute():
            ca_path = REPOSITORY_DIR / ca_path
        self._ssl_context = ssl.create_default_context(
            cafile=str(ca_path) if ca_path is not None else None
        )
        self.ssl_context = self._ssl_context
        self.timeout = self.request_timeout_sec
        self._access_token: Optional[str] = None
        self._token_expires_at = 0.0
        self._last_poll_at = 0.0

    @staticmethod
    def _load_credentials() -> dict:
        try:
            with CREDENTIALS_PATH.open(encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    def initialize(self) -> None:
        self.refresh()

    def tick(self) -> None:
        # The app ticks every second; avoid hammering the NMS with a request per tick.
        if self.data_origin == "csv_snapshot":
            return
        if time.time() - self._last_poll_at >= self.poll_interval_sec:
            self.refresh()

    def refresh(self) -> None:
        self._last_poll_at = time.time()
        self.last_refresh_status = "refreshing"
        self.last_refresh_error = None
        try:
            if self.pmdata_path.is_file():
                if self._load_local_samples():
                    self.data_origin = "csv_snapshot" if self.pmdata_path.suffix.lower() == ".csv" else "local_pmdata"
                    self.last_refresh_status = "snapshot" if self.data_origin == "csv_snapshot" else "connected"
                    return
                self.devices = {}
                self.data_origin = "none"
                self.last_refresh_status = "no_data"
                return
            if self.destination_url:
                self._poll_destination()
                self.data_origin = "live_destination"
                self.last_refresh_status = "connected" if self.devices else "no_data"
                return
            if self._load_local_samples():
                self.last_refresh_status = "connected"
                self.data_origin = "local_pmdata"
                return
            self.devices = {}
            self.data_origin = "none"
            self.last_refresh_status = "no_data"
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.devices = {}
            self._baseline_power_kw = 0.0
            self.data_origin = "none"
            self.last_refresh_status = "error"
            self.last_refresh_error = str(exc)
            print(f"Warning polling Nokia telemetry destination: {exc}")

    def get_devices(self) -> Dict[str, Device]:
        return self.devices

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.devices.get(device_id)

    def set_device_power_mode(self, device_id: str, mode: PowerMode) -> bool:
        if not self.nokia_execution_enabled:
            return False
        # This adapter intentionally does not implement hardware writes.
        return False

    @property
    def baseline_power_kw(self) -> float:
        return self._baseline_power_kw

    @property
    def total_energy_saved_kwh(self) -> float:
        return self._total_energy_saved_kwh

    def _load_local_samples(self) -> bool:
        if not self.pmdata_path.exists():
            return False
        paths = [self.pmdata_path] if self.pmdata_path.is_file() else sorted(self.pmdata_path.glob("*"))
        if self.pmdata_path.is_file() and self.pmdata_path.suffix.lower() == ".csv":
            self._set_devices(self._load_csv_snapshot(self.pmdata_path))
            return bool(self.devices)
        records = []
        for path in paths:
            if path.suffix.lower() == ".json":
                with path.open(encoding="utf-8") as handle:
                    records.extend(self._extract_records(json.load(handle)))
            elif path.suffix.lower() == ".csv":
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    records.extend(csv.DictReader(handle))
        self._set_devices(records)
        return bool(self.devices)

    @staticmethod
    def _csv_number(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.upper() in {"NS", "N/A", "NA", "NULL"}:
            return None
        try:
            number = float(text.replace(",", ""))
        except ValueError:
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def _load_csv_snapshot(cls, path: Path) -> List[dict]:
        metric_sources = {
            "pre_fec_ber": ("BERPreFEC", "PRE-FEC"),
            "post_fec_ber": ("BERPostFEC", "POST-FEC"),
            "tx_power_dbm": ("OPT-AVG",),
            "rx_power_dbm": ("OPR-AVG",),
            "esnr_db": ("ESNR-AVG",),
            "q_factor_db": ("QFACTOR-AVG",),
            "q_margin_avg_db": ("QMARGIN-AVG",),
            "fec_ubc": ("FECUBC",),
            "traffic_utilization_pct": ("BANDWIDTHUTILIZATION",),
            "eth_octets_rx": ("IFINOCTETS",),
            "eth_octets_tx": ("IFOUTOCTETS",),
        }
        aggregates: Dict[str, dict] = {}
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                ne_name = str(row.get("NE") or "").strip()
                if not ne_name:
                    continue
                record = aggregates.setdefault(ne_name, {
                    "device_id": ne_name,
                    "ne_name": ne_name,
                    "name": ne_name,
                    "node_location": ne_name,
                    "chassis_id": ne_name,
                    "product": "Network Element",
                    "timestamp": row.get("From", ""),
                    "description": "15-minute CSV snapshot aggregated across interfaces",
                    "_csv_interfaces": set(),
                    "_csv_metric_sums": {},
                    "_csv_metric_sources": {},
                })
                if row.get("TP"):
                    record["_csv_interfaces"].add(row["TP"].strip())
                for target, source_fields in metric_sources.items():
                    value = next(
                        (
                            parsed
                            for source in source_fields
                            if (parsed := cls._csv_number(row.get(source))) is not None
                        ),
                        None,
                    )
                    if value is None:
                        continue
                    total, count = record["_csv_metric_sums"].get(target, (0.0, 0))
                    record["_csv_metric_sums"][target] = (total + value, count + 1)
                    source_name = next(
                        source for source in source_fields
                        if cls._csv_number(row.get(source)) is not None
                    )
                    record["_csv_metric_sources"].setdefault(target, set()).add(source_name)

        results = []
        for record in aggregates.values():
            sums = record.pop("_csv_metric_sums")
            sources = record.pop("_csv_metric_sources")
            interfaces = record.pop("_csv_interfaces")
            if not sums:
                continue
            for metric, (total, count) in sums.items():
                record[metric] = total / count
            record["csv_available_metrics"] = list(sums)
            record["csv_metric_sources"] = {
                metric: sorted(metric_sources)
                for metric, metric_sources in sources.items()
            }
            record["csv_interface_count"] = len(interfaces)
            results.append(record)
        return results

    # ---------------------------------------------------------------- NSP auth

    def _get_token(self, force: bool = False) -> Optional[str]:
        if not self.auth_url:
            return self.static_token or None
        if not force and self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        if not self.client_id or not self.client_secret or not self.username or not self.password:
            if self.static_token:
                return self.static_token
            raise ValueError(
                "Nokia Keycloak authentication requires NOKIA_CLIENT_ID, "
                "NOKIA_CLIENT_SECRET, NOKIA_USERNAME, and NOKIA_PASSWORD."
            )
        form_data = urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }).encode("utf-8")
        request = Request(
            self.auth_url,
            data=form_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.request_timeout_sec, context=self._ssl_context) as response:
            payload = json.loads(response.read().decode("utf-8"))
        token = payload.get("access_token")
        if not token:
            raise ValueError("NSP token response did not contain an access_token")
        self._access_token = token
        # Renew a minute early so a request never goes out with an expiring token.
        self._token_expires_at = time.time() + max(60.0, float(payload.get("expires_in", 3600)) - 60.0)
        return token

    def _get_json(self, url: str, token: Optional[str]) -> Any:
        headers = {"Accept": "application/yang-data+json, application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, headers=headers)
        with urlopen(request, timeout=self.request_timeout_sec, context=self._ssl_context) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_json(self, url: str, payload: dict, token: Optional[str] = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("Nokia PM response must be a JSON object")
        return result

    @staticmethod
    def _is_inventory_report_url(payload: Any) -> bool:
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], str):
            return False
        parsed = urlsplit(payload[0])
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.netloc)
            and parsed.path.lower().endswith(".json")
        )

    def _get_json_with_token_refresh(
        self, url: str, token: Optional[str]
    ) -> tuple[Any, Optional[str]]:
        try:
            return self._get_json(url, token), token
        except HTTPError as exc:
            if exc.code != 401 or not self.auth_url:
                raise
            token = self._get_token(force=True)
            return self._get_json(url, token), token

    def _post_json_with_token_refresh(
        self, url: str, payload: dict, token: Optional[str]
    ) -> tuple[dict, Optional[str]]:
        try:
            return self._post_json(url, payload, token), token
        except HTTPError as exc:
            if exc.code != 401 or not self.auth_url:
                raise
            token = self._get_token(force=True)
            return self._post_json(url, payload, token), token

    def _poll_destination(self) -> None:
        token = self._get_token()
        payload, token = self._get_json_with_token_refresh(self.destination_url, token)
        if self._is_inventory_report_url(payload):
            payload, token = self._get_json_with_token_refresh(payload[0], token)
        inventory_devices = self._extract_records(payload)
        inventory_records = self._expand_inventory_records(inventory_devices)
        if self.pmdata_url:
            pm_request = {
                "cnp": self._inventory_node_ids(inventory_devices),
                "cxn": False,
            }
            pm_payload, token = self._post_json_with_token_refresh(
                self.pmdata_url, pm_request, token
            )
            inventory_records = self._merge_inventory_and_pmdata(
                inventory_records, self.normalizer.extract_pm_records(pm_payload)
            )
        self._set_devices(inventory_records)

    @staticmethod
    def _inventory_node_ids(inventory_devices: List[dict]) -> List[str]:
        node_ids = []
        seen = set()
        for device in inventory_devices:
            node_id = (
                device.get("neId")
                or device.get("IpAddress")
                or device.get("userLabel")
            )
            if node_id in (None, ""):
                continue
            node_id = str(node_id).strip()
            if node_id and node_id not in seen:
                seen.add(node_id)
                node_ids.append(node_id)
        return node_ids

    @staticmethod
    def _record_identity(record: dict) -> Optional[tuple[str, ...]]:
        def value(*keys: str) -> str:
            for key in keys:
                candidate = record.get(key)
                if candidate not in (None, ""):
                    return str(candidate).strip().casefold()
            return ""

        ne_id = value("ne_id", "neId", "ne-id")
        if ne_id:
            return ("node", ne_id)

        device_id = value("device_id", "deviceId", "DEVICE-ID")
        if device_id:
            return ("id", device_id)

        chassis_id = value("chassis_id", "chassisId", "CHASSIS-ID")
        if chassis_id:
            return ("node", chassis_id)

        node_id = value(
            "chassis",
            "Chassis",
            "IpAddress",
            "userLabel",
            "nodeName",
            "location",
            "ObjectIdentifier",
            "id",
            "ID",
        )
        shelf = value("shelf_id", "shelfId", "shelf-id", "SHELF", "Shelf", "shelf")
        slot = value("slot_id", "slotId", "slot-id", "SLOT", "Slot", "slot")
        card = value(
            "card_name", "cardName", "card-type", "CARD-NAME", "card", "Card"
        )
        port = value("port_id", "portId", "port-id", "PORT", "Port", "port")
        if node_id and any((shelf, slot, card, port)):
            return ("component", node_id, shelf, slot, card, port)
        if node_id:
            return ("node", node_id)
        for key in (
            "device_id",
            "deviceId",
            "DEVICE-ID",
            "id",
            "ID",
            "identifier",
            "IDENTIFIER",
            "ne-id",
            "neId",
        ):
            value = record.get(key)
            if value not in (None, ""):
                return ("id", str(value).strip().casefold())
        return None

    @classmethod
    def _record_identities(cls, record: dict) -> List[tuple[str, ...]]:
        identities = []
        primary = cls._record_identity(record)
        if primary is not None:
            identities.append(primary)
        for keys, identity_type in (
            (("ne_id", "neId", "ne-id"), "node"),
            (("chassis_id", "chassisId", "CHASSIS-ID"), "node"),
            (
                (
                    "IpAddress",
                    "ipAddress",
                    "ip-address",
                    "userLabel",
                    "nodeName",
                    "location",
                    "ObjectIdentifier",
                ),
                "node",
            ),
            (("device_id", "deviceId", "DEVICE-ID"), "id"),
        ):
            value = next(
                (record[key] for key in keys if record.get(key) not in (None, "")),
                None,
            )
            if value is not None:
                identity = (identity_type, str(value).strip().casefold())
                if identity not in identities:
                    identities.append(identity)
        return identities

    @classmethod
    def _merge_inventory_and_pmdata(
        cls, inventory_records: List[dict], pm_records: List[dict]
    ) -> List[dict]:
        pm_by_id = {}
        for record in pm_records:
            for identity in cls._record_identities(record):
                pm_by_id[identity] = record
        merged_records = []
        for inventory_record in inventory_records:
            pm_record = next(
                (
                    pm_by_id[identity]
                    for identity in cls._record_identities(inventory_record)
                    if identity in pm_by_id
                ),
                None,
            )
            merged_records.append(
                {**inventory_record, **pm_record} if pm_record is not None else inventory_record
            )
        return merged_records

    # ------------------------------------------------------------ parsing

    @staticmethod
    def _extract_records(payload: Any) -> List[dict]:
        if isinstance(payload, list):
            return [record for record in payload if isinstance(record, dict)]
        if not isinstance(payload, dict):
            return []
        if isinstance(payload.get("response"), dict):
            return NokiaTelemetryAdapter._extract_records(payload["response"])
        for key in (
            "devices",
            "data",
            "opResultArgs",
            "nsp-equipment:network-element",
            "network-element",
            "networkelements",
            "networkElements",
            "objGetAllNEResponse",
        ):
            if key in payload:
                return NokiaTelemetryAdapter._extract_records(payload[key])
        # RESTCONF wraps lists in a single "module:container" key.
        if len(payload) == 1:
            only = next(iter(payload.values()))
            return NokiaTelemetryAdapter._extract_records(only)
        return [payload]

    @staticmethod
    def _component_records(record: dict) -> List[dict]:
        hardware = record.get("hardware-component")
        if not isinstance(hardware, dict):
            return [record]
        base = {key: value for key, value in record.items() if key != "hardware-component"}
        shelves = hardware.get("shelf", [])
        components = []
        if isinstance(shelves, dict):
            shelves = [shelves]
        if not isinstance(shelves, list):
            return [record]
        for shelf in shelves:
            if not isinstance(shelf, dict):
                continue
            shelf_record = {**base, **shelf}
            shelf_record["chassis_id"] = record.get("ne-id", record.get("chassis_id", ""))
            shelf_record["shelf_id"] = shelf.get("shelf-id", shelf.get("shelf_id", ""))
            cards = shelf.get("card", [])
            if isinstance(cards, dict):
                cards = [cards]
            if not isinstance(cards, list):
                continue
            for card in cards:
                if not isinstance(card, dict):
                    continue
                card_record = {**shelf_record, **card}
                card_record["slot_id"] = card.get("slot-id", card.get("slot_id", ""))
                card_record["card_name"] = card.get("card-type", card.get("card_name", ""))
                ports = card.get("port", [])
                if isinstance(ports, dict):
                    ports = [ports]
                if isinstance(ports, list) and ports:
                    for port in ports:
                        if isinstance(port, dict):
                            port_record = {**card_record, **port}
                            port_record["device_id"] = port.get(
                                "port-id",
                                port.get("port_id", ""),
                            )
                            port_record["port_id"] = port.get(
                                "port-id",
                                port.get("port_id", ""),
                            )
                            components.append(port_record)
                else:
                    components.append(card_record)
        return components or [record]

    @classmethod
    def _expand_inventory_records(cls, records: List[dict]) -> List[dict]:
        return [
            component
            for record in records
            for component in cls._component_records(record)
        ]

    @staticmethod
    def _from_nsp_network_element(record: dict) -> dict:
        """Maps an NSP nsp-equipment network-element onto the normalizer's field names."""
        if "ne-id" not in record:
            return record
        communication_state = str(record.get("communication-state", "up")).lower()
        admin_state = str(record.get("admin-state", "enabled")).lower()
        oper_state = str(record.get("oper-state", "up")).lower()
        reachable = (
            communication_state in {"up", "connected"}
            and admin_state in {"up", "enable", "enabled", "unlock"}
            and oper_state in {"up", "enabled", "in-service"}
        )
        name = record.get("ne-name") or record.get("name") or record["ne-id"]
        mapped = {k: v for k, v in record.items() if k != "@"}
        mapped.update({
            "device_id": record.get("device_id") or record["ne-id"],
            "name": record.get("name") or record.get("port_id") or name,
            "ne_name": name,
            "type": record.get("type") or record.get("product") or "",
            "node_location": record.get("location") or name,
            "description": f"{record.get('product', '')} v{record.get('version', '')} @ {record.get('ip-address', record['ne-id'])}",
            "health": "Normal" if reachable else "Critical",
            "admin_state": record.get("admin-state", ""),
            "oper_capability": record.get("oper-state", ""),
            "connection_state": record.get("communication-state", ""),
        })
        return mapped

    def _set_devices(self, records: List[Any]) -> None:
        self.devices = {
            device.id: device
            for index, record in enumerate(records)
            if isinstance(record, dict)
            for device in [self.normalizer.normalize_device(self._from_nsp_network_element(record), f"NOKIA-{index + 1:03d}")]
        }
        self._baseline_power_kw = sum(d.telemetry.power_consumption_w for d in self.devices.values()) / 1000.0
