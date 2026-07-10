# Bugs Fixed

<!-- AUTO:BEGIN (do not edit inside this block) -->
_generated 2026-07-10 10:40 by the Obsidian Bridge_

Canonical record of confirmed bugs and their fixes.

- Full tables: [[LIVE_TRADING_PARITY]] (repo docs/) -- unit bug, filter
  starvation, GTC brackets, naked orders, timezone, emoji crash, startup.
- Post-mortems: [[08-Incidents-and-Postmortems/_index|Incidents index]]
- Verification trail: [[AI Session Log]]

| Bug | Fixed in | Post-mortem |
|---|---|---|
| get_bars DAYS vs BARS unit mismatch | 236abe3 | LIVE_TRADING_PARITY |
| 30-bar filter starvation (EMA50/HighVol) | 236abe3 | LIVE_TRADING_PARITY |
| Alpaca DAY brackets expired at close | 236abe3 | LIVE_TRADING_PARITY |
| Startup SyntaxError + args-before-parse | fd0ff25 | STARTUP_FIX_REPORT |
| Naked MT5 orders (no SL/TP) | see git ~0ce6e24 era | [[08-Incidents-and-Postmortems/2026-07-07 Naked Orders|note]] |
| Emoji crash (6-day silent outage) | ae148e3 era | [[08-Incidents-and-Postmortems/2026-07-06 Emoji Crash|note]] |
| MT5 server-time bars ~3h shift | Fable PR | [[08-Incidents-and-Postmortems/Timezone Bug|note]] |

Back: [[Production Index]] | [[00 Dashboard]]
<!-- AUTO:END -->
