param(
  [int]$Port = 8877,
  [switch]$SkipBuild,
  [switch]$Ui,
  [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
$env:RASPUTIN_TEST_PORT = "$Port"
$baseUrl = "http://127.0.0.1:$Port"
$composeArgs = @("compose", "-f", "docker-compose.test.yml")

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
  if ($Ui) {
    Invoke-NativeChecked "npm" @("run", "build")
  }

  if ($SkipBuild) {
    Invoke-NativeChecked "docker" ($composeArgs + @("up", "-d"))
  } else {
    Invoke-NativeChecked "docker" ($composeArgs + @("up", "-d", "--build"))
  }

  $ready = $false
  for ($i = 0; $i -lt 45; $i++) {
    try {
      $health = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 3
      if ($health.ok -eq $true) {
        $ready = $true
        break
      }
    } catch {
      Start-Sleep -Seconds 1
    }
  }

  if (-not $ready) {
    docker @composeArgs logs --tail 120 rasputin-wrapper-test
    throw "Rasputin test container did not become healthy at $baseUrl"
  }

  Invoke-NativeChecked "docker" ($composeArgs + @("exec", "-T", "rasputin-wrapper-test", "python", "-m", "unittest", "tests.testBackendSmoke"))
  Invoke-NativeChecked "docker" ($composeArgs + @("exec", "-T", "rasputin-wrapper-test", "python", "/app/tests/liveSmoke.py"))

  if ($Ui) {
    $env:RASPUTIN_TEST_BASE_URL = $baseUrl
    Invoke-NativeChecked "npm" @("run", "testUi")
  }

  Write-Host "Rasputin test harness passed at $baseUrl"
} finally {
  if (-not $KeepRunning) {
    docker @composeArgs down
  }
}
