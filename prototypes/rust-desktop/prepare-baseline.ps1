param([string]$RuntimeDir = (Join-Path $PSScriptRoot '../../node_modules/electron/dist'))
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path $RuntimeDir).Path
if (!(Test-Path (Join-Path $source 'electron.exe'))) { throw 'Install the Electron developer runtime first: node node_modules/electron/install.js' }
if (Test-Path (Join-Path $source 'resources/app.asar')) { throw 'Use a developer runtime, not the packaged application' }
$destination = Join-Path ([System.IO.Path]::GetTempPath()) ('rasputin-electron-baseline-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $destination | Out-Null
# Copy only the developer runtime; no production app or packaged backend is read.
Get-ChildItem -LiteralPath $source | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse
}
# Chromium's restricted GPU process needs read/execute permission on its own
# runtime. Scope this to the new TEMP copy, never the checkout or installed app.
& (Join-Path $env:SystemRoot 'System32/icacls.exe') $destination /grant '*S-1-15-2-2:(OI)(CI)(RX)' /T /Q | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the temporary Electron GPU sandbox ACL' }
Write-Output (Join-Path $destination 'electron.exe')
