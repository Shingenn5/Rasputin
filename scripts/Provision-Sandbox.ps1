<#
.SYNOPSIS
  Provision (or repair / remove) the Rasputin low-privilege sandbox account used to
  run `shell_exec` on the native host with a bounded blast radius (Phase 3, Option A).

.DESCRIPTION
  Creates a dedicated *standard* local user (default: Rasputin_sbx) with an unknown
  random password, stores that password encrypted with the CALLING USER's DPAPI
  (CurrentUser scope) so only the operator's own Rasputin process can decrypt it, and
  installs a best-effort outbound firewall block scoped to the account.

  The agent's shell commands are then run AS this account (CreateProcessWithLogonW),
  so a mistaken `rm -rf` / `del /s` can only touch folders whose ACLs were explicitly
  granted to it -- not C:\Windows, not the operator's profile, not Rasputin's own DB.

  DELIBERATELY a FIRST-PASS script. Three things can only be validated by the first
  real run on a given machine, so they are isolated here and default to the safe
  choice (see "VALIDATION NOTES" at the end of the run):
    * job-object nesting through the seclogon service  (run-as mechanism)
    * per-user Windows Firewall (WFP) egress scoping
    * logon-rights hardening
  v1 therefore does NOT touch logon rights at all: a standard user already has exactly
  the interactive-logon right CreateProcessWithLogonW needs, and proactively denying it
  is the single most likely way to break the run-as path. Deny-logon hardening is a
  documented follow-up, gated on the mechanism that survives first-run validation.

.PARAMETER AccountName
  Local account to create/repair/remove. Default: Rasputin_sbx.

.PARAMETER DataDir
  Where to write the encrypted credential + metadata. MUST match the backend's
  data_dir() for native mode. Default: %LOCALAPPDATA%\Rasputin\data.

.PARAMETER AllowedHosts
  Optional egress allowlist (e.g. a local package mirror) punched through the block.

.PARAMETER Remove
  Tear everything down: firewall rule, credential file, and the account.

.PARAMETER Status
  Report what currently exists; make no changes.

.NOTES
  Run this ELEVATED, AS THE SAME WINDOWS USER who runs Rasputin. UAC elevation keeps
  your identity (same SID), so the DPAPI-CurrentUser blob stays decryptable by the
  unelevated backend. Running it as a DIFFERENT admin account will store a credential
  the operator cannot read -- the backend detects that mismatch and refuses rather than
  fail obscurely.
#>
[CmdletBinding()]
param(
    [string]$AccountName = "Rasputin_sbx",
    [string]$DataDir = (Join-Path $env:LOCALAPPDATA "Rasputin\data"),
    [string[]]$AllowedHosts = @(),
    [switch]$Remove,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$FirewallRulePrefix = "Rasputin Sandbox Egress"
$CredFileName = "sandbox.cred"

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-AccountSid {
    param([string]$Name)
    try {
        return (New-Object Security.Principal.NTAccount($Name)).Translate([Security.Principal.SecurityIdentifier]).Value
    } catch { return $null }
}

function Write-Section { param([string]$Text) Write-Host "`n== $Text ==" -ForegroundColor Cyan }

# ---------------------------------------------------------------------------
# STATUS (read-only) -- safe to run unelevated
# ---------------------------------------------------------------------------
if ($Status) {
    Write-Section "Rasputin sandbox status"
    $acct = Get-LocalUser -Name $AccountName -ErrorAction SilentlyContinue
    Write-Host ("Account '{0}': {1}" -f $AccountName, $(if ($acct) { "present (enabled=$($acct.Enabled))" } else { "absent" }))
    $sid = Get-AccountSid -Name $AccountName
    Write-Host ("SID: {0}" -f $(if ($sid) { $sid } else { "n/a" }))
    $credPath = Join-Path $DataDir $CredFileName
    Write-Host ("Credential file: {0}" -f $(if (Test-Path $credPath) { $credPath } else { "absent ($credPath)" }))
    $fw = Get-NetFirewallRule -DisplayName "$FirewallRulePrefix*" -ErrorAction SilentlyContinue
    Write-Host ("Firewall rules: {0}" -f $(if ($fw) { ($fw | ForEach-Object DisplayName) -join ", " } else { "none" }))
    return
}

if (-not (Test-Admin)) {
    Write-Error "This action needs an elevated shell. Right-click PowerShell -> Run as administrator, AS THE SAME USER who runs Rasputin, then re-run."
    exit 1
}

# ---------------------------------------------------------------------------
# REMOVE (teardown)
# ---------------------------------------------------------------------------
if ($Remove) {
    Write-Section "Removing Rasputin sandbox"
    Get-NetFirewallRule -DisplayName "$FirewallRulePrefix*" -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-NetFirewallRule -Name $_.Name; Write-Host "Removed firewall rule: $($_.DisplayName)"
    }
    $credPath = Join-Path $DataDir $CredFileName
    if (Test-Path $credPath) { Remove-Item $credPath -Force; Write-Host "Removed credential file: $credPath" }
    if (Get-LocalUser -Name $AccountName -ErrorAction SilentlyContinue) {
        Remove-LocalUser -Name $AccountName; Write-Host "Removed account: $AccountName"
    }
    Write-Host "`nSandbox removed. Host Shell workspaces will fail closed until re-provisioned." -ForegroundColor Yellow
    return
}

# ---------------------------------------------------------------------------
# PROVISION (create / repair) -- idempotent
# ---------------------------------------------------------------------------
Write-Section "Provisioning Rasputin sandbox account"

# 1. Strong random password (never printed, never persisted in cleartext).
Add-Type -AssemblyName System.Web -ErrorAction SilentlyContinue
$plain = [System.Web.Security.Membership]::GeneratePassword(40, 8)
$secure = ConvertTo-SecureString $plain -AsPlainText -Force

