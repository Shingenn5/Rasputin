param(
  [int]$Port = 8899,
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$env:RASPUTIN_GUI_TEST_PORT = "$Port"
$composeArgs = @("compose", "-f", "docker-compose.gui-test.yml")

if ($SkipBuild) {
  docker @composeArgs up -d
} else {
  docker @composeArgs up --build -d
}

Write-Host "RasputinTest GUI preview is starting at http://127.0.0.1:$Port/preview/home"
