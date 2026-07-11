"""evidence_report.py -- the monthly evidence report as single source of truth.

Three modes, all read-only on trading systems:
  --daily     append one evidence line per day to docs/EVIDENCE_LEDGER.md
              (shadow fire counts, live fills, ops verdict, gate states)
  --weekly    append a weekly summary block (per-stream shadow rates so far,
              slippage stats, silent-stream flags)
  --month-end generate docs/MONTH_1_LIVE_REPORT.md: research expectation vs
              forward shadow vs live execution, verdict per candidate:
              FAILS_FORWARD_EVIDENCE -> rejected | PASSES -> queued for
              post-window review. Nothing is promoted to live by this script.

Data sources (whatever exists on this host; gaps are stated, never faked):
  research/results/shadow_signals.csv     forward shadow (9 ETF survivors + gates)
  research/results/etf_streams.csv        research expectation (trades/day rates)
  logs/fills.csv                          live execution (per-host)
  docs/DAILY_OPS_REPORT.md                today's ops verdict
  state/macro_daily.csv                   regime record
"""
import argparse
import csv
import os
import re
from datetime import date, datetime

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LEDGER = os.path.join(REPO, "docs", "EVIDENCE_LEDGER.md")
SHADOW = os.path.join(REPO, "research", "results", "shadow_signals.csv")
STREAMS = os.path.join(REPO, "research", "results", "etf_streams.csv")
FILLS = os.path.join(REPO, "logs", "fills.csv")
OPS = os.path.join(REPO, "docs", "DAILY_OPS_REPORT.md")
TODAY = date.today().isoformat()


def read_shadow():
    if not os.path.exists(SHADOW):
        return pd.DataFrame()
    return pd.read_csv(SHADOW)


def read_fills():
    if not os.path.exists(FILLS) or os.path.getsize(FILLS) == 0:
        return pd.DataFrame()
    return pd.read_csv(FILLS)


def ops_verdict():
    if not os.path.exists(OPS):
        return "no ops report"
    m = re.search(r"## VERDICT: \*\*(\w[\w ]*)\*\*", open(OPS, encoding="utf-8").read())
    return m.group(1) if m else "unparsed"


def ensure_ledger():
    if not os.path.exists(LEDGER):
        open(LEDGER, "w").write(
            "# EVIDENCE LEDGER\n\n_One line per day, one block per week, appended by "
            "scripts/ops/evidence_report.py. This ledger + the month-end report are "
            "the single source of truth for the go/no-go decision._\n\n"
            "| date | shadow fired/streams | live fills (host) | ops verdict | gates (lvl/ts) |\n"
            "|---|---|---|---|---|\n")


def daily():
    ensure_ledger()
    txt = open(LEDGER).read()
    if f"| {TODAY} |" in txt:
        print(f"ledger already has {TODAY} -- idempotent no-op")
        return
    sh = read_shadow()
    srow = sh[sh["date"] == TODAY] if not sh.empty else sh
    fired = int(srow["signal"].sum()) if not srow.empty else 0
    nstreams = len(srow) if not srow.empty else 0
    gates = (f"{srow['gate_vix_level'].iloc[0]}/{srow['gate_ts_ratio'].iloc[0]}"
             if not srow.empty else "-")
    fl = read_fills()
    nf = len(fl[fl["timestamp_utc"].str.startswith(TODAY)]) if not fl.empty else 0
    open(LEDGER, "a").write(
        f"| {TODAY} | {fired}/{nstreams} | {nf} | {ops_verdict()} | {gates} |\n")
    print(f"ledger + {TODAY}: shadow {fired}/{nstreams}, fills {nf}, ops {ops_verdict()}")


def weekly():
    ensure_ledger()
    sh = read_shadow()
    lines = [f"\n## Week ending {TODAY}\n"]
    if sh.empty:
        lines.append("_no shadow data yet_")
    else:
        days = sh["date"].nunique()
        per = sh.groupby("stream")["signal"].agg(["sum", "count"])
        lines.append(f"_{days} shadow days accumulated._\n")
        lines.append("| stream | fired | days | rate/day |")
        lines.append("|---|---|---|---|")
        for k, r in per.iterrows():
            lines.append(f"| {k} | {int(r['sum'])} | {int(r['count'])} | {r['sum']/max(r['count'],1):.2f} |")
        silent = per[per["sum"] == 0]
        if len(silent) and days >= 10:
            lines.append(f"\nSILENT >=10d (investigate per stream expectation): {list(silent.index)}")
    fl = read_fills()
    if not fl.empty:
        live = fl[fl.get("dry_run", "False").astype(str).str.lower() != "true"]
        s = pd.to_numeric(live.get("slippage_bps"), errors="coerce").dropna()
        lines.append(f"\nLive fills on this host: {len(live)}"
                     + (f" | slippage avg {s.mean():.1f} bps, worst {s.max():.1f}" if len(s) else " | no slippage data"))
    else:
        lines.append("\nLive fills on this host: 0 (VPS holds MT5 fills -- run there too)")
    open(LEDGER, "a").write("\n".join(lines) + "\n")
    print(f"weekly block appended ({TODAY})")


