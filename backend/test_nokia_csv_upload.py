import csv
import io

import pytest
from fastapi import HTTPException
from app.telemetry.nokia_adapter import CSV_REQUIRED_METRICS, NokiaTelemetryAdapter
from app.quantum_optimizer import analyze_devices_with_local_qaoa
from app.telemetry import telemetry_provider
from app.llm_engine import llm_engine
from app.models import ActionType, WhatIfSimulationRequest
from app.digital_twin import digital_twin_engine
from app.main import (
    analyze_current_telemetry_with_local_qaoa,
    execute_digital_twin_action,
    simulate_what_if_scenario,
)


METADATA = [
    "Device ID",
    "Device Name",
    "device_type",
    "location",
    "timestamp",
    "power_mode",
]


def make_row(device_id: str, timestamp: str, traffic: float = 42.0) -> dict:
    row = {
        "Device ID": device_id,
        "Device Name": f"Device {device_id}",
        "device_type": "Transponder- S4X400",
        "location": "Test site",
        "timestamp": timestamp,
        "power_mode": "Normal",
        "traffic_load_pct": traffic,
        "pre_fec_ber": 1e-6,
        "osnr_db": 25.0,
        "dsp_temp_c": 50.0,
        "power_draw_w": 100.0,
        "tx_optical_power_dbm": 3.0,
        "rx_optical_power_dbm": -11.0,
        "laser_bias_current_ma": 49.0,
        "laser_temp_c": 38.0,
        "module_temp_c": 45.0,
        "post_fec_ber": 1e-12,
        "q_factor_db": 16.0,
        "chromatic_dispersion_ps_nm": 320.0,
        "fan_rpm": 4800.0,
        "supply_voltage_v": 12.0,
        "current_draw_a": 8.0,
    }
    return row


def make_csv(rows: list[dict], headers: list[str] | None = None) -> bytes:
    fields = headers or METADATA + list(CSV_REQUIRED_METRICS)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def test_preview_and_ingestion_keep_device_histories_separate_and_replace_one_slot():
    adapter = NokiaTelemetryAdapter()
    first = make_csv([
        make_row("NOKIA-001", "2026-10-22T10:00:00", 30),
        make_row("NOKIA-001", "2026-10-22T10:00:01", 35),
    ])
    second = make_csv([
        make_row("NOKIA-003", "2026-10-22T19:00:00", 70),
        make_row("NOKIA-003", "2026-10-22T19:00:01", 75),
    ], list(reversed(METADATA + list(CSV_REQUIRED_METRICS))))

    preview = adapter.preview_uploaded_csv_file("device_1", "first.csv", first)
    assert adapter.get_devices() == {}
    assert len(preview["metric_mapping"]) == 16
    assert preview["accepted_rows"] == 2

    adapter.ingest_uploaded_csv_file("device_1", "first.csv", first)
    adapter.ingest_uploaded_csv_file("device_2", "second.csv", second)
    assert set(adapter.get_devices()) == {"NOKIA-001", "NOKIA-003"}
    first_status = adapter.get_uploaded_csv_status()["devices"]["device_1"]
    assert first_status["observation_duration_seconds"] == 1
    assert first_status["telemetry_stale"] is True
    assert first_status["power_saving_status"] == "Not eligible"
    assert len(adapter.get_device("NOKIA-001").raw_record["csv_history"]) == 2
    assert len(adapter.get_device("NOKIA-003").raw_record["csv_history"]) == 2
    assert adapter.get_device("NOKIA-001").telemetry.traffic_utilization_pct == 35
    assert adapter.get_device("NOKIA-003").telemetry.traffic_utilization_pct == 75
    assert adapter.get_device("NOKIA-001").telemetry.ber is None
    assert adapter.get_device("NOKIA-001").wavelength_nm is None
    assert adapter.get_device("NOKIA-001").health.value == "Unknown"
    assert adapter.get_device("NOKIA-001").type.value == "Transponder"
    assert len(adapter.get_device("NOKIA-001").raw_record["csv_history"][0]["metrics"]) == 16
    assert len(adapter.get_device("NOKIA-001").raw_record["csv_history"][0]["original_metrics"]) == 16

    adapter.ingest_uploaded_csv_file("device_1", "first.csv", first)
    assert len(adapter.get_device("NOKIA-001").raw_record["csv_history"]) == 2
    assert adapter.get_uploaded_csv_status()["devices"]["device_1"]["accepted_rows"] == 2

    replacement = make_csv([
        make_row("NOKIA-001", "2026-10-23T10:00:00", 10),
    ])
    adapter.ingest_uploaded_csv_file("device_1", "replacement.csv", replacement)
    assert set(adapter.get_devices()) == {"NOKIA-001", "NOKIA-003"}
    assert adapter.get_device("NOKIA-001").telemetry.traffic_utilization_pct == 10
    assert adapter.get_device("NOKIA-003").telemetry.traffic_utilization_pct == 75
    assert adapter.get_uploaded_csv_status()["devices"]["device_1"]["accepted_rows"] == 1


