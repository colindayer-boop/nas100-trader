# setup_vps.ps1 — one-shot VPS setup for the MT5 bot (Windows).
# Run in PowerShell:  powershell -ExecutionPolicy Bypass -File setup_vps.ps1
#
# Does: download the repo, install Python deps, and create config.ini with your
# MT5 demo creds (prompted — the password is NEVER stored in this script or git).
# Prereqs: Python 3 (64-bit) installed and on PATH, and the MT5 terminal installed
# + logged into your Pepperstone demo.

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/colindayer-boop/nas100-trader/archive/refs/heads/main.zip"
$Target  = "$HOME\nas100-trader"

Write-Host "`n=== 1/4  Checking Python ===" -ForegroundColor Cyan
try { $pv = (python --version) 2>&1; Write-Host "  $pv" }
catch { Write-Host "  Python not found. Install 64-bit Python from python.org (tick 'Add to PATH'), then re-run." -ForegroundColor Red; exit 1 }

Write-Host "`n=== 2/4  Downloading the bot ===" -ForegroundColor Cyan
$zip = "$env:TEMP\nas100.zip"
Invoke-WebRequest -Uri $RepoUrl -OutFile $zip
if (Test-Path $Target) { Remove-Item "$Target.bak" -Recurse -Force -ErrorAction SilentlyContinue; Rename-Item $Target "$Target.bak" }
Expand-Archive -Path $zip -DestinationPath $HOME -Force
Rename-Item "$HOME\nas100-trader-main" $Target
# preserve an existing config.ini from the backup so you don't re-enter creds
if (Test-Path "$Target.bak\config.ini") { Copy-Item "$Target.bak\config.ini" "$Target\config.ini" -Force; Write-Host "  (kept your existing config.ini)" }
Write-Host "  Code in: $Target"

Write-Host "`n=== 3/4  Installing Python packages ===" -ForegroundColor Cyan
python -m pip install --quiet --upgrade pip
python -m pip install --quiet MetaTrader5 pandas pytz numpy yfinance requests
Write-Host "  Done."

Write-Host "`n=== 4/4  Config (MT5 credentials) ===" -ForegroundColor Cyan
$cfgPath = "$Target\config.ini"
if (Test-Path $cfgPath -PathType Leaf -ErrorAction SilentlyContinue) {
    $existing = Get-Content $cfgPath -Raw
} else { $existing = "" }
if ($existing -match "(?m)^\[mt5\]" -and $existing -notmatch "PASTE_") {
    Write-Host "  config.ini already has an [mt5] section — keeping it."
} else {
    Write-Host "  Enter your Pepperstone MT5 demo details:"
    $login  = Read-Host "    Login (e.g. 61552095)"
    $server = Read-Host "    Server (e.g. mt5-demo01.pepperstone.com)"
    $sec    = Read-Host "    Password" -AsSecureString
    $pw     = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    $mt5 = @"
[mt5]
login     = $login
password  = $pw
server    = $server
map_qqq   = NAS100
map_spy   = US500
map_gld   = XAUUSD
risk_scale = 1.0
"@
    # append (or create) — config.ini is gitignored, never committed
    Add-Content -Path $cfgPath -Value "`n$mt5"
    Write-Host "  Wrote [mt5] section to config.ini"
}

Write-Host "`n=== Setup complete ===" -ForegroundColor Green
Write-Host "Make sure the MT5 terminal is open + logged into the demo, then run:"
Write-Host "    cd $Target" -ForegroundColor Yellow
Write-Host "    python mt5_broker.py" -ForegroundColor Yellow
Write-Host "It will print your broker's real symbol names. Send those to confirm the mapping.`n"