def month_end():
    sh = read_shadow()
    out = [f"# MONTH 1 LIVE REPORT -- generated {datetime.now():%Y-%m-%d %H:%M}",
           "\n_Single source of truth: research expectation vs forward shadow vs live "
           "execution. Verdicts: FAILS_FORWARD_EVIDENCE -> rejected; PASSES -> queued "
           "for post-window human review. This script promotes NOTHING to live._\n"]
    # research expectation: signals/day per stream from the persisted research streams
    exp = {}
    if os.path.exists(STREAMS):
        st = pd.read_csv(STREAMS, index_col=0, parse_dates=True)
        for c in st.columns:
            r = st[c].dropna()
            exp[c] = (r != 0).mean()          # share of days with activity (proxy rate)
    out.append("## Candidate: ETF universe expansion (9 survivors, forward shadow)")
    if sh.empty:
        out.append("_NO shadow data -- report cannot verdict; extend the window._")
    else:
        days = sh["date"].nunique()
        out.append(f"\n_{days} shadow days._\n")
        out.append("| stream | research act-rate/day | shadow rate/day | ratio | verdict |")
        out.append("|---|---|---|---|---|")
        per = sh.groupby("stream")["signal"].agg(["sum", "count"])
        for k, r in per.iterrows():
            e = exp.get(k)
            srate = r["sum"] / max(r["count"], 1)
            if e is None or days < 15:
                v = "EXTEND (insufficient days or no expectation)"
                ratio = ""
            else:
                ratio = f"{srate/max(e,1e-9):.2f}"
                v = ("PASSES -> post-window review queue" if srate >= 0.4 * e
                     else "FAILS_FORWARD_EVIDENCE -> rejected")
            out.append(f"| {k} | {'' if e is None else f'{e:.2f}'} | {srate:.2f} | {ratio} | {v} |")
    # ts-gate shadow
    if not sh.empty and "gate_ts_ratio" in sh:
        g = sh.drop_duplicates("date")[["date", "gate_vix_level", "gate_ts_ratio"]]
        agree = (g["gate_vix_level"].astype(float).gt(0) == g["gate_ts_ratio"].astype(float).gt(0)).mean()
        out.append(f"\n## Candidate: VIX term-structure gate (shadow)\n"
                   f"- {len(g)} gate-days logged; level-vs-ts agreement {agree:.0%}; "
                   f"ts blocked {int((g['gate_ts_ratio'].astype(float)==0).sum())} day(s), "
                   f"level blocked {int((g['gate_vix_level'].astype(float)==0).sum())}.")
        out.append("- Verdict: EXTEND unless a backwardation episode occurs in-window "
                   "(no stress episode = shadow cannot differentiate; do not promote on quiet data).")
    # live execution
    fl = read_fills()
    out.append("\n## Live execution vs research costs")
    if fl.empty:
        out.append("_No fills on this host. MT5 fills live on the VPS ledger -- merge "
                   "logs/fills.csv from the VPS before finalizing the go/no-go._")
    else:
        live = fl[fl.get("dry_run", "False").astype(str).str.lower() != "true"]
        s = pd.to_numeric(live.get("slippage_bps"), errors="coerce").dropna()
        out.append(f"- fills {len(live)} | slippage avg {s.mean():.1f} bps vs 3 bps model"
                   if len(s) else f"- fills {len(live)} | no slippage columns populated")
    out.append("\n## Decision inputs (human)\n- Ops ledger: docs/EVIDENCE_LEDGER.md\n"
               "- Parity/monitoring: NEXT_30_DAY_MONITORING_PLAN section 4 criteria\n"
               "- NOTHING here changes production; promotion requires human sign-off post-window.")
    p = os.path.join(REPO, "docs", "MONTH_1_LIVE_REPORT.md")
    open(p, "w").write("\n".join(out) + "\n")
    print(f"wrote docs/MONTH_1_LIVE_REPORT.md ({'no shadow data' if sh.empty else str(sh['date'].nunique())+' shadow days'})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument("--daily", action="store_true")
    m.add_argument("--weekly", action="store_true")
    m.add_argument("--month-end", action="store_true")
    a = ap.parse_args()
    (daily if a.daily else weekly if a.weekly else month_end)()
