$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Rasputin native environment was not found at $python"
}

Set-Location $root
& $python -m backend.tools.native_host start
exit $LASTEXITCODE
