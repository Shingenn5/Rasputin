import unittest

from backend.core import performance


class PerformanceTelemetryTests(unittest.TestCase):
    def setUp(self):
        with performance._LOCK:
            performance._SAMPLES.clear()

    def test_snapshot_groups_routes_and_orders_by_average_latency(self):
        performance.record("/api/fast", "GET", 200, 10)
        performance.record("/api/slow", "POST", 200, 80)
        performance.record("/api/slow", "POST", 500, 120)
        data = performance.snapshot()

        self.assertEqual(data["sampleCount"], 3)
        self.assertEqual(data["slowest"][0]["path"], "/api/slow")
        self.assertEqual(data["slowest"][0]["avgMs"], 100.0)
        self.assertEqual(data["slowest"][0]["errors"], 1)
