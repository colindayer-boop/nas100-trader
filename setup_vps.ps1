# setup_vps.ps1 — git-free VPS setup. Uses only built-in Windows tools (iwr +
# Expand-Archive + schtasks) so it works on locked-down servers with NO git and
# NO winget. Pulls latest code via the repo ZIP, preserves config.ini, and
# registers auto-update (every 30 min) + hourly BTC task. Idempotent.
#
# Run with ONE line on the VPS (Administrator PowerShell):
#   iex (irm https://raw.githubusercontent.com/colindayer-boop/nas100-trader/main/setup_vps.ps1)

$ErrorActionPreference = "Stop"
$ZipUrl = "https://github.com/colindayer-boop/nas100-trader/archive/refs/heads/main.zip"

Write-Host "== 1. locating live_trader.py ==" -ForegroundColor Cyan
$lt = Get-ChildItem C:\Users -Recurse -Filter live_trader.py -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $lt) { Write-Host "live_trader.py not found under C:\Users" -ForegroundColor Red; return }
$Repo = $lt.DirectoryName
Write-Host ("   repo folder: " + $Repo) -ForegroundColor Green

# ---- pull latest code via ZIP, copying every file EXCEPT config.ini ----
function Update-FromZip {
    param($Repo, $ZipUrl)
    $zip = Join-Path $env:TEMP "nas100_main.zip"
    $tmp = Join-Path $env:TEMP "nas100_main"
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Invoke-WebRequest $ZipUrl -OutFile $zip
    Expand-Archive $zip -DestinationPath $tmp -Force
    $src = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
    Get-ChildItem $src -Recurse -File | Where-Object { $_.Name -ne "config.ini" } | ForEach-Object {
        $rel  = $_.FullName.Substring($src.Length + 1)
        $dest = Join-Path $Repo $rel
        $ddir = Split-Path $dest
        if (-not (Test-Path $ddir)) { New-Item -ItemType Directory -Force -Path $ddir | Out-Null }
        Copy-Item $_.FullName $dest -Force
    }
}

Write-Host "== 2. pulling latest code (ZIP, no git needed) ==" -ForegroundColor Cyan
Update-FromZip -Repo $Repo -ZipUrl $ZipUrl
if (Select-String -Path (Join-Path $Repo "mt5_broker.py") -Pattern "BTCUSD" -Quiet) {
    Write-Host "   OK: BTC fix present in mt5_broker.py" -ForegroundColor Green
} else { Write-Host "   WARNING: BTCUSD not found" -ForegroundColor Red }

Write-Host "== 3. writing standalone updater for the scheduler ==" -ForegroundColor Cyan
$updater = Join-Path $Repo "update_from_github.ps1"
$body = @'
$ErrorActionPreference = "SilentlyContinue"
$Repo = $PSScriptRoot
$zip = Join-Path $env:TEMP "nas100_main.zip"
$tmp = Join-Path $env:TEMP "nas100_main"
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Invoke-WebRequest "https://github.com/colindayer-boop/nas100-trader/archive/refs/heads/main.zip" -OutFile $zip
Expand-Archive $zip -DestinationPath $tmp -Force
$src = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
Get-ChildItem $src -Recurse -File | Where-Object { $_.Name -ne "config.ini" } | ForEach-Object {
    $rel  = $_.FullName.Substring($src.Length + 1)
    $dest = Join-Path $Repo $rel
    $ddir = Split-Path $dest
    if (-not (Test-Path $ddir)) { New-Item -ItemType Directory -Force -Path $ddir | Out-Null }
    Copy-Item $_.FullName $dest -Force
}
'@
Set-Content -Path $updater -Value $body -Encoding UTF8
Write-Host ("   wrote " + $updater) -ForegroundColor Green

Write-Host "== 4. registering scheduled tasks ==" -ForegroundColor Cyan
$trUpdate = 'powershell -ExecutionPolicy Bypass -File "' + $updater + '"'
$trBtc    = 'cmd /c cd /d "' + $Repo + '" && python live_trader.py --broker mt5 --session btc'
schtasks /create /tn "nas100-update" /sc MINUTE /mo 30 /f /tr $trUpdate | Out-Null
schtasks /create /tn "nas100-btc"    /sc HOURLY          /f /tr $trBtc    | Out-Null
Write-Host "   nas100-update (every 30 min) + nas100-btc (hourly) registered" -ForegroundColor Green

Write-Host "== 5. test BTC run ==" -ForegroundColor Cyan
Set-Location $Repo
python live_trader.py --broker mt5 --session btc

Write-Host ""
Write-Host "DONE. Future changes: commit+push on the Mac, VPS pulls the ZIP within 30 min." -ForegroundColor Cyan
