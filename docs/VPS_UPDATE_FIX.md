# VPS UPDATE TASK FIX -- `nas100-update` Last Result 0x800710E0

_2026-07-13. Operational only. No strategy signals, filters, timeframes, sizing,
stops, targets, or execution touched._

## Symptom
Windows Scheduled Task `nas100-update` reports **Last Result: -2147020576 =
0x800710E0 = Win32 4320 = ERROR_OPERATOR_OR_ADMIN_HAS_REFUSED_THE_REQUEST**.

## Root cause
The task was registered by `setup_vps_git.ps1` as:
```
schtasks /create /tn "nas100-update" /sc MINUTE /mo 30 /f /tr 'cmd /c cd /d "<Repo>" && git pull'
```
No `/ru` was given, so the task defaults to **"run only when user is logged on."**
0x800710E0 is the textbook code for that task firing while the RDP operator is
**logged off** (disconnecting keeps the session; a real logoff / reboot / idle
policy ends it). The identical code also appears if a bare `git pull` **hangs**
(credential or merge-editor prompt): the default *do-not-start-new-instance*
policy then refuses every subsequent 30-min trigger. Both are deployment-
mechanism faults.

## Fix (repo-side, `setup_vps_git.ps1`)
Register the update task to run as **SYSTEM** (always "logged on", no stored
password, has the Machine PATH + network for a public-repo pull) and harden the
action so it can never hang:
```
$trUpdate = 'cmd /c cd /d "<Repo>" && set GIT_TERMINAL_PROMPT=0 && git config --global --add safe.directory "<Repo>" && git pull --ff-only'
schtasks /create /tn "nas100-update" /sc MINUTE /mo 30 /f /ru SYSTEM /tr $trUpdate
```
- `/ru SYSTEM` -> removes the "logged-on" dependency (kills the 4320 cause).
- `GIT_TERMINAL_PROMPT=0` -> git fails fast instead of blocking on a prompt.
- `git pull --ff-only` -> deterministic; never opens a merge editor.
- `safe.directory` -> SYSTEM trusts the admin-owned working tree.
- Untracked files are never deleted; `config.ini` is gitignored and preserved.

## Confirmations (objective 5)
| check | result |
|---|---|
| git pull works non-interactively | YES -- `GIT_TERMINAL_PROMPT=0 git pull --ff-only` verified on the dev host ("Already up to date."); the flag makes a missing-credential case fail fast, not hang |
| task runs from the correct repo dir | YES -- `cd /d "<Repo>"` unchanged (auto-located under C:\Users) |
| correct executable | YES -- `git` resolved via Machine PATH (available to SYSTEM) |
| untracked VPS files not deleted | YES -- pull/ff-only never remove untracked files; `config.ini` gitignored |
| production strategy code unchanged | YES -- only `setup_vps_git.ps1` changed (diff-verified) |

## Apply on the VPS (one time, Administrator PowerShell)
Re-register the single task with the corrected definition. This does NOT run the
full setup (which would fire a live BTC test session -- avoided during the window):
```powershell
$Repo = (Get-ChildItem C:\Users -Recurse -Filter live_trader.py -EA SilentlyContinue | Select -First 1).DirectoryName
$trUpdate = 'cmd /c cd /d "' + $Repo + '" && set GIT_TERMINAL_PROMPT=0 && git config --global --add safe.directory "' + $Repo + '" && git pull --ff-only'
schtasks /create /tn "nas100-update" /sc MINUTE /mo 30 /f /ru SYSTEM /tr $trUpdate
schtasks /run /tn "nas100-update"
Start-Sleep 20
schtasks /query /tn "nas100-update" /fo LIST /v | Select-String "Last Result"   # expect 0x0
```

## Evidence from this host (objective 7; VPS sections need the VPS)
- `git rev-parse --short HEAD` -> **9ff3654**
- `python status.py` -> exit 0; MT5 + Scheduled-Tasks sections print "run on the
  VPS" (Windows-only, as designed) -- not runnable from macOS.
- `python tools/audit_signal_parity.py` -> exit 0; all rows are pre-window
  (<= 2026-07-13) and "live" counts reflect THIS host's logs only (the tool says
  so). VPS-truth parity requires running it on the VPS after the window opens.

**Objective 6 (run task, confirm Last Result 0) can only be executed on the VPS.**
It is the first block of the "Apply on the VPS" command above; the non-interactive
`git pull --ff-only` half was verified here as a proxy.