def test_parser_reports_bad_rows_and_deduplicates_equivalent_instants():
    adapter = NokiaTelemetryAdapter()
    valid = make_row("NOKIA-001", "2026-10-22T10:00:00")
    equivalent_duplicate = make_row("NOKIA-001", "2026-10-22T12:00:00+02:00")
    invalid_number = make_row("NOKIA-001", "2026-10-22T10:00:02")
    invalid_number["osnr_db"] = "not-a-number"
    missing_timestamp = make_row("NOKIA-001", "")

    preview = adapter.preview_uploaded_csv_file(
        "device_1",
        "rows.csv",
        make_csv([valid, equivalent_duplicate, invalid_number, missing_timestamp]),
    )
    assert preview["accepted_rows"] == 1
    assert preview["skipped_rows"] == 1
    assert preview["rejected_rows"] == 2
    assert any("duplicate timestamp (1)" in reason for reason in preview["rejected_reasons"])
    assert any("invalid numeric value in osnr_db (1)" in reason for reason in preview["rejected_reasons"])


def test_missing_required_metric_and_multiple_device_ids_are_rejected():
    adapter = NokiaTelemetryAdapter()
    headers = METADATA + list(CSV_REQUIRED_METRICS)
    missing_metric_headers = [header for header in headers if header != "q_factor_db"]
    with pytest.raises(ValueError, match="missing required telemetry columns"):
        adapter.preview_uploaded_csv_file(
            "device_1",
            "missing.csv",
            make_csv([make_row("NOKIA-001", "2026-10-22T10:00:00")], missing_metric_headers),
        )

    with pytest.raises(ValueError, match="multiple device IDs"):
        adapter.preview_uploaded_csv_file(
            "device_1",
            "mixed.csv",
            make_csv([
                make_row("NOKIA-001", "2026-10-22T10:00:00"),
                make_row("NOKIA-003", "2026-10-22T10:00:01"),
            ]),
        )


def test_invalid_traffic_range_and_invalid_encoding_are_rejected():
    adapter = NokiaTelemetryAdapter()
    bad_traffic = make_row("NOKIA-001", "2026-10-22T10:00:00", 101)
    with pytest.raises(ValueError, match="no valid rows"):
        adapter.preview_uploaded_csv_file(
            "device_1", "traffic.csv", make_csv([bad_traffic])
        )
    with pytest.raises(ValueError, match="unsupported encoding"):
        adapter.preview_uploaded_csv_file("device_1", "invalid.csv", b"\xff\xfe\xfd")


def test_missing_id_column_requires_user_assignment_and_replacements_keep_slot_identity():
    adapter = NokiaTelemetryAdapter()
    headers = [header for header in METADATA + list(CSV_REQUIRED_METRICS) if header != "Device ID"]
    payload = make_csv(
        [make_row("ignored-without-id-column", "2026-10-22T10:00:00")],
        headers,
    )
    with pytest.raises(ValueError, match="Enter an assigned device ID"):
        adapter.preview_uploaded_csv_file("device_1", "no-id.csv", payload)

    preview = adapter.preview_uploaded_csv_file(
        "device_1", "no-id.csv", payload, assigned_device_id="ASSIGNED-1"
    )
    assert preview["device_id"] == "ASSIGNED-1"
    adapter.ingest_uploaded_csv_file(
        "device_1", "no-id.csv", payload, assigned_device_id="ASSIGNED-1"
    )
    with pytest.raises(ValueError, match="is assigned to"):
        adapter.ingest_uploaded_csv_file(
            "device_1",
            "different-device.csv",
            make_csv([make_row("OTHER-ID", "2026-10-22T10:00:01")]),
        )


def test_uploaded_csv_chat_uses_device_data_and_never_recommends_control(monkeypatch):
    adapter = NokiaTelemetryAdapter()
    adapter.ingest_uploaded_csv_files([
        ("first.csv", make_csv([make_row("NOKIA-001", "2026-10-22T10:00:00", 35)])),
        ("second.csv", make_csv([make_row("NOKIA-003", "2026-10-22T19:00:00", 75)])),
    ])
    monkeypatch.setattr(telemetry_provider, "adapter", adapter)
    monkeypatch.setattr(telemetry_provider, "nokia_adapter", adapter)
    monkeypatch.setattr(telemetry_provider, "_source_mode", "nokia")

    answer = llm_engine.process_chat_query("What is the load on NOKIA-001?")
    assert "project CSV" in answer
    assert "35.00%" in answer
    assert llm_engine.get_recommendations() == []


