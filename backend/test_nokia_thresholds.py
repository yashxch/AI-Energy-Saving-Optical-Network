from app.telemetry.normalizer import NokiaTelemetryNormalizer
from app.thresholds import NokiaThresholdEvaluator


def test_q_margin_uses_guide_boundaries_and_preserves_identity():
    device = NokiaTelemetryNormalizer().normalize_device(
        {
            "DEVICE-ID": "NE-A / CARD-7",
            "name": "Exact Nokia 1830 / Tx-01",
            "NE-NAME": "NE-A",
            "Q-Margin - Min": "0.9",
            "Q-Margin - Average": "2.5",
            "TIMESTAMP": "1700000000000",
        },
        "internal-id",
    )

    results = NokiaThresholdEvaluator().evaluate_device(device)

    minimum = next(result for result in results if result.metric == "Q-margin min")
    average = next(result for result in results if result.metric == "Q-margin average")
    assert device.name == "Exact Nokia 1830 / Tx-01"
    assert minimum.severity == "CRITICAL"
    assert average.severity == "WARNING"
    assert minimum.ne_name == "NE-A"


def test_counter_first_sample_is_unknown_and_reset_is_safe():
    normalizer = NokiaTelemetryNormalizer()
    evaluator = NokiaThresholdEvaluator()
    device = normalizer.normalize_device({"DEVICE-ID": "D1", "FEC UBC": 10}, "internal-id")

    first = next(result for result in evaluator.evaluate_device(device) if result.metric == "FEC UBC")
    assert first.severity == "UNKNOWN"
    assert first.complete is False

    device.raw_record["FEC UBC"] = 12
    second = next(result for result in evaluator.evaluate_device(device) if result.metric == "FEC UBC")
    assert second.measured_value == 2
    assert second.severity == "CRITICAL"

    device.raw_record["FEC UBC"] = 1
    reset = next(result for result in evaluator.evaluate_device(device) if result.metric == "FEC UBC")
    assert reset.measured_value == 1
    assert reset.severity == "CRITICAL"
