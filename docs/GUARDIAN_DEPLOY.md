# prop_risk_guardian -- PowerShell deployment (Windows VPS)

```powershell
cd C:\Users\Administrator\Downloads\nas100-trader-main\nas100-trader-main
# run once (monitor)
python scripts\prop_risk_guardian.py --mode monitor --once --config config\guardian.env
# run continuously in MONITOR (safe: logs/alerts only, never blocks live)
python scripts\prop_risk_guardian.py --mode monitor --config config\guardian.env
# replay the last 2 weeks
python scripts\prop_risk_guardian.py --replay logs\mt5_history.html --config config\guardian.env
# inspect logs
Get-Content logs\risk_guardian_audit.csv -Tail 20
Get-Content runtime\risk_guardian_state.json

# install as a Scheduled Task (MONITOR mode) -- runs at logon, restarts if it dies
$act = New-ScheduledTaskAction -Execute "python" -Argument "scripts\prop_risk_guardian.py --mode monitor --config config\guardian.env" -WorkingDirectory (Get-Location)
$trg = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "PropRiskGuardian" -Action $act -Trigger $trg -RunLevel Highest
# remove the task
Unregister-ScheduledTask -TaskName "PropRiskGuardian" -Confirm:$false

# ---- ENFORCE mode: ONLY after you review RISK_GUARDIAN_REPLAY.md and approve ----
# python scripts\prop_risk_guardian.py --mode enforce --config config\guardian.env
# return safely to monitor: just restart with --mode monitor
```
The live bot is NOT modified or restarted by any of this. Guardian is standalone.
