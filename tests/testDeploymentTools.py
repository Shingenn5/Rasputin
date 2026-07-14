import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.tools import native_host
from scripts import setup_remote_access


class NativeHostStateTests(unittest.TestCase):
    def test_stale_pid_state_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = native_host._paths(Path(temporary))
            native_host._atomic_json(paths["state"], {"pid": 999999999})
            with mock.patch.object(native_host, "_pid_alive", return_value=False):
                self.assertEqual(native_host._state(paths), {})
            self.assertFalse(paths["state"].exists())

    def test_live_desktop_runtime_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = native_host._paths(Path(temporary))
            native_host._atomic_json(paths["desktop"], {"pid": 1234, "url": "http://localhost:5000"})
            with mock.patch.object(native_host, "_pid_alive", return_value=True):
                state = native_host._desktop_runtime(paths)
            self.assertEqual(state["url"], "http://localhost:5000")

    def test_saved_configuration_is_used_and_cli_overrides_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = native_host._paths(Path(temporary))
            native_host._atomic_json(paths["config"], {
                "port": 8788,
                "lan": True,
                "allow_http": False,
                "allowed_hosts": ["rasputin.home"],
            })
            args = argparse.Namespace(port=9000, lan=None, allow_http=None, allowed_host=None)
            config = native_host._effective_config(args, paths)
            self.assertEqual(config["port"], 9000)
            self.assertTrue(config["lan"])
            self.assertEqual(config["allowed_hosts"], ["rasputin.home"])


class RemoteAccessTests(unittest.TestCase):
    def test_caddy_config_has_health_check_and_origin_preserving_proxy(self):
        config = setup_remote_access.caddy_config(
            "rasputin.example.com",
            "http://127.0.0.1:8788",
        )
        self.assertIn("rasputin.example.com {", config)
        self.assertIn("reverse_proxy http://127.0.0.1:8788", config)
        self.assertIn("health_uri /api/health", config)
        self.assertNotIn("header_up Host", config)

    def test_caddy_config_rejects_url_as_hostname(self):
        with self.assertRaises(ValueError):
            setup_remote_access.caddy_config("https://bad.example", "http://127.0.0.1:8788")

    def test_tailscale_identity_strips_trailing_dns_dot(self):
        completed = mock.Mock(returncode=0, stdout=json.dumps({
            "BackendState": "Running",
            "Self": {"DNSName": "rasputin.tailnet.ts.net."},
        }), stderr="")
        with mock.patch("subprocess.run", return_value=completed):
            identity = setup_remote_access._tailscale_identity("tailscale")
        self.assertEqual(identity["dns_name"], "rasputin.tailnet.ts.net")


if __name__ == "__main__":
    unittest.main()
