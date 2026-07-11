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

function Reset-Password {
    Write-Host "Resetting admin password inside the running container..." -ForegroundColor Cyan
    docker compose exec rasputin-wrapper python -m backend.tools.reset_password
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Password reset failed." -ForegroundColor Red
        Write-Host "Make sure the container is running and was built from a version that includes this tool:" -ForegroundColor Yellow
        Write-Host "  .\rasputin.ps1 start   (or: docker compose up --build -d)" -ForegroundColor Yellow
        Write-Host "Alternatively, stop the app and run it natively:" -ForegroundColor Yellow
        Write-Host "  python -m backend.tools.reset_password" -ForegroundColor Yellow
        return
    }
    Write-Host ""
    Write-Host "Note: the running server keeps its own in-memory sessions, so any" -ForegroundColor DarkGray
    Write-Host "already-logged-in browser sessions remain valid until the container restarts." -ForegroundColor DarkGray
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

    $composeFiles = @("-f", "docker-compose.yml")
    if ($EnableWarSat) {
        Write-Host "Enabled WarSat Docker Control Layer..." -ForegroundColor Magenta
        $composeFiles += @("-f", "docker-compose.docker-control.yml")
    }
    # Approving a local folder from the Workspaces tab writes this file with
    # the new bind mount; including it here means picking it up is just a
    # normal restart, no manual editing of any compose file.
    $mountsOverride = "data/docker-compose.mounts.yml"
    if (Test-Path $mountsOverride) {
        Write-Host "Including approved folder mounts from $mountsOverride" -ForegroundColor DarkCyan
        $composeFiles += @("-f", $mountsOverride)
    }
    docker compose @composeFiles up --build -d

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

function Migrate-Data {
    # One-time move of existing bind-mount data into the named volume that
    # docker-compose.yml now uses. Idempotent and copy-never-move: your .\data
    # directory is left fully intact so you can always roll back.
    Test-DockerEnv
    $volume = "rasputin_rasputin-data"
    Write-Host "Migrating Rasputin data into named volume '$volume'..." -ForegroundColor Cyan

    docker volume inspect $volume 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        docker run --rm -v "${volume}:/dest" python:3.12-slim test -f /dest/rasputin.db 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Already migrated: '$volume' already contains rasputin.db. Nothing to do." -ForegroundColor Green
            return
        }
    } else {
        docker volume create $volume | Out-Null
    }

    if (-not (Test-Path "data")) {
        Write-Host "No .\data directory to migrate - the empty volume is ready for a fresh start." -ForegroundColor Yellow
        return
    }

    # The old layout split runtime data: the LIVE store lived under .\data\wrapper
    # (mounted to /app/backend/data). Copy top-level files, then overlay wrapper\
    # so the live copies win any name collision.
    Write-Host "Copying existing data (source .\data is preserved)..." -ForegroundColor Cyan
    docker run --rm -v "${volume}:/dest" -v "${PWD}\data:/src:ro" python:3.12-slim sh -c 'set -e; cd /src; for f in *; do [ "$f" = wrapper ] || cp -a "$f" /dest/; done; if [ -d /src/wrapper ]; then cp -a /src/wrapper/. /dest/; fi; rm -rf /dest/wrapper; echo done'
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Migration copy failed - the volume may be incomplete. Investigate before starting." -ForegroundColor Red
        return
    }

    $size = docker run --rm -v "${volume}:/dest" python:3.12-slim stat -c "%s" /dest/rasputin.db 2>$null
    Write-Host ""
    Write-Host "Migration complete. rasputin.db in volume: $size bytes." -ForegroundColor Green
    Write-Host "Start with '.\rasputin.ps1 start', confirm login + chats, then you may archive .\data\wrapper." -ForegroundColor Gray
}

Show-Header

switch ($Command.ToLower()) {
    "start" { Start-Rasputin }
    "stop" { Stop-Rasputin }
    "credentials" { Test-DockerEnv; Get-Credentials }
    "reset-password" { Test-DockerEnv; Reset-Password }
    "migrate-data" { Migrate-Data }
    default {
        Write-Host "Usage:" -ForegroundColor Cyan
        Write-Host "  .\rasputin.ps1 start             - Starts Rasputin in the background"
        Write-Host "  .\rasputin.ps1 start -EnableWarSat - Starts Rasputin with Docker Control layer"
        Write-Host "  .\rasputin.ps1 stop              - Stops all Rasputin containers"
        Write-Host "  .\rasputin.ps1 credentials       - Fetches your login credentials"
        Write-Host "  .\rasputin.ps1 reset-password    - Resets the admin password and prints a new one"
        Write-Host "  .\rasputin.ps1 migrate-data      - Moves existing .\data into the named volume (idempotent)"
        Write-Host ""
    }
}
