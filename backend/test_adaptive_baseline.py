from app.adaptive_baseline import AdaptiveBaselineManager


def active_manager(**kwargs):
    return AdaptiveBaselineManager(min_samples=kwargs.pop("min_samples", 3), **kwargs)


def test_warmup_and_activation():
    manager = active_manager()
    for _ in range(3):
        result = manager.update_device("d1", {"traffic_utilization_pct": 10})["traffic_utilization_pct"]
    assert result["learning_status"] == "LEARNING_ACTIVE"


def test_running_statistics_and_thresholds():
    manager = active_manager(k=3.0)
    for value in (20, 22, 24):
        manager.update_device("d1", {"osnr_db": value})
    result = manager.classify("d1", "osnr_db", 27)
    assert result["learned_mean"] == 22
    assert round(result["learned_std"], 6) == 2
    assert result["upper_threshold"] == 28
    assert result["classification"] == "WARNING"


def test_normal_warning_and_anomaly():
    manager = active_manager()
    for value in (10, 12, 14):
        manager.update_device("d1", {"traffic_utilization_pct": value})
    assert manager.classify("d1", "traffic_utilization_pct", 15)["classification"] == "NORMAL"
    assert manager.classify("d1", "traffic_utilization_pct", 17)["classification"] == "WARNING"
    assert manager.classify("d1", "traffic_utilization_pct", 20)["classification"] == "ANOMALY"


def test_device_specific_and_anomalies_do_not_contaminate_baseline():
    manager = active_manager()
    for value in (10, 10, 10):
        manager.update_device("d1", {"power_consumption_w": value})
        manager.update_device("d2", {"power_consumption_w": value + 100})
    manager.update_device("d1", {"power_consumption_w": 1000})
    assert manager.classify("d1", "power_consumption_w", 10)["learned_mean"] == 10
    assert manager.classify("d2", "power_consumption_w", 110)["learned_mean"] == 110


def test_gradual_adaptation_and_constant_values():
    manager = active_manager()
    for value in (10, 11, 12, 12, 13, 14):
        manager.update_device("d1", {"module_temp_c": value})
    result = manager.classify("d1", "module_temp_c", 12)
    assert 11.0 < result["learned_mean"] < 12.0
    assert result["learned_std"] > 0
    constant = active_manager()
    for _ in range(3):
        constant.update_device("d1", {"voltage_v": 12})
    assert constant.classify("d1", "voltage_v", 12)["classification"] == "NORMAL"


def test_hard_safety_wins_and_missing_values_are_safe():
    manager = active_manager()
    for value in (20, 20, 20):
        manager.update_device("d1", {"osnr_db": value})
    result = manager.classify("d1", "osnr_db", 10)
    assert result["classification"] == "ANOMALY"
    assert result["hard_safety_violation"] is True
    missing = manager.update_device("d1", {})["osnr_db"]
    assert missing["current_value"] is None
    assert missing["samples"] == 3


def test_restart_persistence(tmp_path):
    path = tmp_path / "baselines.json"
    first = active_manager(persistence_path=str(path))
    for value in (1, 2, 3):
        first.update_device("d1", {"current_a": value})
    second = active_manager(persistence_path=str(path))
    result = second.classify("d1", "current_a", 3)
    assert result["samples"] == 3
    assert result["learned_mean"] == 2