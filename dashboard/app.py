"""NAS100 Trading OS -- read-only Streamlit dashboard (view layer only).

Never executes trades, never writes to production or research files. Visualizes
existing artifacts only; all numbers come from files other tools produced.

Run:  streamlit run dashboard/app.py       ->  http://localhost:8501
"""
from __future__ import annotations

import csv
import re
import subprocess
from datetime import date
from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parent.parent
MONTH_END = date(2026, 8, 11)

st.set_page_config(page_title="NAS100 Trading OS", page_icon="📈", layout="wide")
# stretch: auto-refresh every 60s (pure meta tag, no backend)
st.markdown('<meta http-equiv="refresh" content="60">', unsafe_allow_html=True)


# ---------------------------------------------------------------- loaders --
def md(rel: str) -> str:
    p = REPO / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def csv_rows(rel: str) -> list[dict]:
    p = REPO / rel
    if not p.exists() or p.stat().st_size == 0:
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def live_fills() -> list[dict]:
    return [r for r in csv_rows("logs/fills.csv")
            if str(r.get("dry_run", "")).lower() != "true"]


def tail(rel: str, n: int = 800) -> list[str]:
    p = REPO / rel
    if not p.exists():
        return []
    return p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]


def sh_git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception as e:
        return f"(git unavailable: {e})"


def badge(color: str, text: str):
    c = {"GREEN": "#21c55d", "YELLOW": "#eab308", "RED": "#ef4444"}.get(color, "#888")
    st.markdown(f'<span style="background:{c};color:#000;padding:2px 10px;'
                f'border-radius:8px;font-weight:700">{text}</span>',
                unsafe_allow_html=True)


def cc_section(name: str) -> str:
    """Extract one section from COMMAND_CENTER.md (no recalculation)."""
    txt = md("dashboard/COMMAND_CENTER.md")
    m = re.search(rf"## \d+\. {name}.*?(?=\n## |\Z)", txt, re.S)
    return m.group(0).split("\n", 1)[-1] if m else \
        f"_{name}: not in COMMAND_CENTER.md (regenerate it)_"


def health_color() -> str:
    m = re.search(r"SYSTEM HEALTH: \*\*(\w+)\*\*", md("dashboard/COMMAND_CENTER.md"))
    return m.group(1) if m else "YELLOW"


# ------------------------------------------------------------------ pages --
page = st.sidebar.radio("Pages", ["HOME", "LIVE", "SHADOW", "RESEARCH",
                                  "EVIDENCE", "LOGS", "SETTINGS"])
st.sidebar.caption("Read-only view layer. Trades and research are NEVER "
                   "modified from here.")

if page == "HOME":
    st.title("NAS100 Trading OS")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("System health")
        badge(health_color(), health_color())
        st.markdown(cc_section("SYSTEM HEALTH"))
    with c2:
        st.subheader("Today")
        st.markdown(cc_section("TODAY"))
        st.subheader("Next decision")
        st.markdown(cc_section("NEXT DECISION"))
    with c3:
        st.subheader("Prop readiness")
        st.markdown(cc_section("PROP READINESS"))
        st.metric("Days to month-end review", max((MONTH_END - date.today()).days, 0))
    st.divider()
    c4, c5 = st.columns(2)
    with c4:
        st.subheader("Latest fill")
        lf = live_fills()
        st.write(lf[-1] if lf else "No live fills yet.")
        st.subheader("Open positions")
        st.caption("Not visible from this host -- run `python status.py` on the VPS "
                   "(authoritative for MT5 positions/equity).")
    with c5:
        st.subheader("Latest shadow events")
        sh = csv_rows("research/results/shadow_signals.csv")
        fired = [r for r in sh if r.get("signal") == "1"][-8:]
        st.table(fired if fired else [{"info": "no shadow signals fired yet"}])

elif page == "LIVE":
    st.title("LIVE execution")
    lf = live_fills()
    if not lf:
        st.info("No live fills yet. (fills.csv on this host is empty -- MT5 fills "
                "accumulate on the VPS ledger. Copy or run the dashboard there for "
                "broker-side truth.)")
    else:
        import pandas as pd
        df = pd.DataFrame(lf)
        for col in ("slippage_bps", "spread_bps", "account_equity", "fill_price"):
            df[col] = pd.to_numeric(df.get(col), errors="coerce")
        df["ts"] = pd.to_datetime(df["timestamp_utc"], errors="coerce")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fills (month)", len(df))
        c2.metric("Slippage avg", f"{df['slippage_bps'].mean():.1f} bps"
                  if df["slippage_bps"].notna().any() else "n/a")
        c3.metric("Spread avg", f"{df['spread_bps'].mean():.1f} bps"
                  if df["spread_bps"].notna().any() else "n/a")
        c4.metric("Latest", str(df["ts"].max())[:16])
        st.subheader("Equity (as recorded at each fill)")
        eq = df.dropna(subset=["account_equity"]).set_index("ts")["account_equity"]
        st.line_chart(eq) if len(eq) else st.caption("no equity column data yet")
        st.subheader("Slippage per fill (bps)")
        sl = df.dropna(subset=["slippage_bps"]).set_index("ts")["slippage_bps"]
        st.bar_chart(sl) if len(sl) else st.caption("no slippage data yet")
        st.subheader("Fills over time")
        st.bar_chart(df.groupby(df["ts"].dt.date).size())
        st.subheader("Recent fills")
        st.dataframe(df.tail(25), use_container_width=True)
    st.caption("Execution-quality report: `python tools/analyze_execution.py` "
               "(writes docs/EXECUTION_ANALYSIS.md).")

