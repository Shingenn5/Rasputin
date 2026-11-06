param(
    [string]$Cargo = 'cargo',
    [string]$Executable,
    [string]$Backend,
    [switch]$BuildOnly
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$manifest = Join-Path $PSScriptRoot 'Cargo.toml'
if (!$Executable) {
    & $Cargo build --release --locked --manifest-path $manifest
    if ($LASTEXITCODE -ne 0) { throw 'Rust prototype build failed' }
    if ($BuildOnly) { return }
    $target = if ($env:CARGO_TARGET_DIR) { $env:CARGO_TARGET_DIR } else { Join-Path $PSScriptRoot 'target' }
    $Executable = Join-Path $target 'release/rasputin-rust-prototype.exe'
}
$resolvedExecutable = (Resolve-Path $Executable).Path
if ($Backend) { & $resolvedExecutable --backend (Resolve-Path $Backend).Path }
else { & $resolvedExecutable --source-root $projectRoot }
if ($LASTEXITCODE -ne 0) { throw 'Rust prototype failed; run the debug build for console diagnostics' }
