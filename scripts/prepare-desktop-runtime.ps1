
param(
    [switch]$ForceRefresh
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$root = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $root 'runtime\llama\manifest.json'
$bundleRoot = Join-Path $root 'runtime\llama\bundled'
$stagingRoot = Join-Path $root 'build\llama-runtime'

if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Pinned llama.cpp manifest was not found: $manifestPath"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$runtimes = @($manifest.runtimes)
if ($runtimes.Count -eq 0) {
    throw "The llama.cpp manifest contains no runtimes."
}

New-Item -ItemType Directory -Force -Path $bundleRoot, $stagingRoot | Out-Null

function Get-ResolvedPath([string]$path) {
    return [System.IO.Path]::GetFullPath($path)
}

function Assert-ChildPath([string]$child, [string]$parent) {
    $resolvedChild = Get-ResolvedPath $child
    $resolvedParent = (Get-ResolvedPath $parent).TrimEnd('\') + '\'
    if (-not $resolvedChild.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to write outside the runtime bundle: $resolvedChild"
    }
    return $resolvedChild
}

function Download-VerifiedAsset($asset, [string]$destination) {
    $expected = [string]$asset.sha256
    if ($expected -notmatch '^[0-9a-fA-F]{64}$') {
        throw "Invalid SHA-256 in manifest for $($asset.name)."
    }

    if (Test-Path -LiteralPath $destination) {
        $existing = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existing -eq $expected.ToLowerInvariant()) {
            return
        }
        Remove-Item -LiteralPath $destination -Force
    }

    $temporary = "$destination.$([guid]::NewGuid().ToString('N')).download"
    try {
        Write-Host "Downloading pinned llama.cpp asset $($asset.name)..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri ([string]$asset.url) -OutFile $temporary -UseBasicParsing
        $actual = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected.ToLowerInvariant()) {
            throw "SHA-256 mismatch for $($asset.name): expected $expected, got $actual."
        }
        Move-Item -LiteralPath $temporary -Destination $destination -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Flatten-RuntimeFiles([string]$sourceRoot, [string]$destinationRoot) {
    $files = @(Get-ChildItem -LiteralPath $sourceRoot -Recurse -File |
        Where-Object { $_.FullName -notmatch '[\\/]\.downloads[\\/]' })
    if ($files.Count -eq 0) {
        throw "The llama.cpp archive contained no runtime files."
    }

    foreach ($file in $files) {
        $destination = Join-Path $destinationRoot $file.Name
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }

    $executable = Join-Path $destinationRoot ([string]$script:runtimeExecutable)
    if (-not (Test-Path -LiteralPath $executable)) {
        throw "The llama.cpp archive did not contain $script:runtimeExecutable."
    }
}

foreach ($runtime in $runtimes) {
    $manifestId = [string]$runtime.manifest_id
    $bundledPath = [string]$runtime.bundled_path
    $script:runtimeExecutable = [string]$runtime.executable
    if ([string]::IsNullOrWhiteSpace($script:runtimeExecutable)) {
        $script:runtimeExecutable = 'llama-server.exe'
    }
    if ([string]::IsNullOrWhiteSpace($manifestId) -or [string]::IsNullOrWhiteSpace($bundledPath)) {
        throw "Every packaged llama.cpp runtime needs manifest_id and bundled_path."
    }
    if ([System.IO.Path]::IsPathRooted($bundledPath) -or $bundledPath -match '(^|[\\/])\.\.([\\/]|$)') {
        throw "Unsafe bundled_path in manifest: $bundledPath"
    }

    $destination = Assert-ChildPath (Join-Path (Join-Path $root 'runtime\llama') $bundledPath) $bundleRoot
    $executablePath = Join-Path $destination $script:runtimeExecutable
    if ((-not $ForceRefresh) -and (Test-Path -LiteralPath $executablePath)) {
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $executablePath --version *> $null
        $versionExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorAction
        if ($versionExitCode -eq 0) {
            Write-Host "Verified existing bundled runtime $manifestId." -ForegroundColor Green
            continue
        }
        Remove-Item -LiteralPath $destination -Recurse -Force
    }

    if (Test-Path -LiteralPath $destination) {
        Remove-Item -LiteralPath $destination -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $destination | Out-Null

    $stage = Join-Path $stagingRoot $manifestId
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
    $downloads = Join-Path $stage '.downloads'
    $extract = Join-Path $stage '.extract'
    New-Item -ItemType Directory -Force -Path $downloads, $extract | Out-Null

    foreach ($asset in @($runtime.assets)) {
        $assetPath = Join-Path $downloads ([System.IO.Path]::GetFileName([string]$asset.name))
        Download-VerifiedAsset $asset $assetPath
        $isArchive = [bool]$asset.archive -or ([string]$asset.name).ToLowerInvariant().EndsWith('.zip')
        if ($isArchive) {
            $assetExtract = Join-Path $extract ([System.IO.Path]::GetFileNameWithoutExtension([string]$asset.name))
            New-Item -ItemType Directory -Force -Path $assetExtract | Out-Null
            Expand-Archive -LiteralPath $assetPath -DestinationPath $assetExtract -Force
        }
        else {
            Copy-Item -LiteralPath $assetPath -Destination (Join-Path $extract ([System.IO.Path]::GetFileName([string]$asset.name))) -Force
        }
    }

    Flatten-RuntimeFiles $extract $destination
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $executablePath --version *> $null
    $versionExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction
    if ($versionExitCode -ne 0) {
        throw "Bundled llama.cpp runtime $manifestId failed its --version smoke check (exit code $versionExitCode)."
    }
    Write-Host "Bundled and verified $manifestId." -ForegroundColor Green
}

Get-ChildItem -LiteralPath $stagingRoot -Force -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "All pinned llama.cpp runtimes are bundled under $bundleRoot." -ForegroundColor Green
