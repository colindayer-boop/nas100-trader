# install_evidence_task.ps1 -- Phase 5. RUN ON THE VPS (Administrator PowerShell).
# Registers `nas100-evidence-export`, INDEPENDENT of trading / nas100-update / watchdog.
# A failure here never touches trading. Uses an interactive account (NOT SYSTEM) because
# SYSTEM typically cannot see the live MT5 terminal (confirm with probe_vps_env.py first).
#
#   powershell -ExecutionPolicy Bypass -File install_evidence_task.ps1 `
#       -Repo "C:\...\nas100-trader" -Evidence "C:\...\nas100-live-evidence" `
#       -Python "C:\...\python.exe" -RunUser "ALPHAZONE\Administrator"
param(
  [Parameter(Mandatory=$true)][string]$Repo,
  [string]$Evidence = "C:\Users\Administrator\Documents\nas100-live-evidence",
  [Parameter(Mandatory=$true)][string]$Python,
  [Parameter(Mandatory=$true)][string]$RunUser,   # account proven to reach MT5 (Phase 1)
  [string]$Time1 = "16:20",                        # after the final US session
  [string]$Time2 = "23:20"                         # optional, after overnight
)
$ErrorActionPreference = "Stop"
$sync = Join-Path $Repo "scripts\ops\sync_mt5_evidence.ps1"
$action = "powershell -ExecutionPolicy Bypass -File `"$sync`" -Repo `"$Repo`" -Evidence `"$Evidence`" -Python `"$Python`""

# /IT = run only when $RunUser is logged on (interactive) -> NO stored password needed
# and matches MT5's need for the live desktop session (same mode as the trading tasks).
# /RL LIMITED = no elevation (read-only export). Idempotent: delete then create /f.
function New-EvidenceTask($name, $time) {
  schtasks /query /tn $name *> $null
  if ($LASTEXITCODE -eq 0) { schtasks /delete /tn $name /f *> $null }
  schtasks /create /tn $name /sc DAILY /st $time /ru $RunUser /it /rl LIMITED /tr $action /f
  if ($LASTEXITCODE -ne 0) {
    Write-Host "  /it create failed for $name; retrying without /rl..." -ForegroundColor Yellow
    schtasks /create /tn $name /sc DAILY /st $time /ru $RunUser /it /tr $action /f
  }
  if ($LASTEXITCODE -ne 0) { throw "failed to register $name (exit $LASTEXITCODE)" }
}
New-EvidenceTask "nas100-evidence-export"   $Time1
New-EvidenceTask "nas100-evidence-export-2" $Time2

Write-Host "Registered nas100-evidence-export ($Time1) + -2 ($Time2) as $RunUser [/it, no password]" -ForegroundColor Green
Write-Host "It is INDEPENDENT of trading tasks; an export failure cannot interrupt trading." -ForegroundColor Cyan
Write-Host "Verify:  schtasks /query /tn nas100-evidence-export /fo LIST /v | findstr /i `"Last Result Run`""
