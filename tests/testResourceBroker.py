import unittest
from unittest.mock import patch

from backend.warsat import resource_broker


def _profile():
    return {
        "schemaVersion": 1,
        "devices": [
            {
                "deviceId": "gpu:0",
                "static": {"index": 0, "name": "RTX small", "vendor": "nvidia", "memoryTotalMb": 12288},
                "volatile": {"memoryFreeMb": 10000},
            },
            {
                "deviceId": "gpu:1",
                "static": {"index": 1, "name": "RTX large", "vendor": "nvidia", "memoryTotalMb": 16384},
                "volatile": {"memoryFreeMb": 15000},
            },
        ],
    }


class ResourceBrokerTests(unittest.TestCase):
    def test_selects_largest_fitting_single_gpu_and_keeps_aggregate_explicit(self):
        result = resource_broker.evaluate_admission(
            _profile(),
            {"packId": "main", "ownerId": "elliott", "runtime": "vllm", "requestedVramMb": 12000},
            leases=[],
            now=100.0,
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["placements"], [{"deviceId": "gpu:1", "vramMb": 12000}])
        self.assertIn("largest_fitting_single_gpu_first", result["reasons"])

    def test_active_lease_causes_queue_without_overcommit(self):
        lease = {
            "leaseId": "lease-main",
            "ownerId": "owner-a",
            "packId": "main",
            "runtime": "vllm",
            "placements": [{"deviceId": "gpu:1", "vramMb": 12000}],
            "createdAt": 10,
            "heartbeatAt": 10,
            "expiresAt": 200,
        }
        result = resource_broker.evaluate_admission(
            _profile(),
            {"packId": "helper", "ownerId": "owner-b", "runtime": "vllm", "requestedVramMb": 5000},
            leases=[lease],
            now=100.0,
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["placements"], [{"deviceId": "gpu:0", "vramMb": 5000}])

        queued = resource_broker.evaluate_admission(
            _profile(),
            {"packId": "oversized-helper", "ownerId": "owner-b", "runtime": "vllm", "requestedVramMb": 5000, "deviceId": "gpu:1"},
            leases=[lease],
            now=100.0,
        )
        self.assertEqual(queued["status"], "queued")
        self.assertIn("device_capacity_reserved_or_headroom_required", queued["reasons"])

    def test_combined_vram_requires_explicit_runtime_and_opt_in(self):
        request = {"packId": "large", "runtime": "vllm", "requestedVramMb": 22000, "deviceIds": ["gpu:0", "gpu:1"]}
        blocked = resource_broker.evaluate_admission(_profile(), request, leases=[], now=100.0)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("combined_vram_requires_explicit_opt_in", blocked["reasons"])
        self.assertTrue(blocked["nextActions"])

        wrong_runtime = resource_broker.evaluate_admission(
            _profile(), {**request, "allowCombined": True}, leases=[], now=100.0
        )
        self.assertEqual(wrong_runtime["status"], "blocked")
        self.assertIn("runtime_does_not_certify_combined_vram", wrong_runtime["reasons"])
        self.assertTrue(any("llama.cpp" in item for item in wrong_runtime["nextActions"]))

        allowed = resource_broker.evaluate_admission(
            _profile(), {**request, "runtime": "llama.cpp", "allowCombined": True}, leases=[], now=100.0
        )
        self.assertEqual(allowed["status"], "ready")
        self.assertEqual(sum(item["vramMb"] for item in allowed["placements"]), 22000)

    def test_cpu_fallback_and_unknown_envelope_are_visible(self):
        fallback = resource_broker.evaluate_admission(
            {"devices": []},
            {"packId": "speech", "runtime": "whisper", "requestedVramMb": 2000, "allowCpuFallback": True},
            leases=[],
            now=100.0,
        )
        self.assertEqual(fallback["status"], "degraded")
        self.assertEqual(fallback["placements"], [{"deviceId": "cpu", "vramMb": 0}])

        unknown = resource_broker.evaluate_admission({"devices": []}, {"packId": "unknown"}, leases=[], now=100.0)
        self.assertEqual(unknown["status"], "unmeasured")
        self.assertIn("resource_envelope_missing", unknown["reasons"])

    def test_reserve_heartbeat_and_release_are_owner_scoped_and_expiring(self):
        with patch.object(resource_broker.store, "get_kv", return_value=[]), patch.object(resource_broker.store, "set_kv") as saved:
            reserved = resource_broker.reserve(
                _profile(),
                {"packId": "main", "ownerId": "owner-a", "runtime": "vllm", "requestedVramMb": 8000},
                ttl_seconds=30,
                now=100.0,
            )
            self.assertEqual(reserved["decision"]["status"], "ready")
            lease = reserved["lease"]
            self.assertEqual(lease["ownerId"], "owner-a")
            self.assertEqual(lease["expiresAt"], 130.0)
            saved.assert_called()

        values = [lease]
        with patch.object(resource_broker.store, "get_kv", return_value=values), patch.object(resource_broker.store, "set_kv") as saved:
            self.assertIsNone(resource_broker.heartbeat(lease["leaseId"], "owner-b", now=110.0))
            refreshed = resource_broker.heartbeat(lease["leaseId"], "owner-a", ttl_seconds=60, now=110.0)
            self.assertEqual(refreshed["expiresAt"], 170.0)
            self.assertTrue(resource_broker.release(lease["leaseId"], "owner-a", now=115.0))
            self.assertGreaterEqual(saved.call_count, 2)


if __name__ == "__main__":
    unittest.main()
