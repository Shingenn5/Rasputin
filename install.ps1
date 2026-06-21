$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "      Rasputin Installer (Windows)       " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$targetDir = Join-Path -Path $PWD -ChildPath "Rasputin"

if (Test-Path $targetDir) {
    Write-Host "Directory '$targetDir' already exists!" -ForegroundColor Yellow
    $choice = Read-Host "Do you want to overwrite it? (y/N)"
    if ($choice -notmatch "^[yY]") {
        Write-Host "Installation aborted." -ForegroundColor Red
        exit
    }
    Remove-Item -Recurse -Force $targetDir
}

Write-Host "Downloading Rasputin..." -ForegroundColor Cyan
$zipUrl = "https://github.com/Shingenn5/Rasputin/archive/refs/heads/main.zip"
$zipPath = Join-Path -Path $PWD -ChildPath "rasputin-main.zip"

Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath

Write-Host "Extracting..." -ForegroundColor Cyan
Expand-Archive -Path $zipPath -DestinationPath $PWD -Force
Remove-Item -Force $zipPath

# GitHub zips put everything inside a "Rasputin-main" folder. Let's rename it.
Rename-Item -Path (Join-Path -Path $PWD -ChildPath "Rasputin-main") -NewName "Rasputin"

Write-Host ""
Write-Host "Installation complete! Rasputin is now in '$targetDir'" -ForegroundColor Green
Write-Host ""

Set-Location $targetDir
Write-Host "Starting Rasputin setup..." -ForegroundColor Cyan
& .\rasputin.ps1 start
