"""Compare isolated Rust/Electron process trees; never inspect live app data.

Requires the repository .venv (psutil), Node/Playwright, built Rust executable,
and an Electron executable with no resources/app.asar beside it. See README.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import statistics
import subprocess
import tempfile
import time

import psutil


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def clean_test_data(case_root, kind):
    runtime_root = case_root
    if kind == 'rust':
        lines = (case_root / 'shell.log').read_text(errors='replace').splitlines()
        roots = [line.removeprefix('PROTOTYPE_ROOT=') for line in lines if line.startswith('PROTOTYPE_ROOT=')]
        if not roots:
            return  # Startup failed before a runtime directory was reported.
        runtime_root = Path(roots[-1]).resolve()
        if runtime_root.parent != Path(tempfile.gettempdir()).resolve() or not runtime_root.name.startswith('rasputin-rust-'):
            raise RuntimeError('Refusing cleanup outside the temporary Rust prototype directory')
    for name in ['data', 'webview']:
        target = runtime_root / name
        if target.resolve().parent != runtime_root.resolve() or target.is_symlink():
            raise RuntimeError('Refusing cleanup of a redirected test-data directory')
        if target.exists():
            shutil.rmtree(target)
    (runtime_root / 'desktop-runtime.json').unlink(missing_ok=True)


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def sample(process):
    rows = []
    for child in [process, *process.children(recursive=True)]:
        try:
            memory = child.memory_info()
            name = child.name().lower()
            kind = 'backend' if 'python' in name or 'rasputin-backend' in name else (
                'webview' if 'msedgewebview2' in name else 'shell')
            rows.append({'pid': child.pid, 'kind': kind, 'working_set': memory.rss,
                         'private_bytes': memory.private})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return rows


def run_case(kind, executable, backend, duration, work, extended_ui=False):
    case_root = work / f'{kind}-{time.time_ns()}'
    case_root.mkdir()
    port = free_port()
    env = os.environ.copy()
    # Prevent inherited live app paths and Electron run-as-Node mode.
    for key in ['RASPUTIN_DATA_DIR', 'ELECTRON_RUN_AS_NODE', 'RASPUTIN_DESKTOP_PORT']:
        env.pop(key, None)
    if kind == 'rust':
        command = [str(executable), '--backend' if backend else '--source-root', str(backend or ROOT)]
        env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = f'--remote-debugging-port={port}'
    else:
        command = [str(executable), f'--remote-debugging-port={port}', str(HERE / 'electron-baseline.cjs')]
        env['RASPUTIN_BASELINE_ROOT'] = str(case_root)
        if backend:
            env['RASPUTIN_BASELINE_BACKEND'] = str(backend)
    tracked = []
    probe = None
    launched = time.perf_counter()
    launched_epoch_ms = time.time() * 1000
    with (case_root / 'shell.log').open('wb') as log:
        child = subprocess.Popen(command, env=env, stdout=log, stderr=log, cwd=ROOT)
        process = psutil.Process(child.pid)
        probe_path = case_root / 'probe.json'
        probe_log = (case_root / 'probe.log').open('wb')
        try:
            probe = subprocess.Popen(['node', str(HERE / 'probe.mjs'), str(port), str(probe_path),
                                      'extended' if extended_ui else 'basic'],
                                     stdout=probe_log, stderr=probe_log, cwd=ROOT)
            startup_peak = 0
            deadline = time.monotonic() + 110
            while not probe_path.exists():
                if child.poll() is not None or probe.poll() is not None:
                    raise RuntimeError(f'{kind} exited before UI readiness; inspect {case_root}')
                if time.monotonic() > deadline:
                    raise TimeoutError(f'{kind} UI readiness timed out; inspect {case_root}')
                rows = sample(process)
                tracked.extend(row['pid'] for row in rows)
                startup_peak = max(startup_peak, sum(row['private_bytes'] for row in rows))
                time.sleep(.1)
            probe.wait(timeout=10)
            if probe.returncode:
                raise RuntimeError(f'{kind} UI probe failed; inspect {case_root}')
            ready_ms = (time.perf_counter() - launched) * 1000
            samples = []
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline:
                rows = sample(process)
                tracked.extend(row['pid'] for row in rows)
                samples.append(rows)
                time.sleep(.25)
            result = {
                'kind': kind, 'backend_mode': 'packaged' if backend else 'source',
                'ui_probe_complete_ms': ready_ms,
                'ui_ready_ms': json.loads(probe_path.read_text())['ready_epoch_ms'] - launched_epoch_ms,
                'startup_peak_private_mib': startup_peak / 2**20,
                'idle_private_mib_median': statistics.median(sum(r['private_bytes'] for r in s) for s in samples) / 2**20,
                'idle_working_set_mib_median': statistics.median(sum(r['working_set'] for r in s) for s in samples) / 2**20,
                'final_processes': samples[-1],
                'probe': json.loads(probe_path.read_text()),
                'note': 'Working sets include shared pages; private bytes are committed memory, not physical RAM. No model loaded.',
            }
        finally:
            if probe and probe.poll() is None:
                probe.kill()
                probe.wait()
            probe_log.close()
            if child.poll() is None:
                # Force only this isolated owner; Rust's job must clean up its
                # own descendants. Electron fixture needs explicit tree cleanup.
                if kind == 'electron':
                    subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    child.kill()
                child.wait(timeout=15)
            time.sleep(1)
            survivors = [pid for pid in set(tracked) if psutil.pid_exists(pid)]
            if survivors:
                raise RuntimeError(f'{kind} left owned process IDs alive: {survivors}')
    clean_test_data(case_root, kind)
    result['owned_process_cleanup_verified'] = True
    result['termination'] = 'shell_kill_job_cleanup' if kind == 'rust' else 'explicit_fixture_tree_kill'
    (case_root / 'result.json').write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rust', required=True, type=Path)
    parser.add_argument('--electron', type=Path)
    parser.add_argument('--backend', type=Path)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--extended-ui', action='store_true', help='Also exercise settings/chat and blocked external navigation')
    args = parser.parse_args()
    if args.seconds <= 0 or args.repeats < 1:
        parser.error('seconds and repeats must be positive')
    for path in [args.rust, args.electron, args.backend]:
        if path is not None and not path.is_file():
            parser.error(f'Executable not found: {path}')
    if args.electron and (args.electron.parent / 'resources/app.asar').exists():
        parser.error('Use an isolated Electron runtime without the production app.asar; see README')
    work = Path(tempfile.mkdtemp(prefix='rasputin-shell-benchmark-'))
    print(f'Evidence directory: {work}', flush=True)
    results = []
    for iteration in range(args.repeats):
        cases = [('rust', args.rust), ('electron', args.electron)]
        if iteration % 2:
            cases.reverse()
        for kind, executable in cases:
            if executable:
                result = run_case(kind, executable.resolve(), args.backend.resolve() if args.backend else None,
                                  args.seconds, work, args.extended_ui)
                results.append(result)
                print(json.dumps({k: v for k, v in result.items() if k not in ['final_processes', 'probe']}), flush=True)
    (work / 'results.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
