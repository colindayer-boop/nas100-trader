---
type: incident
date: 2026-07-06
severity: critical
status: resolved
tags: [incident, postmortem]
---
# Emoji crash - silent 6-day outage

**Impact:** every scheduled MT5 run exited code 1 BEFORE evaluating any strategy, for ~6 days. Looked like 'no trades / bad edge'.\n\n**Root cause:** scheduled tasks redirect stdout to a cp1252 log file; a print with an emoji (`SPY Golden` + check-mark) raised `UnicodeEncodeError`. Manual runs (UTF-8 console) worked, masking it.\n\n**Fix:** `sys.stdout/stderr.reconfigure(utf-8, errors=replace)` + `PYTHONUTF8=1` in the .bat + stripped all non-ASCII from `live_trader.py`.\n\n**Lesson:** fail loud; ASCII logs; a green manual run != a green scheduled run.

Back: [[08-Incidents-and-Postmortems/_index|Incidents]]
