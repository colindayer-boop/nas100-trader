# NAS100 Trading OS — Dashboard

Read-only Streamlit dashboard for monitoring the trading system.

## Quick Start

```bash
pip install -r requirements-dashboard.txt
streamlit run dashboard/app.py
```

The dashboard auto-refreshes every 10 seconds.

## What It Shows

| Section | Description |
|---|---|
| **Health Cards** | Latest log timestamp, session, equity, risk scale |
| **Risk State** | Table of all `risk_state*.json` files (per-broker drawdown tracking) |
| **Recent Orders** | Last 20 order events (fills, dry-runs, failures) |
| **Recent Fills** | Last 20 fill events (live + dry-run) |
| **Warnings / Errors** | Last 30 `WARNING` / `ERROR` log lines |
| **Log Tail** | Expandable last 100 lines of `trader.log` |

## Data Sources

All data is read from the `logs/` directory:

```
logs/
├── trader.log              ← main trading log (RotatingFileHandler)
├── hunt_overnight.log      ← overnight hunt log
├── risk_state.json         ← default risk state
├── risk_state_alpaca.json  ← Alpaca-specific risk state
└── risk_state_binance.json ← Binance-specific risk state
```

## Design Principles

- **Read-only** — never places orders, never writes files.
- **Defensive** — never crashes on missing logs or malformed JSON.
- **`pathlib` only** — no `os.path` calls.
- **Auto-refresh** — updates every 10 seconds via `streamlit-autorefresh`
  (falls back to `<meta http-equiv="refresh">` if the package is absent).

## Architecture

```
dashboard/
├── app.py                  ← single-file Streamlit app
└── README.md               ← this file
```

The dashboard is a **pure consumer** of log and JSON state files. It does not
import any trading modules (`live_trader`, `broker`, etc.) and has zero side
effects on the running system.
