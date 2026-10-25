import io
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models import PowerMode
from app.telemetry import (
    NokiaTelemetryAdapter,
    NokiaTelemetryNormalizer,
    SimulatorAdapter,
    telemetry_provider,
)


def test_simulator_adapter_has_100_devices():
    adapter = SimulatorAdapter()
    assert len(adapter.get_devices()) == 100
    adapter.tick()


def test_nokia_normalizer_maps_optical_counters():
    telemetry = NokiaTelemetryNormalizer().normalize_telemetry({
        "OPT-PWR-TX": "4.2",
        "OPT-PWR-RX": "-10.5",
        "TEMP-DSP": "61.5",
        "PRE-FEC-BER": "2e-5",
        "OSNR": "25.1",
        "UTILIZATION-PCT": "42",
        "POWER-W": "175",
        "LASER-BIAS": "49",
        "Q-FACTOR": "15.2",
        "TIMESTAMP": "1700000000000",
        "FEC UBC": "7",
        "Q-Margin - Min": "14.1",
        "Q-Margin - Max": "16.4",
        "Q-Margin - Average": "15.2",
        "Rx Lane Power 1": "-2.1",
        "Tx Lane Power 4": "3.7",
        "OPR - Average": "-2.6",
        "Expected Network Output Power": "4.0",
        "Measured Network Output Power": "3.8",
        "Laser Case Temperature": "29.1",
        "Admin State": "Unlock",
        "Channel Tx Frequency": "193.1",
        "Grid Step Size": "50",
        "Link Span": "80",
        "OTSiG ID": "OTSiG-1",
        "ETHOCTETS-RX": "1000",
        "CV-PCS": "3",
        "ESNR": "26.8",
    })
    assert telemetry.tx_power_dbm == 4.2
    assert telemetry.rx_power_dbm == -10.5
    assert telemetry.pre_fec_ber == 2e-5
    assert telemetry.power_consumption_w == 175.0
    assert telemetry.timestamp == 1700000000.0
    assert telemetry.fec_ubc == 7
    assert telemetry.q_margin_min_db == 14.1
    assert telemetry.rx_lane_power_1_dbm == -2.1
    assert telemetry.tx_lane_power_4_dbm == 3.7
    assert telemetry.opr_avg_dbm == -2.6
    assert telemetry.measured_network_output_power_dbm == 3.8
    assert telemetry.admin_state == "Unlock"
    assert telemetry.channel_tx_frequency_thz == 193.1
    assert telemetry.eth_octets_rx == 1000
    assert telemetry.cv_pcs == 3
    assert telemetry.esnr_db == 26.8


def test_nokia_normalizer_extracts_wavesuite_pm_records():
    payload = {
        "respCtx": {},
        "opResultArgs": [{
            "neId": "NE-1",
            "dtis": 1792065346145,
            "ports": {
                "PORT-1": {
                    "mgs": {
                        "optical": {
                            "metrics": {
                                "OPR-AVG": {"val": "-8.1"},
                                "OPT-AVG": {"val": "3.4"},
                                "BER": {"val": "2e-5"},
                                "OSNR-DB": {"val": "25.6"},
                                "Q-FACTOR": {"val": "14.9"},
                                "TEMP": {"val": "52"},
                                "POWER-W": {"val": "182"},
                                "UTILIZATION-PCT": {"val": "61.5"},
                            },
                        },
                    },
                },
            },
        }],
    }

    records = NokiaTelemetryNormalizer.extract_pm_records(payload)

    assert len(records) == 1
    assert records[0]["chassis_id"] == "NE-1"
    assert records[0]["port_id"] == "PORT-1"
    assert records[0]["timestamp"] == 1792065346.145
    telemetry = NokiaTelemetryNormalizer().normalize_telemetry(records[0])
    assert telemetry.rx_power_dbm == -8.1
    assert telemetry.tx_power_dbm == 3.4
    assert telemetry.pre_fec_ber == 2e-5
    assert telemetry.osnr_db == 25.6
    assert telemetry.q_factor_db == 14.9
    assert telemetry.dsp_temp_c == 52
    assert telemetry.power_consumption_w == 182
    assert telemetry.traffic_utilization_pct == 61.5

    wrapped_records = NokiaTelemetryNormalizer.extract_pm_records({
        "objCurrentPmData": payload,
    })
    assert wrapped_records == records


