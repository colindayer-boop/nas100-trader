# setup_vps_git.ps1 — one-shot VPS setup: convert the stale ZIP folder into a git
# clone that auto-pulls, and register the BTC hourly task. Run once on the VPS in
# an Administrator PowerShell. Idempotent — safe to re-run.
#
#   iwr https://raw.githubusercontent.com/colindayer-boop/nas100-trader/main/setup_vps_git.ps1 -OutFile setup_vps_git.ps1
#   powershell -ExecutionPolicy Bypass -File .\setup_vps_git.ps1

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/colindayer-boop/nas100-trader.git"

Write-Host "== 1. locating live_trader.py ==" -ForegroundColor Cyan
$lt = Get-ChildItem C:\Users -Recurse -Filter live_trader.py -ErrorAction SilentlyContinue |
      Select-Object -First 1
if (-not $lt) { Write-Host "live_trader.py not found under C:\Users. Clone fresh instead." -ForegroundColor Red; exit 1 }
$Repo = $lt.DirectoryName
Write-Host "   repo folder: $Repo" -ForegroundColor Green
Set-Location $Repo

Write-Host "== 2. checking git ==" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "   git missing — installing via winget..." -ForegroundColor Yellow
    winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
    Write-Host "   >>> CLOSE and REOPEN PowerShell, then re-run this script <<<" -ForegroundColor Red
    exit 0
}

Write-Host "== 3. converting folder to a git clone (config.ini is gitignored -> preserved) ==" -ForegroundColor Cyan
if (-not (Test-Path ".git")) {
    git init | Out-Null
    git remote add origin $RepoUrl
} else {
    git remote set-url origin $RepoUrl 2>$null
}
git fetch origin
git reset --hard origin/main
git branch -M main
git branch --set-upstream-to=origin/main main 2>$null
Write-Host "   now at: $(git log -1 --oneline)" -ForegroundColor Green

Write-Host "== 4. verifying BTC symbol fix landed ==" -ForegroundColor Cyan
if (Select-String -Path .\mt5_broker.py -Pattern '"BTC": "BTCUSD"' -Quiet) {
    Write-Host "   OK: BTC -> BTCUSD present" -ForegroundColor Green
} else {
    Write-Host "   WARNING: BTC map missing — the push may not have reached GitHub yet" -ForegroundColor Red
}

Write-Host "== 5. registering scheduled tasks ==" -ForegroundColor Cyan
# auto-update: git pull every 30 min
schtasks /create /tn "nas100-update" /sc MINUTE /mo 30 /f `
    /tr "cmd /c cd /d `"$Repo`" && git pull" | Out-Null
# BTC sweep hourly (code self-gates to 08-16 UTC)
schtasks /create /tn "nas100-btc" /sc HOURLY /f `
    /tr "cmd /c cd /d `"$Repo`" && python live_trader.py --broker mt5 --session btc" | Out-Null
Write-Host "   nas100-update (git pull /30min) + nas100-btc (hourly) registered" -ForegroundColor Green

Write-Host "== 6. test BTC run ==" -ForegroundColor Cyan
python live_trader.py --broker mt5 --session btc

Write-Host "`nDONE. Future code changes: commit+push on the Mac -> VPS pulls within 30 min." -ForegroundColor Cyan
