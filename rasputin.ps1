param(
    [Parameter(Position=0)]
    [string]$Command = "help",
    
    [switch]$EnableWarSat
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Show-Header {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "           🛡️ RASPUTIN MANAGER          " -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Test-DockerEnv {
    try {
        [void](docker compose version 2>&1)
        if ($LASTEXITCODE -ne 0) { throw "Docker not found" }
    } catch {
        Write-Host "❌ Docker is not running or not installed." -ForegroundColor Red
        Write-Host "Rasputin requires Docker Desktop to run its sandboxes." -ForegroundColor Yellow
        Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
        Write-Host "Once installed and running, run this script again." -ForegroundColor Yellow
        exit 1
    }
}

function Open-Browser {
    param([string]$Url)
    Write-Host "Opening $Url in your default browser..." -ForegroundColor Cyan
    Start-Process $Url
}

function Get-Credentials {
    Write-Host "Fetching credentials from logs..." -ForegroundColor Cyan
    $logs = docker compose logs rasputin-wrapper 2>&1
    
    $username = $null
    $password = $null
    
    foreach ($line in $logs) {
        if ($line -match "username:\s*([^\s]+)") { $username = $matches[1] }
        if ($line -match "password:\s*([^\s]+)") { $password = $matches[1] }
    }
    
    if ($username -and $password) {
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Green
        Write-Host "         RASPUTIN CREDENTIALS            " -ForegroundColor Green
        Write-Host "=========================================" -ForegroundColor Green
        Write-Host " Username: " -NoNewline; Write-Host $username -ForegroundColor Yellow
        Write-Host " Password: " -NoNewline; Write-Host $password -ForegroundColor Yellow
        Write-Host "=========================================" -ForegroundColor Green
        Write-Host "Change this password after your first login!" -ForegroundColor Gray
        Write-Host ""
    } else {
        Write-Host "Still waiting for credentials to be generated... (Check 'docker compose logs' if this persists)" -ForegroundColor DarkGray
    }
}

function Start-Rasputin {
    Test-DockerEnv

    foreach ($dir in @("data", "workspace", "models")) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
    }

    $port = if ($env:WRAPPER_PORT) { $env:WRAPPER_PORT } else { "8787" }
    $url = "http://127.0.0.1:$port"

    Write-Host "Starting Rasputin on $url" -ForegroundColor Cyan
    
    if ($EnableWarSat) {
        Write-Host "Enabled WarSat Docker Control Layer..." -ForegroundColor Magenta
        docker compose -f docker-compose.yml -f docker-compose.docker-control.yml up --build -d
    } else {
        docker compose up --build -d
    }

    Write-Host "Waiting for Rasputin to become healthy..." -ForegroundColor Cyan
    
    # Simple wait loop checking the health API or just waiting for the container log
    $maxTries = 30
    $try = 0
    $healthy = $false
    while ($try -lt $maxTries) {
        Start-Sleep -Seconds 2
        try {
            $resp = Invoke-WebRequest -Uri "$url/api/system/health" -UseBasicParsing -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $healthy = $true
                break
            }
        } catch {
            Write-Host "." -NoNewline
        }
        $try++
    }
    Write-Host ""

    if ($healthy) {
        Write-Host "Rasputin is UP and RUNNING!" -ForegroundColor Green
        Get-Credentials
        Open-Browser -Url $url
    } else {
        Write-Host "Rasputin took too long to respond. It might still be starting up." -ForegroundColor Yellow
        Write-Host "Run '.\rasputin.ps1 credentials' in a few moments." -ForegroundColor Yellow
    }
}

function Stop-Rasputin {
    Test-DockerEnv
    Write-Host "Stopping Rasputin..." -ForegroundColor Cyan
    docker compose down
    Write-Host "Rasputin stopped." -ForegroundColor Green
}

Show-Header

switch ($Command.ToLower()) {
    "start" { Start-Rasputin }
    "stop" { Stop-Rasputin }
    "credentials" { Test-DockerEnv; Get-Credentials }
    default {
        Write-Host "Usage:" -ForegroundColor Cyan
        Write-Host "  .\rasputin.ps1 start             - Starts Rasputin in the background"
        Write-Host "  .\rasputin.ps1 start -EnableWarSat - Starts Rasputin with Docker Control layer"
        Write-Host "  .\rasputin.ps1 stop              - Stops all Rasputin containers"
        Write-Host "  .\rasputin.ps1 credentials       - Fetches your login credentials"
        Write-Host ""
    }
}