def test_nokia_normalizer_maps_wavesuite_inventory_fields():
    device = NokiaTelemetryNormalizer().normalize_device({
        "deviceId": "NMS-DEVICE-1",
        "IpAddress": "192.0.2.10",
        "nodeType": "ROADM",
        "userLabel": "ROADM",
    })

    assert device.id == "NMS-DEVICE-1"
    assert device.name == "ROADM"
    assert device.chassis_id == "192.0.2.10"
    assert device.type.value == "ROADM WSS"
    assert device.raw_record["product"] == "ROADM"

    fallback_device = NokiaTelemetryNormalizer().normalize_device({
        "neId": "NE-2",
        "userLabel": "Chassis-2",
        "productName": "EDFA",
    })
    assert fallback_device.name == "Chassis-2"
    assert fallback_device.node_location == "Chassis-2"
    assert fallback_device.chassis_id == "Chassis-2"
    assert fallback_device.raw_record["product"] == "EDFA"


def test_nokia_adapter_loads_local_samples_and_is_read_only(tmp_path):
    sample_path = tmp_path / "pmdata.json"
    sample_path.write_text(json.dumps([{
        "DEVICE-ID": "TRX-LIVE-001",
        "EQUIPMENT-TYPE": "Transponder-800G",
        "NODE": "NYC",
        "OPT-PWR-TX": 3.5,
        "POWER-W": 200,
    }]), encoding="utf-8")
    adapter = NokiaTelemetryAdapter({"nokia_pmdata_path": str(tmp_path)})
    adapter.initialize()
    assert "TRX-LIVE-001" in adapter.get_devices()
    assert adapter.set_device_power_mode("TRX-LIVE-001", PowerMode.SLEEP) is False


def test_nokia_adapter_loads_csv_snapshot_and_maps_available_metrics(tmp_path):
    csv_path = tmp_path / "15Min_snapshot.csv"
    csv_path.write_text(
        "NE,TP,From,PRE-FEC,BERPreFEC,OPR-AVG,OPT-AVG,ESNR-AVG,BANDWIDTHUTILIZATION,POWER-W,TEMP\n"
        "NE-1,PORT-1,2025-08-22 06:30:00,1e-5,, -10,3,14,20,,\n"
        "NE-1,PORT-2,2025-08-22 06:30:00,3e-5,, -12,5,16,60,,\n"
        "NE-2,PORT-3,2025-08-22 06:30:00,NS,NS,NS,NS,NS,NS,NS,NS\n",
        encoding="utf-8",
    )
    adapter = NokiaTelemetryAdapter({
        "nokia_destination_url": "https://<NSP_HOST>/inventory",
        "nokia_pmdata_path": str(csv_path),
    })
    adapter.initialize()

    assert adapter.last_refresh_status == "snapshot"
    assert adapter.data_origin == "csv_snapshot"
    assert set(adapter.get_devices()) == {"NE-1"}
    device = adapter.get_device("NE-1")
    assert device is not None
    assert device.type.value == "Network Element"
    assert device.telemetry.pre_fec_ber == 2e-5
    assert device.telemetry.rx_power_dbm == -11.0
    assert device.telemetry.tx_power_dbm == 4.0
    assert device.telemetry.esnr_db == 15.0
    assert device.telemetry.traffic_utilization_pct == 40.0
    assert "osnr_db" not in device.raw_record["csv_available_metrics"]
    assert "dsp_temp_c" not in device.raw_record["csv_available_metrics"]
    assert "power_consumption_w" not in device.raw_record["csv_available_metrics"]
    assert device.raw_record["csv_interface_count"] == 2


