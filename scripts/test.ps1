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
$runId = "{0}-{1}" -f $Port, ([Guid]::NewGuid().ToString("N").Substring(0, 8))
$runRoot = "./testdata/runs/$runId"
$env:RASPUTIN_TEST_DATA_DIR = "$runRoot/data"
$env:RASPUTIN_TEST_WORKSPACE_DIR = "$runRoot/workspace"
New-Item -ItemType Directory -Force -Path $env:RASPUTIN_TEST_DATA_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:RASPUTIN_TEST_WORKSPACE_DIR | Out-Null

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

  Invoke-NativeChecked "docker" ($composeArgs + @("exec", "-T", "rasputin-wrapper-test", "python", "-m", "unittest", "tests.testBackendSmoke", "tests.testMultiUser"))
  Invoke-NativeChecked "docker" ($composeArgs + @("exec", "-T", "rasputin-wrapper-test", "python", "/app/tests/liveSmoke.py"))
  Invoke-NativeChecked "docker" ($composeArgs + @("exec", "-T", "rasputin-wrapper-test", "python", "/app/tests/warsatSmoke.py"))

  if ($Ui) {
    $env:RASPUTIN_TEST_BASE_URL = $baseUrl
    Invoke-NativeChecked "npm" @("run", "testUi")
  }

  Write-Host "Rasputin test harness passed at $baseUrl"
  Write-Host "Test state was isolated under $runRoot"
} finally {
  if (-not $KeepRunning) {
    docker @composeArgs down
  }
}
