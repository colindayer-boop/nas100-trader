"""
weekly_report.py — Friday summary of live paper-trading activity → Telegram.

Pulls the source-of-truth from the BROKER (not local logs, which are wiped each
cloud run): filled orders in the last 7 days + current equity + 1-week P&L from
Alpaca's portfolio-history endpoint. Posts one clean summary via alerts.send().

Run:  python weekly_report.py
Schedule: GitHub Actions cron "0 22 * * 5" (Fri 22:00 UTC, after US close).
"""
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

import alerts
from broker import load_config

ALPACA_DATA_BASE = "https://paper-api.alpaca.markets"


def _get(path: str, key: str, secret: str, params: dict | None = None):
    url = f"{ALPACA_DATA_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def build_report() -> str:
    cfg = load_config("alpaca")
    key    = cfg.get("key", "").strip()
    secret = cfg.get("secret", "").strip()
    if not key or key.startswith("YOUR_"):
        return "📊 Weekly report: Alpaca keys not configured — skipped."

    # current equity
    acct = _get("/v2/account", key, secret)
    equity = float(acct.get("equity", 0))

    # 1-week P&L from portfolio history
    pnl_str = "n/a"
    try:
        hist = _get("/v2/account/portfolio/history", key, secret,
                    {"period": "1W", "timeframe": "1D"})
        pl = [p for p in hist.get("profit_loss", []) if p is not None]
        if pl:
            week_pnl = sum(pl)
            base = equity - week_pnl
            pct = (week_pnl / base * 100) if base else 0
            sign = "+" if week_pnl >= 0 else ""
            pnl_str = f"{sign}${week_pnl:,.2f} ({sign}{pct:.2f}%)"
    except Exception as e:
        pnl_str = f"n/a ({type(e).__name__})"

    # filled orders in the last 7 days
    after = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        orders = _get("/v2/orders", key, secret,
                      {"status": "closed", "after": after, "limit": 500})
        fills = [o for o in orders if o.get("filled_at")]
    except Exception as e:
        fills = []
    n = len(fills)

    lines = [
        "📊 WEEKLY REPORT (Alpaca paper)",
        f"Trades this week: {n}",
        f"Week P&L: {pnl_str}",
        f"Equity: ${equity:,.2f}",
    ]
    if n:
        lines.append("—")
        for o in fills[:12]:
            sym = o.get("symbol", "?")
            side = (o.get("side", "") or "").upper()
            qty = o.get("filled_qty", o.get("qty", "?"))
            when = (o.get("filled_at", "") or "")[:10]
            lines.append(f"{when} {side} {qty} {sym}")
    else:
        lines.append("(no trades — expected rate ~1-2/wk; a 0 week is normal)")
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        msg = build_report()
    except Exception as e:
        msg = f"📊 Weekly report FAILED: {type(e).__name__}: {e}"
    print(msg)
    alerts.send(msg)