def test_nokia_adapter_resolves_relative_ca_bundle_from_repository_root():
    expected_ca_path = Path(__file__).resolve().parent / "Certifi" / "ca.pem"
    with patch("app.telemetry.nokia_adapter.ssl.create_default_context") as create_context:
        NokiaTelemetryAdapter({"nokia_ca_bundle": "backend/Certifi/ca.pem"})

    assert create_context.call_args.kwargs["cafile"] == str(expected_ca_path)


def test_nokia_adapter_follows_async_inventory_report_url():
    inventory_url = "https://<NSP_HOST>/networkelements"
    report_url = "https://<NSP_HOST>/data_report/GetAllNEResponse.json"
    inventory = {
        "respCtx": {},
        "opResultArgs": [{
            "deviceId": "PORT-1",
            "neId": "NE-1",
            "IpAddress": "192.0.2.10",
            "nodeType": "ROADM",
            "name": "ROADM 1",
        }],
    }
    responses = {
        inventory_url: [report_url],
        report_url: inventory,
    }
    requests = []
    adapter = NokiaTelemetryAdapter({"nokia_destination_url": inventory_url})
    adapter._get_token = lambda: "test-token"

    def get_json(url, token):
        requests.append((url, token))
        return responses[url]

    adapter._get_json = get_json
    adapter._poll_destination()

    assert requests == [
        (inventory_url, "test-token"),
        (report_url, "test-token"),
    ]
    assert "PORT-1" in adapter.get_devices()
    assert adapter.get_device("PORT-1").chassis_id == "192.0.2.10"


def test_nokia_adapter_posts_json_with_bearer_token():
    adapter = NokiaTelemetryAdapter()
    payload = {"cnp": ["192.0.2.1"], "cxn": False}
    with patch(
        "app.telemetry.nokia_adapter.urlopen",
        return_value=io.BytesIO(b'{"data": []}'),
    ) as mock_urlopen:
        result = adapter._post_json("https://<NSP_HOST>/pm", payload, "test-token")

    request = mock_urlopen.call_args.args[0]
    assert request.get_method() == "POST"
    assert request.data == json.dumps(payload).encode("utf-8")
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("Authorization") == "Bearer test-token"
    assert result == {"data": []}


def test_nokia_adapter_uses_keycloak_password_grant_form():
    env = {
        "NOKIA_CLIENT_ID": "NSP-OSS",
        "NOKIA_CLIENT_SECRET": "test-client-secret",
        "NOKIA_USERNAME": "test-user",
        "NOKIA_PASSWORD": "test-password",
    }
    with patch.dict(os.environ, env, clear=True), patch(
        "app.telemetry.nokia_adapter.urlopen",
        return_value=io.BytesIO(b'{"access_token":"test-access-token","expires_in":3600}'),
    ) as mock_urlopen:
        adapter = NokiaTelemetryAdapter({
            "nokia_auth_url": "https://<NSP_HOST>/auth/token",
        })
        token = adapter._get_token()

    request = mock_urlopen.call_args.args[0]
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert parse_qs(request.data.decode("utf-8")) == {
        "client_id": ["NSP-OSS"],
        "client_secret": ["test-client-secret"],
        "username": ["test-user"],
        "password": ["test-password"],
        "grant_type": ["password"],
    }
    assert token == "test-access-token"


