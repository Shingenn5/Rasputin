param(
  [int]$Port = 8899
)

$ErrorActionPreference = "Stop"
$env:RASPUTIN_GUI_TEST_PORT = "$Port"
docker compose -f docker-compose.gui-test.yml down
