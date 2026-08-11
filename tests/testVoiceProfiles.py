import unittest

from backend.assistant import runtime
from backend.assistant import voice_profiles


class VoiceProfileContractTests(unittest.TestCase):
    def test_profile_is_local_only_and_covers_both_audio_roles(self):
        catalog = voice_profiles.list_profiles()
        self.assertEqual(catalog["contract_version"], voice_profiles.VOICE_PROFILE_CONTRACT_VERSION)
        self.assertTrue(catalog["local_only"])
        self.assertEqual(len(catalog["profiles"]), 1)
        profile = catalog["profiles"][0]
        self.assertTrue(profile["local_only"])
        self.assertEqual(
            set(profile["roles"]),
            {"speech_to_text", "text_to_speech"},
        )
        self.assertFalse(profile["policy"]["remote_endpoints_allowed"])
        self.assertTrue(profile["health_check"]["required_before_voice_turn"])

    def test_capability_contract_exposes_profile_without_starting_io(self):
        capabilities = runtime.capabilities()
        profiles = capabilities["voice_profiles"]
        self.assertTrue(profiles["local_only"])
        self.assertFalse(profiles["profiles"][0]["policy"]["models_started"])


if __name__ == "__main__":
    unittest.main()