def test_nokia_adapter_get_401_refresh_uses_keycloak_password_grant():
    env = {
        "NOKIA_CLIENT_ID": "NSP-OSS",
        "NOKIA_CLIENT_SECRET": "test-client-secret",
        "NOKIA_USERNAME": "test-user",
        "NOKIA_PASSWORD": "test-password",
    }
    unauthorized = HTTPError(
        "https://<NSP_HOST>/inventory", 401, "Unauthorized", {}, io.BytesIO()
    )
    with patch.dict(os.environ, env, clear=True), patch(
        "app.telemetry.nokia_adapter.urlopen",
        side_effect=[
            unauthorized,
            io.BytesIO(b'{"access_token":"refreshed-token","expires_in":3600}'),
            io.BytesIO(b'{"devices":[]}'),
        ],
    ) as mock_urlopen:
        adapter = NokiaTelemetryAdapter({
            "nokia_auth_url": "https://<NSP_HOST>/auth/token",
        })
        payload, token = adapter._get_json_with_token_refresh(
            "https://<NSP_HOST>/inventory", "expired-token"
        )

    auth_request = mock_urlopen.call_args_list[1].args[0]
    assert auth_request.get_method() == "POST"
    assert auth_request.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert parse_qs(auth_request.data.decode("utf-8")) == {
        "client_id": ["NSP-OSS"],
        "client_secret": ["test-client-secret"],
        "username": ["test-user"],
        "password": ["test-password"],
        "grant_type": ["password"],
    }
    assert payload == {"devices": []}
    assert token == "refreshed-token"


def test_nokia_adapter_pm_401_refresh_uses_keycloak_password_grant():
    env = {
        "NOKIA_CLIENT_ID": "NSP-OSS",
        "NOKIA_CLIENT_SECRET": "test-client-secret",
        "NOKIA_USERNAME": "test-user",
        "NOKIA_PASSWORD": "test-password",
    }
    unauthorized = HTTPError(
        "https://<NSP_HOST>/pm", 401, "Unauthorized", {}, io.BytesIO()
    )
    with patch.dict(os.environ, env, clear=True), patch(
        "app.telemetry.nokia_adapter.urlopen",
        side_effect=[
            unauthorized,
            io.BytesIO(b'{"access_token":"refreshed-token","expires_in":3600}'),
            io.BytesIO(b'{"data":[]}'),
        ],
    ) as mock_urlopen:
        adapter = NokiaTelemetryAdapter({
            "nokia_auth_url": "https://<NSP_HOST>/auth/token",
        })
        payload, token = adapter._post_json_with_token_refresh(
            "https://<NSP_HOST>/pm", {"cnp": ["192.0.2.1"], "cxn": False}, "expired-token"
        )

    auth_request = mock_urlopen.call_args_list[1].args[0]
    assert auth_request.get_method() == "POST"
    assert auth_request.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert parse_qs(auth_request.data.decode("utf-8")) == {
        "client_id": ["NSP-OSS"],
        "client_secret": ["test-client-secret"],
        "username": ["test-user"],
        "password": ["test-password"],
        "grant_type": ["password"],
    }
    assert payload == {"data": []}
    assert token == "refreshed-token"


def test_nokia_adapter_merges_nested_wavesuite_pm_by_port_id():
    inventory_url = "https://<NSP_HOST>/networkelements"
    pm_url = "https://<NSP_HOST>/mncpm/currentpmdata"
    adapter = NokiaTelemetryAdapter({
        "nokia_destination_url": inventory_url,
        "nokia_pmdata_url": pm_url,
        "nokia_ne_ip": "192.0.2.1",
    })
    adapter._get_token = lambda: "test-token"
    adapter._get_json = lambda _url, _token: [{
        "device_id": "PORT-1",
        "neId": "NE-1",
        "chassis_id": "NE-1",
        "port_id": "PORT-1",
    }]
    adapter._post_json = lambda _url, _payload, _token: {
        "respCtx": {},
        "opResultArgs": [{
            "neId": "NE-1",
            "dtis": 1792065346145,
            "ports": {
                "PORT-1": {
                    "mgs": {
                        "optical": {
                            "metrics": {
                                "OPR-AVG": {"val": "-8.1"},
                                "OPT-AVG": {"val": "3.4"},
                                "OSNR-DB": {"val": "25.6"},
                            },
                        },
                    },
                },
            },
        }],
    }

    adapter._poll_destination()

    device = adapter.get_devices()["PORT-1"]
    assert device.chassis_id == "NE-1"
    assert device.telemetry.rx_power_dbm == -8.1
    assert device.telemetry.tx_power_dbm == 3.4
    assert device.telemetry.osnr_db == 25.6
    assert device.telemetry.timestamp == 1792065346.145


