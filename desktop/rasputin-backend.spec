from pathlib import Path
import json
import ssl

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32 import versioninfo


ROOT = Path(SPECPATH).resolve().parent
package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
version = package["version"]
version_numbers = tuple(int(part) for part in version.split("-")[0].split(".")[:3]) + (0,)
backend_version = versioninfo.VSVersionInfo(
    ffi=versioninfo.FixedFileInfo(filevers=version_numbers, prodvers=version_numbers, fileType=1),
    kids=[versioninfo.StringFileInfo([versioninfo.StringTable("040904B0", [
        versioninfo.StringStruct("CompanyName", package["author"]),
        versioninfo.StringStruct("FileDescription", "Rasputin Backend"),
        versioninfo.StringStruct("FileVersion", version),
        versioninfo.StringStruct("ProductName", "Rasputin"),
        versioninfo.StringStruct("ProductVersion", version),
        versioninfo.StringStruct("OriginalFilename", "rasputin-backend.exe"),
    ])]), versioninfo.VarFileInfo([versioninfo.VarStruct("Translation", [1033, 1200])])],
)
# Some build interpreters load an adjacent CA policy when creating any SSL
# context. Preserve that policy in the frozen stdlib directory as well.
ssl_policy = Path(ssl.__file__).with_name("codex-rejected-cas.pem")
ssl_policy_data = [(str(ssl_policy), ".")] if ssl_policy.is_file() else []

analysis = Analysis(
    [str(ROOT / "server.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "frontend"), "frontend"),
           (str(ROOT / "backend/core/training_worker.py"), "backend/core"), *ssl_policy_data],
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
    version=backend_version,
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
