[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PackagePath,
    [Parameter(Mandatory = $true)][string]$ConfigPath
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$root = Split-Path -Parent $PSScriptRoot
$version = & node -p "require('./scripts/store-config.cjs').storeVersion"
if ($LASTEXITCODE -ne 0) { throw 'Could not read Store version' }
$package = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $PackagePath).Path)
try {
    $manifestEntry = $package.GetEntry('AppxManifest.xml')
    if (-not $manifestEntry) { throw 'Package has no AppxManifest.xml' }
    $reader = New-Object System.IO.StreamReader($manifestEntry.Open())
    try { [xml]$manifest = $reader.ReadToEnd() } finally { $reader.Dispose() }
    $identity = $manifest.Package.Identity
    if ($identity.Name -cne $config.appx.identityName -or $identity.Publisher -cne $config.appx.publisher) {
        throw 'Packaged identity does not match the requested Store identity'
    }
    if ($identity.Version -ne $version -or $identity.ProcessorArchitecture -ne 'x64') {
        throw 'Incorrect Store version or architecture'
    }
    $application = $manifest.Package.Applications.Application
    if ($application.Id -ne 'Rasputin' -or $application.Executable -ne 'app\Rasputin.exe' -or $application.EntryPoint -ne 'Windows.FullTrustApplication') {
        throw 'Incorrect full-trust desktop entry point'
    }
    if (-not ($manifest.Package.Capabilities.ChildNodes | Where-Object { $_.Name -eq 'runFullTrust' })) {
        throw 'Missing runFullTrust capability'
    }
    foreach ($file in @(
        'app/Rasputin.exe', 'app/resources/app.asar',
        'app/resources/backend/rasputin-backend.exe',
        'app/resources/backend/_internal/frontend/index.html',
        'app/resources/backend/_internal/docx/templates/default.docx',
        'app/resources/llama/manifest.json',
        'assets/StoreLogo.png', 'assets/Square150x150Logo.png',
        'assets/Square44x44Logo.png', 'assets/Wide310x150Logo.png'
    )) {
        $entry = $package.GetEntry($file)
        if (-not $entry -or $entry.Length -eq 0) { throw "Missing package content: $file" }
    }
    if ($package.Entries | Where-Object { $_.FullName -like '*/docx/templates/default-docx-template/*' }) {
        throw 'Unused expanded Word template must not enter the Store package'
    }
    $templateStream = $package.GetEntry('app/resources/backend/_internal/docx/templates/default.docx').Open()
    $template = New-Object System.IO.Compression.ZipArchive($templateStream, [System.IO.Compression.ZipArchiveMode]::Read)
    try {
        if (-not $template.GetEntry('word/document.xml')) { throw 'Invalid packaged Word template' }
    } finally {
        $template.Dispose()
        $templateStream.Dispose()
    }
} finally {
    $package.Dispose()
}
$hash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $(Split-Path -Leaf $PackagePath)" | Set-Content -LiteralPath "$PackagePath.sha256" -Encoding ascii
@{
    sourceCommit = $env:GITHUB_SHA
    workflowRun = $env:GITHUB_RUN_ID
    applicationVersion = (Get-Content -LiteralPath (Join-Path $root 'package.json') -Raw | ConvertFrom-Json).version
    packageVersion = $version
    identityName = $config.appx.identityName
    publisher = $config.appx.publisher
    mode = $env:STORE_PACKAGE_MODE
    sha256 = $hash
    signed = $false
} | ConvertTo-Json | Set-Content -LiteralPath "$PackagePath.json" -Encoding utf8
Write-Host "PASS actual AppX identity, version, desktop entry point, backend, frontend, runtime manifest, assets and SHA-256"
