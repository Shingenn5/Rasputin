param(
  [switch]$Detached
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

foreach ($dir in @("data", "workspace", "models")) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$port = if ($env:WRAPPER_PORT) { $env:WRAPPER_PORT } else { "8787" }
$url = "http://127.0.0.1:$port"

docker compose version | Out-Null

Write-Host "Starting Rasputin with Docker control on $url"
Write-Host "Advanced mode: docker.sock is mounted into the wrapper container."

if ($Detached) {
  docker compose -f docker-compose.yml -f docker-compose.docker-control.yml up --build -d
} else {
  docker compose -f docker-compose.yml -f docker-compose.docker-control.yml up --build
}
