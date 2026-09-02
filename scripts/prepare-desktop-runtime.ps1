$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root 'runtime\llama\manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Pinned llama.cpp manifest was not found: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$runtimes = @($manifest.runtimes)
if ($runtimes.Count -eq 0) {
    throw 'The llama.cpp manifest contains no runtimes.'
}

$ids = @{}
foreach ($runtime in $runtimes) {
    $manifestId = [string]$runtime.manifest_id
    if ([string]::IsNullOrWhiteSpace($manifestId) -or $ids.ContainsKey($manifestId)) {
        throw "Every runtime needs a unique manifest_id; invalid value: $manifestId"
    }
    $ids[$manifestId] = $true
    if ($runtime.PSObject.Properties.Name -contains 'bundled_path') {
        throw "Runtime $manifestId must be downloaded after hardware detection, not bundled."
    }
    if ([string]$runtime.executable -ne 'llama-server.exe') {
        throw "Runtime $manifestId must declare llama-server.exe."
    }
    $assets = @($runtime.assets)
    if ($assets.Count -eq 0) {
        throw "Runtime $manifestId has no assets."
    }
    foreach ($asset in $assets) {
        if ([string]$asset.url -notmatch '^https://github\.com/ggml-org/llama\.cpp/releases/download/') {
            throw "Runtime asset $($asset.name) has an unapproved source."
        }
        if ([string]$asset.sha256 -notmatch '^[0-9a-fA-F]{64}$') {
            throw "Runtime asset $($asset.name) has an invalid SHA-256."
        }
        if ([long]$asset.size_bytes -le 0) {
            throw "Runtime asset $($asset.name) has an invalid size."
        }
    }
}

Write-Host "Validated $($runtimes.Count) hardware-selectable llama.cpp runtimes. No runtime binaries will be bundled." -ForegroundColor Green