def test_nokia_adapter_queries_pm_for_discovered_inventory_nodes():
    inventory_url = "https://<NSP_HOST>/networkelements"
    pm_url = "https://<NSP_HOST>/mncpm/currentpmdata"
    inventory = [
        {"neId": "SITE-A-PSS-32", "userLabel": "Site A"},
        {"IpAddress": "192.0.2.12", "userLabel": "Site B"},
        {"userLabel": "Site C"},
    ]
    adapter = NokiaTelemetryAdapter({
        "nokia_destination_url": inventory_url,
        "nokia_pmdata_url": pm_url,
        "nokia_ne_ip": "192.0.2.1",
    })
    adapter._get_token = lambda: "test-token"
    adapter._get_json = lambda url, _token: inventory
    post_calls = []

    def post_json(url, payload, token=None):
        post_calls.append((url, payload, token))
        return {"data": []}

    adapter._post_json = post_json
    adapter._poll_destination()

    assert post_calls == [
        (
            pm_url,
            {"cnp": ["SITE-A-PSS-32", "192.0.2.12", "Site C"], "cxn": False},
            "test-token",
        )
    ]


def test_nokia_adapter_matches_pm_data_to_inventory_by_ne_id():
    inventory = [{
        "neId": "SITE-A-PSS-32",
        "device_id": "INVENTORY-DEVICE",
        "name": "Site A",
    }]
    pm_records = [{
        "ne_id": "SITE-A-PSS-32",
        "device_id": "PM-PORT",
        "OSNR": "25.7",
    }]

    merged = NokiaTelemetryAdapter._merge_inventory_and_pmdata(inventory, pm_records)

    assert merged == [{
        "neId": "SITE-A-PSS-32",
        "device_id": "PM-PORT",
        "name": "Site A",
        "OSNR": "25.7",
        "ne_id": "SITE-A-PSS-32",
    }]


def test_nokia_adapter_matches_pm_ne_id_to_inventory_user_label():
    inventory = [{
        "userLabel": "SITE-A-PSS-32",
        "device_id": "INVENTORY-DEVICE",
    }]
    pm_records = [{
        "ne_id": "SITE-A-PSS-32",
        "device_id": "PM-PORT",
        "OSNR": "25.7",
    }]

    merged = NokiaTelemetryAdapter._merge_inventory_and_pmdata(inventory, pm_records)

    assert merged[0]["OSNR"] == "25.7"


def test_nokia_normalizer_preserves_server_identity_fields():
    device = NokiaTelemetryNormalizer().normalize_device({
        "deviceId": "vendor-id/42",
        "deviceName": "  nE-Alpha / Card-7  ",
        "neName": "NE Alpha",
        "description": "Original vendor description",
        "equipmentName": "Equipment Alpha",
        "cardName": "Card 7-A",
        "interfaceName": "Ethernet-1/1",
        "shelfId": "Shelf A",
        "slotId": " 3 ",
        "portId": "1/1/1",
        "chassisId": "Chassis-1",
        "equipment_type": "Transponder",
        "NODE": "New York",
        "POWER-W": "100",
    })

    assert device.id == "vendor-id/42"
    assert device.name == "  nE-Alpha / Card-7  "
    assert device.ne_name == "NE Alpha"
    assert device.description == "Original vendor description"
    assert device.equipment_name == "Equipment Alpha"
    assert device.card_name == "Card 7-A"
    assert device.interface_name == "Ethernet-1/1"
    assert device.shelf_id == "Shelf A"
    assert device.slot_id == " 3 "
    assert device.port_id == "1/1/1"
    assert device.chassis_id == "Chassis-1"