elif page == "SHADOW":
    st.title("Forward shadow")
    sh = csv_rows("research/results/shadow_signals.csv")
    days = len({r["date"] for r in sh})
    st.progress(min(days / 15, 1.0),
                text=f"{days}/15 days toward the pre-registered verdict minimum")
    # research expectation column parsed from the frozen review doc (no recalc)
    rev = md("docs/ETF_FORWARD_SHADOW_REVIEW.md")
    exp = dict(re.findall(r"\| (S\d_\w+) \| \d+ \| \d+ \| ([\d.]+) \|", rev))
    if sh:
        per: dict[str, list[int]] = {}
        for r in sh:
            k = r["stream"]
            per.setdefault(k, [0, 0])
            per[k][1] += 1
            per[k][0] += int(r["signal"])
        rows = []
        for k, (f_, n) in sorted(per.items()):
            status = "READY FOR REVIEW" if days >= 15 else (
                "WATCHING" if n else "INSUFFICIENT DATA")
            rows.append({"stream": k, "fired": f_, "days": n,
                         "shadow rate/day": round(f_ / max(n, 1), 2),
                         "research rate/day": exp.get(k, "?"),
                         "status": status})
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No shadow data yet.")
    st.subheader("VIX term-structure gate")
    st.write("Status: WAITING -- needs a backwardation episode to differentiate "
             "(gate values logged daily in shadow_signals.csv).")

elif page == "RESEARCH":
    st.title("Research backlog (frozen)")
    txt = md("docs/RESEARCH_BACKLOG.md")
    st.markdown(txt if txt else "_RESEARCH_BACKLOG.md missing_")
    st.divider()
    st.subheader("Open a report")
    reports = sorted({str(p.relative_to(REPO)) for pat in
                      ("docs/*REVIEW*.md", "docs/*AUDIT*.md", "research/results/*.md")
                      for p in REPO.glob(pat)})
    if reports:
        sel = st.selectbox("report", reports)
        st.markdown(md(sel))
    else:
        st.caption("no reports found")

elif page == "EVIDENCE":
    st.title("Evidence")
    tabs = st.tabs(["COMMAND CENTER", "MONTHLY COMMITTEE", "PROP READINESS",
                    "EVIDENCE LEDGER"])
    for tab, rel in zip(tabs, ["dashboard/COMMAND_CENTER.md",
                               "docs/MONTHLY_EVIDENCE_COMMITTEE.md",
                               "docs/PROP_READINESS.md", "docs/EVIDENCE_LEDGER.md"]):
        with tab:
            txt = md(rel)
            st.markdown(txt if txt else f"_{rel} missing_")

elif page == "LOGS":
    st.title("Logs")
    logs = sorted(str(p.relative_to(REPO)) for p in (REPO / "logs").glob("*.log")) \
        if (REPO / "logs").exists() else []
    if not logs:
        st.info("no log files")
    else:
        sel = st.selectbox("file", logs, index=logs.index("logs/trader.log")
                           if "logs/trader.log" in logs else 0)
        q = st.text_input("filter (substring or regex)", "")
        only_err = st.checkbox("errors/alerts only (CRASH|FAIL|ERROR|ALERT|WATCHDOG)")
        lines = tail(sel)
        if only_err:
            lines = [l for l in lines
                     if re.search(r"CRASH|FAIL|ERROR|ALERT|WATCHDOG|NAKED", l)]
        if q:
            try:
                rx = re.compile(q)
                lines = [l for l in lines if rx.search(l)]
            except re.error:
                lines = [l for l in lines if q in l]
        st.code("\n".join(lines[-400:]) or "(no matching lines)")

elif page == "SETTINGS":
    st.title("Settings / environment")
    st.write({"repo path": str(REPO),
              "git commit": sh_git("rev-parse", "--short", "HEAD"),
              "branch": sh_git("branch", "--show-current"),
              "last sync (last commit)": sh_git("log", "-1", "--format=%ci %s"),
              "auto-refresh": "60 s (meta tag)"})
    st.subheader("VPS status")
    st.caption("Not reachable from this view. Authoritative check on the VPS: "
               "`python status.py` (MT5 connection, symbol maps, task LastResult, "
               "log tails). The daily ledger line mirrors its verdict.")
