"""web.py -- PHASE 701 web interface. Read-only HTML view of market intelligence, calendar,
opportunities, belief + guardian status. Serves on localhost. Places no orders (no broker imports).
Run:  py -m market_intel.web --port 8787 --symbols EURUSD,XAUUSD,NAS100
"""
from __future__ import annotations
import argparse, html, json, os
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from . import calendar_feed as cal
from .opportunity import OpportunityRegistry

SYMBOLS = ["EURUSD", "XAUUSD", "NAS100"]
CSS = """body{font:14px -apple-system,Segoe UI,sans-serif;background:#0d1117;color:#c9d1d9;margin:0;padding:24px}
h1{font-size:18px;margin:0 0 4px}h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#8b949e;margin:26px 0 8px}
table{border-collapse:collapse;width:100%;margin-bottom:8px}th,td{text-align:left;padding:6px 10px;border-bottom:1px solid #21262d}
th{color:#8b949e;font-weight:600;font-size:12px}.up{color:#3fb950}.down{color:#f85149}.warn{color:#d29922}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;background:#21262d}
.shadow{background:#1f2937;color:#d29922;border:1px solid #d29922}.card{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px;margin-bottom:10px}
small{color:#6e7681}"""


def _state_rows(symbols):
    rows = []
    try:
        import MetaTrader5 as mt5, pandas as pd
        from .state import classify
        if mt5.initialize():
            for s in symbols:
                try:
                    def g(tf, n):
                        r = mt5.copy_rates_from_pos(s, tf, 0, n)
                        if r is None or not len(r): return None
                        d = pd.DataFrame(r); d["time"] = pd.to_datetime(d["time"], unit="s", utc=True)
                        return d.set_index("time")[["open", "high", "low", "close"]]
                    m5, d1 = g(mt5.TIMEFRAME_M5, 600), g(mt5.TIMEFRAME_D1, 90)
                    if m5 is None or d1 is None: continue
                    rows.append(classify(s, m5, d1))
                except Exception:
                    continue
    except Exception:
        pass
    return rows


def page(symbols):
    now = datetime.now(timezone.utc)
    states = _state_rows(symbols)
    events = cal.load()
    up = cal.upcoming(events, now=now, hours=48)
    opps = OpportunityRegistry().all()
    try:
        from execution_safety.belief_reader import decide
        bdec, bdet = decide("H_portfolio_multisleeve")
    except Exception as e:
        bdec, bdet = "UNKNOWN", {"error": str(e)[:80]}

    h = [f"<style>{CSS}</style><h1>Market Intelligence</h1>",
         f"<small>{now:%Y-%m-%d %H:%M UTC}</small> &nbsp;",
         "<span class='badge shadow'>EXECUTION: SHADOW — no orders</span>"]

    h.append("<h2>Market state</h2><table><tr><th>symbol</th><th>price</th><th>trend</th><th>vol</th>"
             "<th>session</th><th>kill zone</th><th>structure</th><th>sweep</th><th>fvg</th>"
             "<th>PDH / PDL</th><th>VWAP dist</th></tr>")
    for s in states:
        cls = "up" if s.trend == "up" else "down" if s.trend == "down" else ""
        h.append(f"<tr><td><b>{html.escape(s.symbol)}</b></td><td>{s.price:.5f}</td>"
                 f"<td class='{cls}'>{s.trend}</td><td>{s.volatility_regime}</td><td>{s.session}</td>"
                 f"<td>{','.join(s.kill_zones) or '—'}</td><td>{s.structure}</td>"
                 f"<td>{s.liquidity_sweep}</td><td>{s.fvg}</td>"
                 f"<td>{s.prev_day_high:.5f} / {s.prev_day_low:.5f}</td>"
                 f"<td>{s.dist_vwap_pct:+.3%}</td></tr>")
    if not states:
        h.append("<tr><td colspan=11>no MT5 data (terminal running?)</td></tr>")
    h.append("</table>")

    h.append("<h2>Economic calendar — next 48h</h2><table>"
             "<tr><th>countdown</th><th>impact</th><th>ccy</th><th>event</th>"
             "<th>prev</th><th>forecast</th><th>actual</th><th>surprise</th></tr>")
    for e in up[:15]:
        try:
            t = datetime.fromisoformat(e.scheduled.replace("Z", "+00:00"))
            m = int((t - now).total_seconds() // 60); cd = f"T-{m//60}h{m%60:02d}m" if m > 0 else "DUE"
        except Exception:
            cd = "?"
        sp = e.surprise()
        h.append(f"<tr><td>{cd}</td><td class='{'warn' if e.impact=='high' else ''}'>{e.impact}</td>"
                 f"<td>{html.escape(e.currency)}</td><td>{html.escape(e.name)}</td>"
                 f"<td>{e.previous}</td><td>{e.forecast}</td><td>{e.actual if e.actual is not None else '—'}</td>"
                 f"<td>{f'{sp:+.4g}' if sp is not None else '—'}</td></tr>")
    if not up:
        h.append("<tr><td colspan=8>no calendar feed — set CALENDAR_API_URL / CALENDAR_API_TOKEN"
                 " or drop market_intel/calendar.csv</td></tr>")
    h.append("</table>")

    h.append("<h2>Opportunities</h2>")
    if not opps:
        h.append("<div class='card'><small>none yet — generated only AFTER an official Actual is published</small></div>")
    for o in opps[-10:][::-1]:
        h.append(f"<div class='card'><b>{html.escape(o['instrument'])}</b> "
                 f"dir {o['direction']:+d} · conf {o['confidence']} · "
                 f"<span class='badge'>{html.escape(o['status'])}</span><br>"
                 f"<small>{html.escape(o['economic_reasoning'])}</small><br>"
                 f"<small>for: {html.escape(', '.join(o['evidence_supporting']))} | "
                 f"against: {html.escape(', '.join(o['evidence_contradicting']) or 'none')}</small></div>")

    h.append("<h2>Pipeline status</h2><div class='card'>"
             f"Belief graph: <b>{bdec}</b> <small>{html.escape(json.dumps(bdet))}</small><br>"
             "Guardian: evaluated at order time (fail-closed)<br>"
             "Execution: <b class='warn'>SHADOW</b> — this interface can never place a trade"
             "</div>")
    return "".join(h)


class H(BaseHTTPRequestHandler):
    symbols = SYMBOLS
    def do_GET(self):
        body = ("<meta http-equiv='refresh' content='30'>" + page(self.symbols)).encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--symbols", default=",".join(SYMBOLS))
    a = ap.parse_args()
    H.symbols = [s.strip() for s in a.symbols.split(",") if s.strip()]
    print(f"Market Intelligence -> http://localhost:{a.port}  (refreshes 30s, SHADOW only)")
    HTTPServer(("127.0.0.1", a.port), H).serve_forever()