def test_nokia_adapter_merges_pm_records_by_matching_device_id_only():
    inventory = [
        {"ne-id": "NE-1", "device_id": "PORT-1", "name": "Port 1"},
        {"ne-id": "NE-2", "device_id": "PORT-2", "name": "Port 2"},
    ]
    pmdata = [
        {"device_id": "PORT-1", "OSNR": 25.1, "POWER-W": 175},
        {"device_id": "UNKNOWN-PORT", "OSNR": 20.0},
    ]

    merged = NokiaTelemetryAdapter._merge_inventory_and_pmdata(inventory, pmdata)

    assert merged == [
        {"ne-id": "NE-1", "device_id": "PORT-1", "name": "Port 1", "OSNR": 25.1, "POWER-W": 175},
        {"ne-id": "NE-2", "device_id": "PORT-2", "name": "Port 2"},
    ]


def test_nokia_adapter_polls_inventory_and_pm_endpoints_and_normalizes_live_metrics():
    inventory_url = "https://<NSP_HOST>/inventory"
    pmdata_url = "https://<NSP_HOST>/pm"
    payloads = {
        inventory_url: [{"device_id": "PORT-1", "name": "Port 1", "CHASSIS-ID": "CH-1"}],
        pmdata_url: {
            "data": [{
                "device_id": "PORT-1",
                "UTILIZATION-PCT": "62.5",
                "PRE-FEC-BER": "0.000024",
                "OSNR": "26.4",
                "Q-FACTOR": "14.8",
                "OPT-PWR-TX": "3.5",
                "OPT-PWR-RX": "-11.8",
                "POWER-W": "185",
                "TEMP-DSP": "54",
                "TIMESTAMP": "1700000000000",
            }],
        },
    }
    adapter = NokiaTelemetryAdapter({
        "nokia_destination_url": inventory_url,
        "nokia_pmdata_url": pmdata_url,
        "nokia_ne_ip": "192.0.2.1",
    })
    adapter._get_token = lambda: "test-token"
    adapter._get_json = lambda url, _token: payloads[url]
    post_calls = []

    def post_json(url, payload, token):
        post_calls.append((url, payload, token))
        return payloads[url]

    adapter._post_json = post_json

    adapter._poll_destination()

    assert post_calls == [
        (pmdata_url, {"cnp": [], "cxn": False}, "test-token")
    ]
    device = adapter.get_devices()["PORT-1"]
    assert device.chassis_id == "CH-1"
    assert device.telemetry.traffic_utilization_pct == 62.5
    assert device.telemetry.pre_fec_ber == 0.000024
    assert device.telemetry.osnr_db == 26.4
    assert device.telemetry.q_factor_db == 14.8
    assert device.telemetry.tx_power_dbm == 3.5
    assert device.telemetry.rx_power_dbm == -11.8
    assert device.telemetry.power_consumption_w == 185.0
    assert device.telemetry.dsp_temp_c == 54.0
    assert device.telemetry.timestamp == 1700000000.0


def test_nokia_adapter_prefers_live_endpoint_over_local_samples():
    adapter = NokiaTelemetryAdapter({"nokia_destination_url": "https://<NSP_HOST>/inventory"})
    adapter._load_local_samples = lambda: True
    adapter._poll_destination = lambda: None

    adapter.refresh()

    assert adapter.data_origin == "live_destination"
    assert adapter.last_refresh_status == "no_data"


def test_nokia_normalizer_uses_explicit_unavailable_name_without_fabrication():
    device = NokiaTelemetryNormalizer().normalize_device({
        "DEVICE-ID": "server-id-7",
        "NE-NAME": "NE-7",
        "SHELF": "Shelf-7",
        "POWER-W": "100",
    }, fallback_id="NOKIA-001")

    assert device.id == "server-id-7"
    assert device.name == "Name unavailable"
    assert device.ne_name == "NE-7"
    assert device.shelf_id == "Shelf-7"


def test_provider_switches_sources():
    telemetry_provider.set_source_mode("simulator")
    assert telemetry_provider.source_mode == "simulator"
    assert len(telemetry_provider.get_devices()) == 100
    telemetry_provider.set_source_mode("nokia")
    assert telemetry_provider.source_mode == "nokia"
    assert set(telemetry_provider.get_devices()) == {"NOKIA-001", "NOKIA-003"}
    telemetry_provider.set_source_mode("simulator")
