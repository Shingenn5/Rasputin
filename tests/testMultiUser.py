import os
import shutil
import tempfile
import unittest
from pathlib import Path


TEST_ROOT = Path(tempfile.mkdtemp(prefix="rasputin-multiuser-"))
os.environ["RASPUTIN_DATA_DIR"] = str(TEST_ROOT / "data")
os.environ.pop("RASPUTIN_LOCALHOST_BYPASS", None)

from backend.core import auth, preferences, workspace  # noqa: E402
from backend.engine.agent import AgentHub  # noqa: E402
from backend.rag import memory  # noqa: E402
from backend import warsat  # noqa: E402
import server  # noqa: E402


class MultiUserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        auth.bootstrap()
        data = auth.load()
        password = "Admin-passphrase-123"
        hashed = auth._hash_password(password)
        data["users"][0]["salt"] = hashed["salt"]
        data["users"][0]["password_hash"] = hashed["hash"]
        auth.store.set_kv("auth", data)
        cls.admin_username = data["users"][0]["username"]
        cls.admin_password = password

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def test_restart_safe_sessions_and_account_lifecycle(self):
        auth.create_user("alice", "Alice-passphrase-123", "member")
        token, info = auth.login("alice", "Alice-passphrase-123")
        self.assertEqual(info["role"], "member")
        self.assertNotIn(token, {"", None})

        auth._sessions.clear()  # simulate a process restart losing the cache
        self.assertEqual(auth.session_info(token)["username"], "alice")
        auth.update_user("alice", enabled=False)
        self.assertIsNone(auth.session_info(token))

    def test_personal_state_is_owner_scoped(self):
        preferences.save({"theme": "contrast"}, "alice")
        preferences.save({"theme": "rasputin-dark"}, "bob")
        self.assertEqual(preferences.load("alice")["theme"], "contrast")
        self.assertEqual(preferences.load("bob")["theme"], "rasputin-dark")

        alice_memory = memory.add_item("fact", "alice-only", owner_id="alice")
        memory.add_item("fact", "bob-only", owner_id="bob")
        self.assertIn("alice-only", memory.load_memory("alice")["facts"])
        self.assertNotIn("bob-only", memory.load_memory("alice")["facts"])
        self.assertIsNone(memory.get_item(alice_memory["id"], "bob"))

        hub = AgentHub()
        alice_session = hub.create_session(title="Alice", owner_id="alice")
        hub.create_session(title="Bob", owner_id="bob")
        self.assertEqual([item["id"] for item in hub.sessions(owner_id="alice")["sessions"]], [alice_session["session"]["id"]])

    def test_workspace_acl_roles(self):
        workspace.claim_legacy_membership(self.admin_username)
        workspace.set_member("project-root", "alice", "viewer")
        self.assertEqual(workspace.require_user_access("project-root", "alice"), "viewer")
        with self.assertRaises(PermissionError):
            workspace.require_user_access("project-root", "alice", "developer")
        self.assertEqual(workspace.require_user_access("project-root", self.admin_username, "owner"), "owner")

    def test_https_requires_leaf_files_and_enables_secure_cookie(self):
        cert = TEST_ROOT / "rasputin.pem"
        key = TEST_ROOT / "rasputin-key.pem"
        cert.write_text("test certificate", encoding="utf-8")
        key.write_text("test key", encoding="utf-8")
        os.environ["RASPUTIN_HTTPS"] = "1"
        os.environ["RASPUTIN_TLS_CERT_FILE"] = str(cert)
        os.environ["RASPUTIN_TLS_KEY_FILE"] = str(key)
        os.environ.pop("RASPUTIN_COOKIE_SECURE", None)
        self.assertEqual(server._tls_config(), {"ssl_certfile": str(cert), "ssl_keyfile": str(key)})
        self.assertTrue(auth.cookie_secure())

    def test_docker_version_without_daemon_is_reported_not_crashed(self):
        checks, detected = warsat._docker_info_checks("docker", {"Client": {"Version": "1.2.3"}, "Server": None})
        self.assertEqual(detected["dockerClientVersion"], "1.2.3")
        self.assertEqual(detected["dockerServerVersion"], "")
        self.assertEqual(next(item for item in checks if item["id"] == "dockerDaemon")["status"], "block")


if __name__ == "__main__":
    unittest.main()
