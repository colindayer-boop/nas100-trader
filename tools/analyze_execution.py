"""
analyze_execution.py -- execution-quality analytics over logs/fills.csv.

Read-only: consumes the fill ledger, writes a CSV summary and a Markdown report.
Never touches trading code. Gracefully reports when the ledger is empty/missing
(expected until the first post-deploy order).

Usage:
    python tools/analyze_execution.py
    python tools/analyze_execution.py --input logs/fills.csv \
        --csv research/results/execution_analysis.csv \
        --md  docs/EXECUTION_ANALYSIS.md
    python tools/analyze_execution.py --include-dry    # include dry-run rows
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKTEST_COST_BPS = 3.0     # the research cost assumption (SLIP=0.0003/side)


def fnum(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def load(path, include_dry):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not include_dry:
        rows = [r for r in rows if str(r.get("dry_run", "")).lower() != "true"]
    return rows


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"n": len(vals), "avg": sum(vals) / len(vals),
            "worst": max(vals), "best": min(vals)}


def group_slippage(rows, key):
    g = defaultdict(list)
    for r in rows:
        s = fnum(r.get("slippage_bps"))
        if s is not None:
            g[r.get(key) or "(blank)"].append(s)
    return {k: stats(v) for k, v in sorted(g.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join(REPO, "logs", "fills.csv"))
    ap.add_argument("--csv", default=os.path.join(REPO, "research", "results",
                                                  "execution_analysis.csv"))
    ap.add_argument("--md", default=os.path.join(REPO, "docs",
                                                 "EXECUTION_ANALYSIS.md"))
    ap.add_argument("--include-dry", action="store_true")
    args = ap.parse_args()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = load(args.input, args.include_dry)

    os.makedirs(os.path.dirname(args.md), exist_ok=True)
    os.makedirs(os.path.dirname(args.csv), exist_ok=True)

    if not rows:
        msg = (f"# EXECUTION ANALYSIS - {now}\n\n"
               f"**No fill data yet.** `{os.path.relpath(args.input, REPO)}` is "
               f"missing or has no qualifying rows.\n\n"
               f"This is EXPECTED until the first order after the fill-ledger "
               f"deploy (2026-07-10): the ledger writes one row per submitted "
               f"order, and none has occurred on this host since. The VPS keeps "
               f"its own logs/fills.csv - run this tool there (or copy the file) "
               f"for MT5 fills.\n")
        open(args.md, "w", encoding="utf-8").write(msg)
        open(args.csv, "w", encoding="utf-8").write("metric,value\nrows,0\n")
        print("no fill data (report written explaining why)")
        return

    spreads = [fnum(r.get("spread_bps")) for r in rows]
    slips = [fnum(r.get("slippage_bps")) for r in rows]
    sp, sl = stats([s for s in spreads if s is not None]), \
             stats([s for s in slips if s is not None])

    by_strat = group_slippage(rows, "strategy")
    by_sess = group_slippage(rows, "session")
    by_sym = group_slippage(rows, "symbol")

    # expected vs actual entry, per fill
    detail = []
    for r in rows:
        sig, fill = fnum(r.get("signal_price")), fnum(r.get("fill_price"))
        detail.append({
            "timestamp_utc": r.get("timestamp_utc", ""),
            "strategy": r.get("strategy", ""), "session": r.get("session", ""),
            "symbol": r.get("symbol", ""), "side": r.get("side", ""),
            "expected_entry": sig if sig is not None else "",
            "actual_entry": fill if fill is not None else "",
            "slippage_bps": fnum(r.get("slippage_bps")) if fnum(r.get("slippage_bps")) is not None else "",
            "spread_bps": fnum(r.get("spread_bps")) if fnum(r.get("spread_bps")) is not None else "",
            "status": r.get("status", ""), "dry_run": r.get("dry_run", ""),
        })

    # ---- CSV output ----------------------------------------------------------
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["section", "key", "n", "avg", "worst", "best"])
        if sp: w.writerow(["overall", "spread_bps", sp["n"], f"{sp['avg']:.3f}",
                           f"{sp['worst']:.3f}", f"{sp['best']:.3f}"])
        if sl: w.writerow(["overall", "slippage_bps", sl["n"], f"{sl['avg']:.3f}",
                           f"{sl['worst']:.3f}", f"{sl['best']:.3f}"])
        for name, grp in (("by_strategy", by_strat), ("by_session", by_sess),
                          ("by_symbol", by_sym)):
            for k, s in grp.items():
                if s:
                    w.writerow([name, k, s["n"], f"{s['avg']:.3f}",
                                f"{s['worst']:.3f}", f"{s['best']:.3f}"])
        w.writerow([])
        w.writerow(["fill", "timestamp_utc", "strategy", "symbol", "side",
                    "expected_entry", "actual_entry", "slippage_bps", "status"])
        for d in detail:
            w.writerow(["fill", d["timestamp_utc"], d["strategy"], d["symbol"],
                        d["side"], d["expected_entry"], d["actual_entry"],
                        d["slippage_bps"], d["status"]])

    # ---- Markdown report -----------------------------------------------------
    def tbl(grp):
        out = ["| key | n | avg bps | worst | best |", "|---|---|---|---|---|"]
        for k, s in grp.items():
            if s:
                out.append(f"| {k} | {s['n']} | {s['avg']:.2f} | "
                           f"{s['worst']:.2f} | {s['best']:.2f} |")
        return "\n".join(out) if len(out) > 2 else "_no measurable rows_"

    md = [f"# EXECUTION ANALYSIS - {now}",
          f"\n_{len(rows)} qualifying fills from `{os.path.relpath(args.input, REPO)}`"
          f" (dry-run rows {'included' if args.include_dry else 'excluded'})._",
          f"\nResearch cost assumption: **{BACKTEST_COST_BPS} bps/side**. "
          f"Positive slippage = paid worse than the signal price.",
          "\n## Overall"]
    if sp: md.append(f"- average spread: **{sp['avg']:.2f} bps** (n={sp['n']})")
    if sl: md.append(f"- average slippage: **{sl['avg']:.2f} bps** | worst: "
                     f"**{sl['worst']:.2f}** | best: {sl['best']:.2f} (n={sl['n']})")
    if sl:
        verdict = ("WITHIN model" if sl["avg"] <= BACKTEST_COST_BPS else
                   "EXCEEDS the 3 bps model -- re-cost the backtest before funding")
        md.append(f"- **verdict vs research costs: {verdict}**")
    md += ["\n## Slippage by strategy", tbl(by_strat),
           "\n## Slippage by session", tbl(by_sess),
           "\n## Slippage by symbol", tbl(by_sym),
           "\n## Expected vs actual entry (per fill)",
           "| time (UTC) | strat | symbol | side | expected | actual | slip bps | status |",
           "|---|---|---|---|---|---|---|---|"]
    for d in detail[-50:]:
        md.append(f"| {d['timestamp_utc']} | {d['strategy']} | {d['symbol']} | "
                  f"{d['side']} | {d['expected_entry']} | {d['actual_entry']} | "
                  f"{d['slippage_bps']} | {d['status']} |")
    open(args.md, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"wrote {os.path.relpath(args.csv, REPO)} and {os.path.relpath(args.md, REPO)}"
          f" ({len(rows)} fills)")


if __name__ == "__main__":
    main()
