from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[4]


class PromQLContractTest(unittest.TestCase):
    def test_active_rules_use_emitted_metrics(self):
        values = (ROOT / "platform/observability/prometheus/prometheus-values.yaml").read_text()
        self.assertIn("gin_requests_total", values)
        self.assertIn("gin_request_duration_seconds_bucket", values)
        self.assertIn("HighErrorRate", values)
        self.assertIn("HighLatency", values)
        self.assertIn("DLQEventsDetected", values)

    def test_kargo_uses_emitted_metrics(self):
        kargo = (ROOT / "delivery/analysis/prometheus-checks.yaml").read_text()
        self.assertIn("gin_requests_total", kargo)
        self.assertIn("gin_request_duration_seconds_bucket", kargo)
        self.assertNotIn("http_requests_total", kargo)
