import unittest

from backend.warsat.capabilities import build_capability_profile


class HardwareCapabilityProfileTests(unittest.TestCase):
    def test_profile_keeps_static_identity_and_volatile_capacity_separate(self):
        profile = build_capability_profile(
            {
                "os": "Linux",
                "platform": "Linux-test",
                "runtime": "native",
                "gpus": [
                    {
                        "index": 0,
                        "name": "NVIDIA GeForce RTX 5060 Ti",
                        "memoryTotalMb": 16384,
                        "memoryUsedMb": 2048,
                    },
                    {
                        "index": 1,
                        "name": "AMD Radeon Test",
                        "memoryTotalMb": 8192,
                        "memoryFreeMb": 4096,
                    },
                ],
                "gpuProbeSource": "nvidia-smi",
                "dockerRuntimes": ["runc", "nvidia"],
            },
            host_memory={"totalMb": 32768, "availableMb": 24576, "usedMb": 8192},
            generated_at=123.0,
        )

        self.assertEqual(profile["schemaVersion"], 1)
        self.assertEqual(profile["generatedAt"], 123.0)
        self.assertEqual(profile["summary"]["hardwareClass"], "mixed-vendor")
        self.assertEqual(profile["summary"]["installedVramMb"], 24576)
        self.assertEqual(profile["summary"]["knownFreeVramMb"], 18432.0)
        first = profile["devices"][0]
        self.assertEqual(first["deviceId"], "gpu:0")
        self.assertEqual(first["static"]["vendor"], "nvidia")
        self.assertEqual(first["static"]["memoryTotalMb"], 16384)
        self.assertEqual(first["volatile"]["memoryFreeMb"], 14336.0)
        self.assertEqual(profile["backends"]["cuda"]["status"], "observed")
        self.assertEqual(profile["backends"]["rocm"]["status"], "observed")
        self.assertTrue(profile["summary"]["combinedVramRequiresExplicitRuntime"])

    def test_cpu_only_profile_is_explicit_and_unknown_accelerators_stay_unknown(self):
        profile = build_capability_profile(
            {"os": "Linux", "platform": "Linux-cpu", "gpus": []},
            host_memory={"totalMb": 16384, "availableMb": 12000, "usedMb": 4384},
            generated_at=456.0,
        )

        self.assertEqual(profile["summary"]["hardwareClass"], "cpu-only")
        self.assertEqual(profile["summary"]["gpuCount"], 0)
        self.assertEqual(profile["backends"]["cpu"]["status"], "available")
        self.assertEqual(profile["backends"]["cuda"]["status"], "unknown")
        self.assertEqual(profile["backends"]["metal"]["status"], "unknown")
        self.assertEqual(profile["cpu"]["memoryAvailableMb"], 12000)
        self.assertEqual(profile["summary"]["knownFreeVramMb"], None)


if __name__ == "__main__":
    unittest.main()
