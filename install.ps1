param(
    [string]$Destination = (Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'),
    [switch]$Run
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repository = 'Shingenn5/Rasputin'
$minimumVersion = [version]'0.2.1'

Write-Host 'Finding latest Rasputin Windows release...' -ForegroundColor Cyan
$headers = @{ Accept = 'application/vnd.github+json'; 'User-Agent' = 'Rasputin-Installer' }
$releases = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$repository/releases?per_page=20"
$release = @($releases | Where-Object { -not $_.draft } | Select-Object -First 1)

if (-not $release) {
    throw "No Rasputin release is available. See https://github.com/$repository/releases"
}

$versionText = ([string]$release.tag_name) -replace '^v', '' -replace '-.*$', ''
$releaseVersion = $null
if (-not [version]::TryParse($versionText, [ref]$releaseVersion) -or $releaseVersion -lt $minimumVersion) {
    throw "Latest published installer is obsolete. Wait for v$minimumVersion or newer: https://github.com/$repository/releases"
}

$installer = @($release.assets | Where-Object { $_.name -match '^Rasputin-Setup-.*\.exe$' } | Select-Object -First 1)
$checksum = @($release.assets | Where-Object { $_.name -eq "$($installer.name).sha256" } | Select-Object -First 1)
if (-not $installer -or -not $checksum) {
    throw "Release $($release.tag_name) is missing its installer or SHA-256 file."
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$installerPath = Join-Path $Destination $installer.name
$checksumPath = "$installerPath.sha256"
Invoke-WebRequest -Headers $headers -Uri $installer.browser_download_url -OutFile $installerPath
Invoke-WebRequest -Headers $headers -Uri $checksum.browser_download_url -OutFile $checksumPath

$expected = ((Get-Content -LiteralPath $checksumPath -Raw).Trim() -split '\s+')[0]
$actual = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash
if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or $actual -ne $expected) {
    Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
    throw 'Installer SHA-256 verification failed. Downloaded installer was removed.'
}

Write-Host "Verified installer: $installerPath" -ForegroundColor Green
if ($Run) {
    Start-Process -FilePath $installerPath
} else {
    Write-Host 'Run it when ready, or rerun this script with -Run.'
}
