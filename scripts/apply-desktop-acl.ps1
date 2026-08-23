[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$AppDir
)

$ErrorActionPreference = "Stop"
$resolvedAppDir = (Resolve-Path -LiteralPath $AppDir).Path
$executable = Join-Path $resolvedAppDir "Rasputin.exe"
if (-not (Test-Path -LiteralPath $executable)) {
  throw "Expected packaged executable at $executable"
}

$icacls = Join-Path $env:SystemRoot "System32\icacls.exe"
if (-not (Test-Path -LiteralPath $icacls)) {
  throw "Windows icacls.exe was not found at $icacls"
}

& $icacls $resolvedAppDir /grant "*S-1-15-2-2:(OI)(CI)(RX)" /T
if ($LASTEXITCODE -ne 0) {
  throw "icacls failed with exit code $LASTEXITCODE while preparing $resolvedAppDir"
}

$aclText = & $icacls $resolvedAppDir
if (($aclText -join [Environment]::NewLine) -notmatch "ALL RESTRICTED APPLICATION PACKAGES") {
  throw "The Electron restricted-application read/execute ACE was not applied to $resolvedAppDir"
}

Write-Host "Applied Electron GPU sandbox read/execute ACL to $resolvedAppDir"
