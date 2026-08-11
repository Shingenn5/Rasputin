import unittest
from pathlib import Path


class AssistantUiContractTests(unittest.TestCase):
    def test_push_to_talk_is_explicit_bounded_and_local_adapter_wired(self):
        source = (Path(__file__).resolve().parents[1] / "frontend-src" / "src" / "features" / "assistant" / "AssistantView.jsx").read_text(encoding="utf-8")
        self.assertIn("navigator.mediaDevices?.getUserMedia", source)
        self.assertIn("getUserMedia({ audio: true })", source)
        self.assertIn("new MediaRecorder(stream)", source)
        self.assertIn("/api/assistant/voice/turn", source)
        self.assertIn("atob(data.audioBase64)", source)
        self.assertIn("MAX_RECORDING_MS = 60 * 1000", source)
        self.assertIn('data-testid="assistant-voice-console"', source)
        self.assertIn('data-testid="assistant-voice-toggle"', source)
        self.assertIn('data-testid="assistant-voice-audio"', source)
        self.assertIn('data-testid="assistant-voice-response"', source)
        self.assertIn('data-testid="assistant-voice-model-readiness"', source)
        self.assertIn("voiceProfiles.profiles", source)
        self.assertIn('data-testid="assistant-voice-profile"', source)
        self.assertIn('data-testid={`assistant-voice-role-${key}`}', source)
        self.assertIn("voiceModelReadiness.nextActions", source)
        self.assertIn("assistant-handoff-receipt-", source)
        self.assertIn("Governed Code task started", source)
        self.assertIn("aria-pressed={active}", source)


if __name__ == "__main__":
    unittest.main()