# 2. Create or repair the account as a STANDARD user (never Administrators).
$acct = Get-LocalUser -Name $AccountName -ErrorAction SilentlyContinue
if ($acct) {
    Set-LocalUser -Name $AccountName -Password $secure -PasswordNeverExpires $true
    Write-Host "Repaired existing account '$AccountName' (password rotated)."
} else {
    New-LocalUser -Name $AccountName -Password $secure -FullName "Rasputin Sandbox" `
        -Description "Low-privilege account Rasputin uses to run host shell commands. Do not use interactively." `
        -PasswordNeverExpires -UserMayNotChangePassword | Out-Null
    Write-Host "Created account '$AccountName'."
}
# Ensure it is ONLY a standard user: in Users, and definitely not in Administrators.
try { Add-LocalGroupMember -Group "Users" -Member $AccountName -ErrorAction SilentlyContinue } catch {}
try {
    if (Get-LocalGroupMember -Group "Administrators" -Member $AccountName -ErrorAction SilentlyContinue) {
        Remove-LocalGroupMember -Group "Administrators" -Member $AccountName
        Write-Host "  (removed from Administrators -- sandbox must be standard-user)" -ForegroundColor Yellow
    }
} catch {}

$sid = Get-AccountSid -Name $AccountName
Write-Host "Account SID: $sid"

# NOTE (v1): logon rights are intentionally left at the standard-user default.
# CreateProcessWithLogonW performs an interactive-type logon; denying interactive
# logon here would likely break the run-as path. Deny-logon hardening is deferred
# to after first-run mechanism validation (see VALIDATION NOTES).

# 3. Store the password encrypted with the CALLING USER's DPAPI (CurrentUser scope).
#    Only that same user (the operator running Rasputin) can decrypt it later.
Write-Section "Storing credential (DPAPI, CurrentUser)"
if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir -Force | Out-Null }
Add-Type -AssemblyName System.Security
$bytes = [System.Text.Encoding]::UTF8.GetBytes($plain)
$enc = [System.Security.Cryptography.ProtectedData]::Protect(
    $bytes, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
$callerSid = ([Security.Principal.WindowsIdentity]::GetCurrent()).User.Value
$record = [ordered]@{
    account   = $AccountName
    sid       = $sid
    ownerSid  = $callerSid    # backend refuses to use the cred if its own SID differs
    dpapi     = [Convert]::ToBase64String($enc)
    scope     = "CurrentUser"
    createdAt = (Get-Date).ToString("o")
}
$credPath = Join-Path $DataDir $CredFileName
$record | ConvertTo-Json | Set-Content -Path $credPath -Encoding UTF8
# Lock the file down to the caller only.
icacls $credPath /inheritance:r /grant:r ("{0}:(F)" -f $callerSid) | Out-Null
# Scrub the plaintext from this session's memory promptly.
$plain = $null; $bytes = $null; [System.GC]::Collect()
Write-Host "Wrote $credPath (owner-only ACL; plaintext held only in this elevated session, now cleared)."

# 4. Best-effort egress deny scoped to the account SID (WFP user-ID condition).
#    Flagged as validation-pending: per-user outbound scoping is not guaranteed on
#    all builds, and loopback (127.0.0.1/::1) is exempt by Windows design.
Write-Section "Network egress block (best-effort)"
$fwOk = $false
try {
    Get-NetFirewallRule -DisplayName "$FirewallRulePrefix*" -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-NetFirewallRule -Name $_.Name }
    $sddl = "D:(A;;CC;;;$sid)"
    foreach ($h in $AllowedHosts) {
        New-NetFirewallRule -DisplayName "$FirewallRulePrefix Allow $h" -Direction Outbound `
            -Action Allow -RemoteAddress $h -LocalUser $sddl -Profile Any | Out-Null
        Write-Host "  allow egress to $h"
    }
    New-NetFirewallRule -DisplayName "$FirewallRulePrefix Block" -Direction Outbound `
        -Action Block -LocalUser $sddl -Profile Any | Out-Null
    $fwOk = $true
    Write-Host "Installed outbound block for the sandbox account."
} catch {
    Write-Host "  Firewall scoping failed on this machine ($($_.Exception.Message))." -ForegroundColor Yellow
    Write-Host "  Proceeding WITHOUT egress deny -- ACL + account isolation still apply." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Summary + honest limitations
# ---------------------------------------------------------------------------
Write-Section "Done -- what this bought you"
Write-Host "Account      : $AccountName (standard user, unknown random password)"
Write-Host "Credential   : $credPath (DPAPI CurrentUser; owner=$callerSid)"
Write-Host "Egress block : $(if ($fwOk) { 'installed' } else { 'NOT installed (best-effort failed)' })"
Write-Host ""
Write-Host "VALIDATION NOTES (resolved by the first Host Shell run):" -ForegroundColor Cyan
Write-Host "  1. Run-as mechanism: CreateProcessWithLogonW + Job Object nesting via seclogon"
Write-Host "     is expected to work on Win8+, but confirm the process tree is killed on timeout."
Write-Host "  2. Egress deny is best-effort; loopback (127.0.0.1/::1) is NEVER blocked by design,"
Write-Host "     so local services stay reachable. Honest claim: 'external egress denied (if installed);"
Write-Host "     loopback open', not 'no network'."
Write-Host "  3. Deny-interactive-logon hardening deferred until (1) picks the final mechanism."
Write-Host ""
Write-Host "The workspace ACL grant (icacls <ws> /grant ${AccountName}:(OI)(CI)M) is applied by the"
Write-Host "backend when you enable Host Shell on a folder, and removed when you disable it -- not here."
