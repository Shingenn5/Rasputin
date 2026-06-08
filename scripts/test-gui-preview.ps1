param(
  [int]$Port = 8899,
  [switch]$SkipBuild,
  [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
$env:RASPUTIN_GUI_TEST_PORT = "$Port"
$env:RASPUTIN_TEST_BASE_URL = "http://127.0.0.1:$Port"
$env:RASPUTIN_GUI_PREVIEW = "1"
$composeArgs = @("compose", "-f", "docker-compose.gui-test.yml")

function Invoke-NativeChecked {
  param(
    [string]$Command,
    [string[]]$Arguments
  )
  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$Command failed with exit code $LASTEXITCODE"
  }
}

try {
  Invoke-NativeChecked "powershell" @("-ExecutionPolicy", "Bypass", "-File", "./scripts/check-repo-safety.ps1")
  Invoke-NativeChecked "npm" @("run", "build")

  if ($SkipBuild) {
    Invoke-NativeChecked "docker" ($composeArgs + @("up", "-d"))
  } else {
    Invoke-NativeChecked "docker" ($composeArgs + @("up", "-d", "--build"))
  }

  $ready = $false
  for ($i = 0; $i -lt 45; $i++) {
    try {
      $health = Invoke-RestMethod -Uri "$env:RASPUTIN_TEST_BASE_URL/api/health" -TimeoutSec 3
      if ($health.ok -eq $true) {
        $ready = $true
        break
      }
    } catch {
      Start-Sleep -Seconds 1
    }
  }

  if (-not $ready) {
    docker @composeArgs logs --tail 120 rasputin-gui-test
    throw "RasputinTest GUI preview did not become healthy at $env:RASPUTIN_TEST_BASE_URL"
  }

  Invoke-NativeChecked "npx" @("playwright", "test", "tests/ui/guiPreview.spec.mjs")
  Write-Host "RasputinTest GUI preview tests passed at $env:RASPUTIN_TEST_BASE_URL"
} finally {
  if (-not $KeepRunning) {
    docker @composeArgs down
  }
}
