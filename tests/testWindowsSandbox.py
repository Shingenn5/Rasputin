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
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import uuid

from backend.core.windows_sandbox import probe, recover_abandoned, _api


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

    def test_toolchain_and_host_lease_are_not_writable_or_replaceable(self):
        result = self.run_fixture("""
const fs = require('node:fs'), path = require('node:path');
const denied = fn => { try { fn(); return false; } catch(e) { return ['EACCES','EPERM'].includes(e.code); } };
const toolchain = path.dirname(process.execPath);
const lease = path.join(process.cwd(), '..', 'lease.json');
console.log(JSON.stringify({
 createTool: denied(() => fs.writeFileSync(path.join(toolchain, 'injected.cjs'), 'code')),
 replaceToolchain: denied(() => fs.renameSync(toolchain, path.join(process.cwd(), 'stolen'))),
 readLease: denied(() => fs.readFileSync(lease)),
 writeLease: denied(() => fs.writeFileSync(lease, '{}'))
}));
""")
        self.assert_success(result)
        self.assertEqual({"createTool": True, "replaceToolchain": True, "readLease": True,
                          "writeLease": True}, json.loads(result["output"]))

    def test_memory_and_process_ceilings_are_enforced(self):
        # A small allocation must work in the same runtime where exceeding the
        # job's memory allowance cannot complete successfully.
        small = self.run_fixture("Buffer.alloc(4 * 1024 * 1024, 1); console.log('allocated');",
                                 memory_limit_mb=128)
        self.assert_success(small)
        excessive = self.run_fixture("Buffer.alloc(256 * 1024 * 1024, 1); console.log('escaped');",
                                     memory_limit_mb=128)
        self.assertNotEqual(0, excessive["exit_code"], excessive)
        self.assertNotIn("escaped", excessive["output"])
        result = self.run_fixture("""
try {
 const child = require('node:child_process').spawn(process.execPath,
  ['-e', 'console.log("unexpected-child")'], {stdio: 'inherit', cwd: process.cwd()});
 child.on('error', () => console.log('process ceiling rejected child'));
 child.on('spawn', () => process.exitCode = 1);
} catch(e) {
 if (e.syscall !== 'spawn') throw e;
 console.log('process ceiling rejected child');
}
""", max_processes=1)
        self.assertNotIn("unexpected-child", result["output"])
        self.assertIn("process ceiling rejected child", result["output"])

    def test_junction_cannot_grant_access_to_unrelated_files(self):
        with tempfile.TemporaryDirectory(dir=self.scratch, prefix="junction-target-") as folder:
            sentinel = Path(folder) / "private.txt"
            sentinel.write_text("keep", encoding="utf-8")
            result = self.run_fixture("""
const fs = require('node:fs'), path = require('node:path');
const denied = fn => { try { fn(); return false; } catch(e) { return ['EACCES','EPERM'].includes(e.code); } };
try { fs.symlinkSync(process.argv[2], 'redirect', 'junction'); }
catch(e) {
 if (!['EACCES','EPERM'].includes(e.code)) throw e;
 console.log('junction creation denied');
 process.exit(0);
}
if (!denied(() => fs.readFileSync(path.join('redirect', 'private.txt'))) ||
    !denied(() => fs.writeFileSync(path.join('redirect', 'private.txt'), 'changed'))) {
 throw Error('junction escaped');
}
console.log('junction access denied');
""", arguments=[folder])
            self.assert_success(result)
            self.assertRegex(result["output"], "junction (creation|access) denied")
            self.assertEqual("keep", sentinel.read_text(encoding="utf-8"))

    def test_recovery_retains_invalid_metadata_and_does_not_follow_junctions(self):
        with tempfile.TemporaryDirectory(dir=self.scratch, prefix="recovery-policy-") as folder:
            parent = Path(folder)
            invalid = parent / ("rasputin-probe-" + uuid.uuid4().hex)
            invalid.mkdir()
            (invalid / "lease.json").write_text('{"owner_pid": 0}', encoding="utf-8")
            with tempfile.TemporaryDirectory(dir=self.scratch, prefix="unrelated-recovery-") as target:
                sentinel = Path(target) / "keep.txt"
                sentinel.write_text("keep", encoding="utf-8")
                junction = parent / ("rasputin-probe-" + uuid.uuid4().hex)
                subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"),
                                "/d", "/c", "mklink", "/J", str(junction), target],
                               check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                # No owner probing or profile deletion is allowed on these inputs.
                with patch("backend.core.windows_sandbox._process_identity", side_effect=AssertionError("invalid lease was trusted")):
                    retained = recover_abandoned(parent)
                self.assertEqual(["retained", "retained"], sorted(item["status"] for item in retained))
                self.assertTrue((invalid / "lease.json").exists())
                self.assertEqual("keep", sentinel.read_text(encoding="utf-8"))
                junction.rmdir()

    def assert_pid_stopped(self, pid):
        kernel, _, _ = _api()
        handle = kernel.OpenProcess(0x100000, False, pid)
        if handle:
            try:
                self.assertEqual(0, kernel.WaitForSingleObject(handle, 5000), "Fixture process survived owner death")
            finally:
                kernel.CloseHandle(handle)
        else:
            self.assertEqual(87, ctypes.get_last_error(), "Unable to prove the fixture terminated")

    def test_abrupt_backend_death_kills_job_and_recovers_only_owned_resources(self):
        # A separate host process owns the job handle. Kill it without executing
        # any Python finally blocks; Windows, rather than test cleanup, must kill
        # both sandbox processes. The restart path must then reclaim its lease.
        helper = '''
import sys
from backend.core.windows_sandbox import probe
source = """
const fs = require('node:fs');
const child = require('node:child_process').spawn(process.execPath,
 ['-e', 'setInterval(() => {}, 1000)'], {stdio: 'inherit', cwd: process.cwd()});
child.on('spawn', () => fs.writeFileSync('pids.json', JSON.stringify([process.pid, child.pid])));
setInterval(() => {}, 1000);
"""
probe(sys.argv[1], {'fixture.cjs': source},
 ['--preserve-symlinks', '--preserve-symlinks-main', 'fixture.cjs'], scratch_parent=sys.argv[2], timeout=60)
'''
        with tempfile.TemporaryDirectory(dir=self.scratch, prefix="owner-death-") as folder:
            unrelated = Path(folder) / "keep.txt"
            unrelated.write_text("keep", encoding="utf-8")
            process = subprocess.Popen([sys.executable, "-c", helper, self.node, folder],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic() + 15
                pids = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail("Fixture host failed: " + process.stderr.read().decode(errors="replace"))
                    for record in Path(folder).glob("rasputin-probe-*/workspace/pids.json"):
                        try:
                            pids = json.loads(record.read_text(encoding="utf-8"))
                        except (ValueError, OSError):
                            continue
                    if pids:
                        break
                    time.sleep(0.025)
                self.assertIsNotNone(pids, "Sandbox parent and child did not start")
                active = recover_abandoned(folder)
                self.assertEqual(["active"], [item["status"] for item in active], active)
                process.kill()
                process.wait(timeout=5)
                for pid in pids:
                    self.assert_pid_stopped(pid)
                recovered = recover_abandoned(folder)
                self.assertEqual(["recovered"], [item["status"] for item in recovered], recovered)
                self.assertEqual([], list(Path(folder).glob("rasputin-probe-*")))
                self.assertEqual("keep", unrelated.read_text(encoding="utf-8"))
                self.assertEqual([], recover_abandoned(folder))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                process.stderr.close()
                recover_abandoned(folder)

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
        self.assert_pid_stopped(pid)


if __name__ == "__main__":
    unittest.main()
