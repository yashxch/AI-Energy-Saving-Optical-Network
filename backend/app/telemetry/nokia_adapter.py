import csv
import io
import json
import math
import os
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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


@dataclass
class UploadedCsvResult:
    slot: str
    filename: str
    device_id: str
    device_name: str
    accepted_rows: int
    rejected_rows: int
    skipped_rows: int
    rejected_reasons: List[str]
    metric_mapping: Dict[str, Dict[str, Any]]
    latest_timestamp: str
    assumed_timezone: str
    history: List[Dict[str, Any]]


CSV_REQUIRED_METRICS: Dict[str, Dict[str, Any]] = {
    "traffic_load_pct": {
        "field": "traffic_utilization_pct",
        "label": "Traffic utilization",
        "unit": "%",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": True,
    },
    "pre_fec_ber": {
        "field": "pre_fec_ber",
        "label": "Pre-FEC BER",
        "unit": "ratio",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": True,
    },
    "osnr_db": {
        "field": "osnr_db",
        "label": "OSNR",
        "unit": "dB",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": True,
    },
    "dsp_temp_c": {
        "field": "dsp_temp_c",
        "label": "DSP temperature",
        "unit": "°C",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
    "power_draw_w": {
        "field": "power_consumption_w",
        "label": "Power draw",
        "unit": "W",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": True,
    },
    "tx_optical_power_dbm": {
        "field": "tx_power_dbm",
        "label": "Tx optical power",
        "unit": "dBm",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
    "rx_optical_power_dbm": {
        "field": "rx_power_dbm",
        "label": "Rx optical power",
        "unit": "dBm",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
    "laser_bias_current_ma": {
        "field": "laser_bias_ma",
        "label": "Laser bias current",
        "unit": "mA",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
    "laser_temp_c": {
        "field": "laser_temp_c",
        "label": "Laser temperature",
        "unit": "°C",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
    "module_temp_c": {
        "field": "module_temp_c",
        "label": "Module temperature",
        "unit": "°C",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
    "post_fec_ber": {
        "field": "post_fec_ber",
        "label": "Post-FEC BER",
        "unit": "ratio",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": True,
    },
    "q_factor_db": {
        "field": "q_factor_db",
        "label": "Q factor",
        "unit": "dB",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": True,
    },
    "chromatic_dispersion_ps_nm": {
        "field": "chromatic_dispersion",
        "label": "Chromatic dispersion",
        "unit": "ps/nm",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
    "fan_rpm": {
        "field": "fan_rpm",
        "label": "Fan speed",
        "unit": "rpm",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
    "supply_voltage_v": {
        "field": "voltage_v",
        "label": "Supply voltage",
        "unit": "V",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
    "current_draw_a": {
        "field": "current_a",
        "label": "Current draw",
        "unit": "A",
        "data_type": "number",
        "required": True,
        "chartable": True,
        "alertable": True,
        "power_calc": False,
    },
}


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
        self.project_csv_paths = []
        for csv_path in config.get("nokia_csv_files", []):
            path = Path(csv_path)
            if not path.is_absolute():
                path = REPOSITORY_DIR / path
            self.project_csv_paths.append(path)
        self.nokia_execution_enabled = bool(config.get("nokia_execution_enabled", False))
        self.telemetry_stale_timeout_sec = float(
            config.get("telemetry_stale_timeout_sec", 30.0)
        )
        self.minimum_power_observation_sec = float(
            config.get("minimum_power_observation_sec", 900.0)
        )
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
        self._uploaded_csv_active = False
        self._uploaded_csv_status: Dict[str, Any] = {
            "ingestion_status": "not_loaded",
            "device_count": 0,
            "devices": {},
            "last_ingested_at": None,
            "record_limit": 20000,
            "size_limit_bytes": 2 * 1024 * 1024,
        }

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
        if self.data_origin in {"csv_snapshot", "uploaded_csv", "project_csv"}:
            return
        if time.time() - self._last_poll_at >= self.poll_interval_sec:
            self.refresh()

    def refresh(self) -> None:
        self._last_poll_at = time.time()
        self.last_refresh_status = "refreshing"
        self.last_refresh_error = None
        try:
            if self.project_csv_paths:
                self.ingest_uploaded_csv_files([
                    (path.name, path.read_bytes()) for path in self.project_csv_paths
                ])
                self.data_origin = "project_csv"
                self.last_refresh_status = "snapshot"
                return
            if self._uploaded_csv_active:
                self.data_origin = "uploaded_csv"
                self.last_refresh_status = "snapshot" if self.devices else "no_data"
                return
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
            self._uploaded_csv_status = {
                **self._uploaded_csv_status,
                "ingestion_status": "error",
                "device_count": 0,
                "devices": {},
            }
            print(f"Warning polling Nokia telemetry destination: {exc}")

    def get_uploaded_csv_status(self) -> Dict[str, Any]:
        return dict(self._uploaded_csv_status)

    @property
    def is_historical_csv(self) -> bool:
        return self.data_origin in {"uploaded_csv", "project_csv"}

    def ingest_uploaded_csv_files(
        self, file_payloads: List[Tuple[str, bytes]]
    ) -> Dict[str, Any]:
        if len(file_payloads) != 2:
            raise ValueError("Exactly two CSV files are required.")

        parsed_results = []
        used_device_ids = set()
        for index, payload in enumerate(file_payloads, start=1):
            filename, content = payload
            slot = f"device_{index}"
            result = self._parse_uploaded_csv_file(slot, filename, content)
            if result.device_id in used_device_ids:
                raise ValueError(
                    f"Both CSV files resolved to the same device ID '{result.device_id}'. "
                    "Upload two different device-specific files."
                )
            used_device_ids.add(result.device_id)
            parsed_results.append(result)

        devices: Dict[str, Device] = {}
        status_devices: Dict[str, Any] = {}
        for result in parsed_results:
            device = self._normalize_uploaded_result(result)
            devices[device.id] = device
            status_devices[result.slot] = self._result_status(result)

        self.devices = devices
        self._uploaded_csv_active = True
        self.data_origin = "uploaded_csv"
        self.last_refresh_status = "snapshot"
        self.last_refresh_error = None
        self._uploaded_csv_status = {
            "ingestion_status": "ready",
            "device_count": len(self.devices),
            "devices": status_devices,
            "last_ingested_at": datetime.now(timezone.utc).isoformat(),
            "record_limit": 20000,
            "size_limit_bytes": 2 * 1024 * 1024,
        }
        self._update_uploaded_baseline()
        return self.get_uploaded_csv_status()

    def preview_uploaded_csv_file(
        self,
        slot: str,
        filename: str,
        content: bytes,
        assigned_device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if slot not in {"device_1", "device_2"}:
            raise ValueError("Device slot must be 'device_1' or 'device_2'.")
        result = self._parse_uploaded_csv_file(
            slot, filename, content, assigned_device_id
        )
        self._validate_uploaded_slot(slot, result)
        status = self._result_status(result)
        status["latest_metrics"] = result.history[-1]["metrics"]
        return status

    def ingest_uploaded_csv_file(
        self,
        slot: str,
        filename: str,
        content: bytes,
        assigned_device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if slot not in {"device_1", "device_2"}:
            raise ValueError("Device slot must be 'device_1' or 'device_2'.")

        result = self._parse_uploaded_csv_file(
            slot, filename, content, assigned_device_id
        )
        self._validate_uploaded_slot(slot, result)
        device = self._normalize_uploaded_result(result)
        if not self._uploaded_csv_active:
            self.devices = {}
        previous_slot = self._uploaded_csv_status.get("devices", {}).get(slot)
        if previous_slot:
            self.devices.pop(previous_slot["device_id"], None)
        self.devices[device.id] = device

        status_devices = (
            dict(self._uploaded_csv_status.get("devices", {}))
            if self._uploaded_csv_active
            else {}
        )
        status_devices[slot] = self._result_status(result)
        self._uploaded_csv_active = True
        self.data_origin = "uploaded_csv"
        self.last_refresh_status = "snapshot"
        self.last_refresh_error = None
        self._uploaded_csv_status = {
            "ingestion_status": "ready" if len(status_devices) == 2 else "partial",
            "device_count": len(self.devices),
            "devices": status_devices,
            "last_ingested_at": datetime.now(timezone.utc).isoformat(),
            "record_limit": 20000,
            "size_limit_bytes": 2 * 1024 * 1024,
        }
        self._update_uploaded_baseline()
        return self.get_uploaded_csv_status()

    def _validate_uploaded_slot(self, slot: str, result: UploadedCsvResult) -> None:
        other_slot = "device_2" if slot == "device_1" else "device_1"
        other_device = self._uploaded_csv_status.get("devices", {}).get(other_slot)
        if other_device and other_device["device_id"] == result.device_id:
            raise ValueError(
                f"Device ID '{result.device_id}' is already assigned to {other_slot}."
            )
        previous_slot = self._uploaded_csv_status.get("devices", {}).get(slot)
        if previous_slot and previous_slot["device_id"] != result.device_id:
            raise ValueError(
                f"{slot} is assigned to '{previous_slot['device_id']}', but this file "
                f"contains '{result.device_id}'. Upload the matching device file."
            )

    def _update_uploaded_baseline(self) -> None:
        self._baseline_power_kw = sum(
            device.telemetry.power_consumption_w for device in self.devices.values()
        ) / 1000.0

    def _normalize_uploaded_result(self, result: UploadedCsvResult) -> Device:
        latest_record = result.history[-1]
        raw_record = self._to_normalizer_record(result, latest_record)
        return self.normalizer.normalize_device(raw_record, result.device_id)

    def _result_status(self, result: UploadedCsvResult) -> Dict[str, Any]:
        observation_duration = max(
            0.0,
            result.history[-1]["timestamp_epoch"] - result.history[0]["timestamp_epoch"],
        )
        telemetry_age = max(0.0, time.time() - result.history[-1]["timestamp_epoch"])
        telemetry_stale = telemetry_age > self.telemetry_stale_timeout_sec
        reasons = []
        if observation_duration < self.minimum_power_observation_sec:
            reasons.append(
                f"Only {observation_duration:.0f} seconds are observed; "
                f"{self.minimum_power_observation_sec:.0f} seconds are required."
            )
        if telemetry_stale:
            reasons.append(
                f"The latest sample is {telemetry_age:.0f} seconds old, exceeding "
                f"the {self.telemetry_stale_timeout_sec:.0f}-second stale limit."
            )
        reasons.append(
            "Supported low-power modes, protected service capacity, and current "
            "device state are not verified."
        )
        return {
            "filename": result.filename,
            "device_id": result.device_id,
            "device_name": result.device_name,
            "accepted_rows": result.accepted_rows,
            "rejected_rows": result.rejected_rows,
            "skipped_rows": result.skipped_rows,
            "latest_timestamp": result.latest_timestamp,
            "assumed_timezone": result.assumed_timezone,
            "rejected_reasons": result.rejected_reasons,
            "metric_mapping": result.metric_mapping,
            "observation_duration_seconds": observation_duration,
            "telemetry_age_seconds": telemetry_age,
            "telemetry_stale": telemetry_stale,
            "power_saving_status": "Not eligible",
            "power_saving_reason": " ".join(reasons)
            + " No power-saving action or savings estimate is authorized.",
        }

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

    @staticmethod
    def _device_id_column(headers: List[str]) -> Optional[str]:
        for header in headers:
            normalized = header.strip().lower()
            if normalized.startswith("device id"):
                return header
        for candidate in ("device_id", "device id"):
            for header in headers:
                if header.strip().lower() == candidate:
                    return header
        return None

    @staticmethod
    def _decode_csv_payload(content: bytes, filename: str, size_limit: int) -> str:
        if len(content) > size_limit:
            raise ValueError(
                f"{filename}: file size exceeds the {size_limit // (1024 * 1024)} MB limit."
            )
        for encoding in ("utf-8-sig", "utf-8"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError(
            f"{filename}: unsupported encoding. Use UTF-8 CSV files."
        )

    @staticmethod
    def _parse_timestamp(value: Any) -> Tuple[Optional[datetime], str]:
        if value is None:
            return None, "missing timestamp"
        text = str(value).strip()
        if not text:
            return None, "missing timestamp"
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None, f"invalid timestamp '{text}'"
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed, "UTC (assumed for timezone-free timestamps)"
        return parsed, "embedded in timestamp"

    @classmethod
    def _required_metric_mapping(
        cls, headers: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        headers_by_normalized = {
            header.strip().casefold(): header for header in (headers or [])
        }
        return {
            headers_by_normalized.get(header.casefold(), header): {
                "original_header": headers_by_normalized.get(header.casefold(), header),
                "internal_field": spec["field"],
                "display_label": spec["label"],
                "unit": spec["unit"],
                "data_type": spec["data_type"],
                "validation_rules": (
                    "Finite numeric value from 0 through 100."
                    if header == "traffic_load_pct"
                    else "Finite numeric value; must be zero or greater."
                    if header in {"pre_fec_ber", "post_fec_ber"}
                    else "Finite numeric value."
                ),
                "required": spec["required"],
                "chartable": spec["chartable"],
                "alertable": spec["alertable"],
                "power_calc": spec["power_calc"],
            }
            for header, spec in CSV_REQUIRED_METRICS.items()
        }

    def _parse_uploaded_csv_file(
        self,
        slot: str,
        filename: str,
        content: bytes,
        assigned_device_id: Optional[str] = None,
    ) -> UploadedCsvResult:
        limits = self._uploaded_csv_status
        text = self._decode_csv_payload(content, filename, int(limits["size_limit_bytes"]))
        if not text.strip():
            raise ValueError(f"{filename}: file is empty.")
        sample = text[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
        original_headers = reader.fieldnames or []
        headers = [header.strip() if header else "" for header in original_headers]
        reader.fieldnames = headers
        if not headers:
            raise ValueError(f"{filename}: missing CSV headers.")
        if any(not header for header in headers):
            raise ValueError(f"{filename}: contains an empty column header.")
        if len({header.casefold() for header in headers}) != len(headers):
            raise ValueError(f"{filename}: contains duplicate column headers.")

        headers_by_normalized = {header.casefold(): header for header in headers}
        missing_headers = [
            h for h in CSV_REQUIRED_METRICS if h.casefold() not in headers_by_normalized
        ]
        if missing_headers:
            raise ValueError(
                f"{filename}: missing required telemetry columns: {', '.join(missing_headers)}."
            )

        if "timestamp" not in headers_by_normalized:
            raise ValueError(f"{filename}: missing required timestamp column.")
        timestamp_column = headers_by_normalized["timestamp"]

        device_column = self._device_id_column(headers)
        assigned_device_id = (assigned_device_id or "").strip()
        if not device_column and not assigned_device_id:
            raise ValueError(
                f"{filename}: missing device identifier column. Enter an assigned device ID to continue."
            )

        rows = list(reader)
        if not rows:
            raise ValueError(f"{filename}: file is empty.")
        if len(rows) > int(limits["record_limit"]):
            raise ValueError(
                f"{filename}: row count {len(rows)} exceeds limit {int(limits['record_limit'])}."
            )

        accepted = []
        rejected_rows = 0
        skipped_rows = 0
        reasons: Dict[str, int] = {}
        device_ids = set()
        seen_timestamps = set()
        timezone_note = "embedded in timestamp"

        for row in rows:
            device_id = (
                str(row.get(device_column, "")).strip()
                if device_column
                else assigned_device_id
            )
            if not device_id:
                rejected_rows += 1
                reasons["missing device identifier"] = reasons.get("missing device identifier", 0) + 1
                continue
            if assigned_device_id and device_column and device_id != assigned_device_id:
                raise ValueError(
                    f"{filename}: CSV device ID '{device_id}' does not match the "
                    f"assigned device ID '{assigned_device_id}'."
                )
            device_ids.add(device_id)

            parsed_ts, ts_note = self._parse_timestamp(row.get(timestamp_column))
            if parsed_ts is None:
                rejected_rows += 1
                reasons[ts_note] = reasons.get(ts_note, 0) + 1
                continue
            if ts_note.startswith("UTC"):
                timezone_note = ts_note

            numeric_fields: Dict[str, float] = {}
            invalid_field = None
            for source_field, spec in CSV_REQUIRED_METRICS.items():
                actual_header = headers_by_normalized[source_field.casefold()]
                value = self._csv_number(row.get(actual_header))
                if value is None:
                    invalid_field = source_field
                    break
                if source_field == "traffic_load_pct" and not 0 <= value <= 100:
                    invalid_field = source_field
                    break
                if source_field in {"pre_fec_ber", "post_fec_ber"} and value < 0:
                    invalid_field = source_field
                    break
                numeric_fields[spec["field"]] = value
            if invalid_field:
                rejected_rows += 1
                reason = f"invalid numeric value in {invalid_field}"
                reasons[reason] = reasons.get(reason, 0) + 1
                continue

            timestamp_key = parsed_ts.astimezone(timezone.utc).isoformat()
            if row.get(None):
                rejected_rows += 1
                reasons["row contains extra values beyond the header"] = (
                    reasons.get("row contains extra values beyond the header", 0) + 1
                )
                continue
            if timestamp_key in seen_timestamps:
                skipped_rows += 1
                reasons["duplicate timestamp"] = reasons.get("duplicate timestamp", 0) + 1
                continue
            seen_timestamps.add(timestamp_key)

            accepted.append({
                "timestamp": str(row.get(timestamp_column, "")).strip(),
                "timestamp_utc": timestamp_key,
                "timestamp_epoch": parsed_ts.timestamp(),
                "power_mode": str(row.get(headers_by_normalized.get("power_mode", ""), "")).strip(),
                "device_id": device_id,
                "device_name": str(row.get(headers_by_normalized.get("device name", ""), "")).strip() or device_id,
                "node_location": str(row.get(headers_by_normalized.get("location", ""), "")).strip(),
                "device_type": str(row.get(headers_by_normalized.get("device_type", ""), "")).strip(),
                "original_metrics": {
                    headers_by_normalized[source_field.casefold()]: str(
                        row.get(headers_by_normalized[source_field.casefold()], "")
                    ).strip()
                    for source_field in CSV_REQUIRED_METRICS
                },
                "metrics": numeric_fields,
            })

        if len(device_ids) != 1:
            raise ValueError(
                f"{filename}: file contains multiple device IDs ({', '.join(sorted(device_ids))})."
            )
        if not accepted:
            reason_list = [f"{message} ({count})" for message, count in sorted(reasons.items())]
            reasons_text = f" Reasons: {', '.join(reason_list)}." if reason_list else ""
            raise ValueError(
                f"{filename}: no valid rows after validation (accepted 0, "
                f"rejected {rejected_rows}, skipped {skipped_rows}).{reasons_text}"
            )

        accepted.sort(key=lambda item: item["timestamp_epoch"])
        latest_timestamp = accepted[-1]["timestamp_utc"]
        reason_list = [f"{message} ({count})" for message, count in sorted(reasons.items())]
        return UploadedCsvResult(
            slot=slot,
            filename=filename,
            device_id=next(iter(device_ids)),
            device_name=accepted[-1]["device_name"],
            accepted_rows=len(accepted),
            rejected_rows=rejected_rows,
            skipped_rows=skipped_rows,
            rejected_reasons=reason_list,
            metric_mapping=self._required_metric_mapping(headers),
            latest_timestamp=latest_timestamp,
            assumed_timezone=timezone_note,
            history=accepted,
        )

    @staticmethod
    def _to_normalizer_record(
        result: UploadedCsvResult, latest_record: Dict[str, Any]
    ) -> Dict[str, Any]:
        metrics = latest_record["metrics"]
        return {
            "device_id": result.device_id,
            "name": result.device_name,
            "node_location": latest_record["node_location"],
            "target_node": "",
            "power_mode": latest_record["power_mode"] or "Unknown",
            "health": "Unknown",
            "type": latest_record["device_type"],
            "timestamp": latest_record["timestamp_epoch"],
            "device_name": result.device_name,
            "description": f"Uploaded CSV device ({result.filename})",
            "csv_available_metrics": sorted(metrics.keys()),
            "csv_metric_mapping": result.metric_mapping,
            "csv_history": result.history,
            "csv_ingestion": {
                "accepted_rows": result.accepted_rows,
                "rejected_rows": result.rejected_rows,
                "skipped_rows": result.skipped_rows,
                "latest_timestamp": result.latest_timestamp,
                "assumed_timezone": result.assumed_timezone,
                "filename": result.filename,
                "slot": result.slot,
                "rejected_reasons": result.rejected_reasons,
            },
            **metrics,
        }

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