def test_refresh_loads_only_configured_project_csv_files(tmp_path):
    first = tmp_path / "device-one.csv"
    second = tmp_path / "device-two.csv"
    legacy_snapshot = tmp_path / "legacy-865-device-snapshot.csv"
    first.write_bytes(make_csv([make_row("NOKIA-001", "2026-10-22T10:00:00")]))
    second.write_bytes(make_csv([make_row("NOKIA-003", "2026-10-22T19:00:00")]))
    legacy_snapshot.write_text(
        "NE,TP,From,BERPreFEC\nLEGACY-DEVICE,PORT-1,2025-08-22T06:45:00,0.000001\n",
        encoding="utf-8",
    )

    adapter = NokiaTelemetryAdapter({
        "nokia_csv_files": [str(first), str(second)],
        "nokia_pmdata_path": str(legacy_snapshot),
        "nokia_destination_url": "https://nms.invalid/networkinventory",
    })
    adapter.refresh()

    assert adapter.data_origin == "project_csv"
    assert set(adapter.get_devices()) == {"NOKIA-001", "NOKIA-003"}
    assert adapter.get_uploaded_csv_status()["device_count"] == 2
    assert adapter.get_uploaded_csv_status()["ingestion_status"] == "ready"


def test_missing_configured_project_csv_does_not_fall_back_to_legacy_snapshot(tmp_path):
    legacy_snapshot = tmp_path / "legacy-865-device-snapshot.csv"
    legacy_snapshot.write_text(
        "NE,TP,From,BERPreFEC\nLEGACY-DEVICE,PORT-1,2025-08-22T06:45:00,0.000001\n",
        encoding="utf-8",
    )
    adapter = NokiaTelemetryAdapter({
        "nokia_csv_files": [str(tmp_path / "missing.csv")],
        "nokia_pmdata_path": str(legacy_snapshot),
        "nokia_destination_url": "https://nms.invalid/networkinventory",
    })

    adapter.refresh()

    assert adapter.get_devices() == {}
    assert adapter.data_origin == "none"
    assert adapter.last_refresh_status == "error"
    assert "missing.csv" in adapter.last_refresh_error


def test_local_qaoa_uses_csv_metrics_without_claiming_qpu_or_device_execution(monkeypatch):
    adapter = NokiaTelemetryAdapter()
    adapter.ingest_uploaded_csv_files([
        ("first.csv", make_csv([
            make_row("NOKIA-001", "2026-10-22T10:00:00", 10),
            make_row("NOKIA-001", "2026-10-22T10:00:01", 12),
        ])),
        ("second.csv", make_csv([
            make_row("NOKIA-003", "2026-10-22T19:00:00", 75),
        ])),
    ])

    analysis = analyze_devices_with_local_qaoa(adapter.get_devices())

    assert analysis["method"] == "local_qaoa_statevector"
    assert analysis["status"] == "success"
    assert analysis["candidate_count"] == 1
    assert analysis["candidates"][0]["device_id"] == "NOKIA-001"
    assert analysis["candidates"][0]["variable"] == "x0"
    assert analysis["qpu_used"] is False
    assert analysis["execution_performed"] is False

    with monkeypatch.context() as context:
        context.setattr(telemetry_provider, "adapter", adapter)
        context.setattr(telemetry_provider, "nokia_adapter", adapter)
        context.setattr(telemetry_provider, "_source_mode", "nokia")
        api_result = analyze_current_telemetry_with_local_qaoa()

    assert api_result["source"] == "nokia"
    assert api_result["data_origin"] == "uploaded_csv"
    assert api_result["candidate_count"] == 1
    assert api_result["minimum_observation_seconds"] == 900.0


def test_csv_what_if_simulation_uses_csv_device_and_blocks_execution(monkeypatch):
    adapter = NokiaTelemetryAdapter()
    adapter.ingest_uploaded_csv_files([
        ("first.csv", make_csv([
            make_row("NOKIA-001", "2026-10-22T10:00:00", 10),
        ])),
        ("second.csv", make_csv([
            make_row("NOKIA-003", "2026-10-22T19:00:00", 75),
        ])),
    ])
    request = WhatIfSimulationRequest(
        device_id="NOKIA-001",
        action_type=ActionType.SLEEP_TRANSPONDER,
    )

    with monkeypatch.context() as context:
        context.setattr(telemetry_provider, "adapter", adapter)
        context.setattr(telemetry_provider, "nokia_adapter", adapter)
        context.setattr(telemetry_provider, "_source_mode", "nokia")
        twin_state = digital_twin_engine.synchronize()
        assert twin_state.total_devices == 2

        simulation = simulate_what_if_scenario(request)
        assert simulation.device_id == "NOKIA-001"
        assert simulation.discarded is True

        with pytest.raises(HTTPException) as exc_info:
            execute_digital_twin_action(request)
        assert exc_info.value.status_code == 403

    digital_twin_engine.synchronize()
