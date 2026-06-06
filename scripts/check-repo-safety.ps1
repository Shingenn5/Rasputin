param(
  [switch]$StagedOnly
)

$ErrorActionPreference = "Stop"

$blockedPathPatterns = @(
  "^data(/|$)",
  "^workspace/.*",
  "^models/.*",
  "^output(/|$)",
  "^testdata(/|$)",
  "^playwright-report(/|$)",
  "^test-results(/|$)",
  "^frontend(/|$)",
  "(^|/)auth\.json$",
  "(^|/)telegram\.json$",
  "(^|/)security\.json$",
  "(^|/)models\.json$",
  "(^|/)workspace\.json$",
  "(^|/)preferences\.json$",
  "(^|/)output\.json$",
  "(^|/)audit\.jsonl$",
  "(^|/)memory\.json$",
  "(^|/)memory\.json\.backup-.*$",
  "(^|/)rasputin\.db.*$",
  "(^|/)rag_index\.json$",
  "(^|/)graph\.json$",
  "\.(gguf|safetensors|pt|pth|onnx|ckpt)$"
)

$allowedTracked = @(
  "workspace/.gitkeep",
  "models/.gitkeep"
)

function Normalize-RepoPath {
  param([string]$Path)
  return ($Path -replace "\\", "/").Trim()
}

function Test-BlockedPath {
  param([string]$Path)
  $normalized = Normalize-RepoPath $Path
  if ($allowedTracked -contains $normalized) {
    return $false
  }
  foreach ($pattern in $blockedPathPatterns) {
    if ($normalized -match $pattern) {
      return $true
    }
  }
  return $false
}

function Get-GitLines {
  param([string[]]$Arguments)
  $lines = & git @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
  }
  return @($lines | Where-Object { $_ })
}

$tracked = if ($StagedOnly) { @() } else { Get-GitLines @("ls-files") }
$staged = Get-GitLines @("diff", "--cached", "--name-only")

$blockedTracked = @($tracked | Where-Object { Test-BlockedPath $_ })
$blockedStaged = @($staged | Where-Object { Test-BlockedPath $_ })

if ($blockedTracked.Count -or $blockedStaged.Count) {
  Write-Host "Rasputin repo safety check failed." -ForegroundColor Red
  if ($blockedTracked.Count) {
    Write-Host ""
    Write-Host "Tracked private/local files:" -ForegroundColor Yellow
    $blockedTracked | Sort-Object | ForEach-Object { Write-Host "  $_" }
  }
  if ($blockedStaged.Count) {
    Write-Host ""
    Write-Host "Staged private/local files:" -ForegroundColor Yellow
    $blockedStaged | Sort-Object | ForEach-Object { Write-Host "  $_" }
  }
  exit 1
}

Write-Host "Rasputin repo safety check passed."
