# RUNBOOK — EMERGENCY STOP

**When:** any suspected runaway execution, orphan position, missing broker stop, or loss of attribution.

1. **MT5:** click the green **Algo Trading** button → grey. No EA/script can open or modify positions.
2. **VPS:** Task Manager → Details → end any `python.exe` running `live_trader.py` / `phase404_live.py`.
   Check **Task Scheduler** and **Startup** and disable any entry that relaunches them.
3. **Guardian kill switch:** set `KILL_SWITCH=1` in `config/guardian.env` (blocks all new entries).
4. **Do NOT auto-close positions.** Record ticket, symbol, volume, SL, entry, magic, comment.
5. **Save logs:** MT5 Journal + Experts tabs → Save As; copy `MQL5/Logs/`.
6. **Classify** each open position via [RUNBOOK_ORPHAN_POSITION.md](RUNBOOK_ORPHAN_POSITION.md).
7. Do not restart execution until the readiness checklist passes and a human approves.
