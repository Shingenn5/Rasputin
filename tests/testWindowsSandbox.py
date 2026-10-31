"""Real opt-in AppContainer probes; never use the live Rasputin data store.

Set RASPUTIN_SANDBOX_PROBE_ROOT to an approved external scratch directory.
The default unit test run skips these Windows process-isolation experiments.
"""
import ctypes
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

from backend.core.windows_sandbox import probe, _api


@unittest.skipUnless(os.name == "nt" and os.environ.get("RASPUTIN_SANDBOX_PROBE_ROOT"),
                     "Opt-in Windows AppContainer integration probes")
class WindowsSandboxTests(unittest.TestCase):
    def setUp(self):
        self.scratch = os.environ["RASPUTIN_SANDBOX_PROBE_ROOT"]
        self.node = shutil.which("node")
        self.assertTrue(self.node, "The fixture requires an explicit installed Node toolchain")

    def run_fixture(self, source, *, arguments=(), **limits):
        return probe(self.node, {"fixture.cjs": source},
                     ["--preserve-symlinks", "--preserve-symlinks-main", "fixture.cjs", *arguments],
                     scratch_parent=self.scratch, **limits)

    def assert_success(self, result):
        self.assertEqual("exited", result["termination_reason"], result)
        self.assertEqual(0, result["exit_code"], result)
        self.assertFalse(result["production_ready"])

    def test_fixture_can_edit_and_test_its_own_files(self):
        result = self.run_fixture("""
const fs = require('node:fs');
fs.writeFileSync('sum.cjs', 'exports.sum = (a,b) => a-b;');
const filename = require('node:path').join(process.cwd(), 'sum.cjs');
let failed = require(filename).sum(2,3) !== 5;
if (!failed) throw Error('expected an initial failing test');
fs.writeFileSync('sum.cjs', 'exports.sum = (a,b) => a+b;');
delete require.cache[filename];
if (require(filename).sum(2,3) !== 5) throw Error('repair failed');
console.log('failed -> repaired -> passed');
""")
        self.assert_success(result)
        self.assertIn("failed -> repaired -> passed", result["output"])

    def test_unrelated_file_read_write_and_inherited_secrets_are_denied(self):
        with tempfile.TemporaryDirectory(dir=self.scratch, prefix="outside-probe-") as folder:
            sentinel = Path(folder) / "private.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            os.environ["RASPUTIN_PROBE_SECRET"] = "must-not-inherit"
            try:
                result = self.run_fixture("""
const fs = require('node:fs');
const denied = fn => { try { fn(); return false; } catch(e) { return ['EACCES','EPERM'].includes(e.code); } };
console.log(JSON.stringify({read: denied(() => fs.readFileSync(process.argv[2])),
 write: denied(() => fs.writeFileSync(process.argv[2], 'changed')),
 secretAbsent: !process.env.RASPUTIN_PROBE_SECRET}));
""", arguments=[str(sentinel)])
            finally:
                del os.environ["RASPUTIN_PROBE_SECRET"]
            self.assert_success(result)
            self.assertEqual({"read": True, "write": True, "secretAbsent": True}, json.loads(result["output"]))
            self.assertEqual("unchanged", sentinel.read_text(encoding="utf-8"))

    def test_network_and_loopback_are_denied(self):
        # Use a real listening endpoint so connection refusal cannot masquerade as isolation.
        import socket
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with socket.create_connection(listener.getsockname(), timeout=1):
                connection, _ = listener.accept()
                connection.close()
            result = self.run_fixture("""
const net = require('node:net');
async function denied(host, port) {
 return await new Promise((resolve, reject) => {
  const s = net.connect({host, port});
  s.on('connect', () => { s.destroy(); reject(Error('network escaped')); });
  s.on('error', e => resolve(e.code));
  s.setTimeout(1500, () => { s.destroy(); reject(Error('timeout does not prove denial')); });
 });
}
(async () => console.log(JSON.stringify({loopback: await denied('127.0.0.1', Number(process.argv[2])),
 external: await denied('1.1.1.1', 443)})))().catch(() => process.exit(1));
""", arguments=[str(listener.getsockname()[1])])
        self.assert_success(result)
        errors = json.loads(result["output"])
        self.assertIn(errors["loopback"], {"EACCES", "EPERM", "ECONNREFUSED", "ETIMEDOUT"}, errors)
        self.assertIn(errors["external"], {"EACCES", "EPERM"}, errors)

    def test_timeout_cancellation_and_output_limit(self):
        result = self.run_fixture("setInterval(() => {}, 1000);", timeout=0.3)
        self.assertEqual("timeout", result["termination_reason"])
        cancel = threading.Event()
        timer = threading.Timer(0.3, cancel.set)
        timer.start()
        try:
            result = self.run_fixture("setInterval(() => {}, 1000);", cancel=cancel)
        finally:
            timer.cancel()
            timer.join()
        self.assertEqual("cancelled", result["termination_reason"])
        result = self.run_fixture("setInterval(() => console.log('x'.repeat(8192)), 1);", max_output=1024)
        self.assertEqual("output_limit", result["termination_reason"])
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["output"].encode()), 1024)

    def test_background_descendant_is_killed_when_fixture_exits(self):
        result = self.run_fixture("""
const child = require('node:child_process').spawn(process.execPath,
 ['-e', 'setInterval(() => {}, 1000)'], {stdio: 'inherit', cwd: process.cwd()});
console.log(child.pid);
child.unref();
""")
        self.assert_success(result)
        pid = int(result["output"].strip())
        kernel, _, _ = _api()
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x100000, False, pid)
        if handle:
            try:
                self.assertEqual(0, kernel.WaitForSingleObject(handle, 5000), "Descendant survived job closure")
            finally:
                kernel.CloseHandle(handle)


if __name__ == "__main__":
    unittest.main()
