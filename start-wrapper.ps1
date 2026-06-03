param(
  [switch]$Detached
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

foreach ($dir in @("data", "workspace", "models")) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

$port = if ($env:WRAPPER_PORT) { $env:WRAPPER_PORT } else { "8787" }

docker compose version | Out-Null

Write-Host "Starting Rasputin on http://127.0.0.1:$port"
Write-Host "First-run admin password appears in the container logs."
if ($Detached) {
  docker compose up --build -d
} else {
  docker compose up --build
}
