from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import runpy
import ssl


class DesktopSslPackagingTests(TestCase):
    def test_build_preserves_optional_interpreter_ssl_policy(self):
        spec = Path(__file__).resolve().parents[1] / "desktop" / "rasputin-backend.spec"
        for exists in (False, True):
            with self.subTest(policy_present=exists), TemporaryDirectory() as directory:
                root = Path(directory)
                policy = root / "codex-rejected-cas.pem"
                if exists:
                    policy.write_text("public CA policy fixture", encoding="utf-8")
                captured = {}

                def analysis(*args, **kwargs):
                    captured.update(kwargs)
                    return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])

                with patch.object(ssl, "__file__", str(root / "ssl.py")), patch("PyInstaller.utils.hooks.collect_submodules", return_value=[]):
                    runpy.run_path(str(spec), init_globals={
                        "SPECPATH": str(spec.parent), "Analysis": analysis,
                        "PYZ": lambda *args, **kwargs: None,
                        "EXE": lambda *args, **kwargs: None,
                        "COLLECT": lambda *args, **kwargs: None,
                    })
                expected = (str(policy), ".")
                self.assertEqual(expected in captured["datas"], exists)
