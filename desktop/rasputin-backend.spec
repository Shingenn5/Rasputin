from pathlib import Path
import ssl

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPECPATH).resolve().parent
# Some build interpreters load an adjacent CA policy when creating any SSL
# context. Preserve that policy in the frozen stdlib directory as well.
ssl_policy = Path(ssl.__file__).with_name("codex-rejected-cas.pem")
ssl_policy_data = [(str(ssl_policy), ".")] if ssl_policy.is_file() else []

analysis = Analysis(
    [str(ROOT / "server.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "frontend"), "frontend"), *ssl_policy_data],
    hiddenimports=collect_submodules("backend"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "playwright", "tkinter"],
    noarchive=False,
    optimize=1,
)

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="rasputin-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="rasputin-backend",
)
