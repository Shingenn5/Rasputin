$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Create Rasputin's .venv before packaging the desktop application."
}

& $python -c 'import PyInstaller' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing desktop build dependencies...' -ForegroundColor Cyan
    & $python -m pip install -r (Join-Path $root 'requirements-desktop.txt')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$frontend = Join-Path $root 'frontend\index.html'
if (-not (Test-Path -LiteralPath $frontend)) {
    throw "Build the frontend before packaging: npm run build"
}

Set-Location $root
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath (Join-Path $root 'dist\desktop-backend') `
    --workpath (Join-Path $root 'build\pyinstaller') `
    (Join-Path $root 'desktop\rasputin-backend.spec')
exit $LASTEXITCODE
