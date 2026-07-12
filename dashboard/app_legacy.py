"""
NAS100 Trading OS — Read-only Streamlit Dashboard.

Displays live trading system state from logs/ and risk_state*.json.
Never writes, never places orders, never crashes on missing/malformed data.

Run:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

# ── paths ────────────────────────────────────────────────────────────────────

BASE_DIR: Path = Path(__file__).resolve().parent.parent
LOG_DIR: Path = BASE_DIR / "logs"

# ── page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NAS100 Trading OS",
    page_icon="📈",
    layout="wide",
)

# ── helpers (all defensive, never raise) ─────────────────────────────────────


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    """Load JSON without crashing on missing files or malformed content."""
    try:
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return None
        return json.loads(text)
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _tail_lines(path: Path, n: int = 100) -> list[str]:
    """Return the last *n* lines of a text file (empty list on any error)."""
    try:
        if not path.is_file():
            return []
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            all_lines = fh.readlines()
        return [line.rstrip("\n") for line in all_lines[-n:]]
    except OSError:
        return []


def _all_log_files() -> list[Path]:
    """Return every *.log file in LOG_DIR, newest first."""
    try:
        files = sorted(
            LOG_DIR.glob("*.log"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )
        return files
    except OSError:
        return []


def _read_all_log_lines() -> list[str]:
    """Concatenate lines from every log file (newest first)."""
    out: list[str] = []
    for f in _all_log_files():
        try:
            with f.open("r", encoding="utf-8", errors="ignore") as fh:
                out.extend(fh.readlines())
        except OSError:
            continue
    return [line.rstrip("\n") for line in out]


# ── regex patterns for log parsing ───────────────────────────────────────────

_TS_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
)
_LEVEL_RE = re.compile(r"\b(INFO|WARNING|ERROR|CRITICAL)\b")
_SESSION_START_RE = re.compile(r"SESSION (\S+) start")
_SESSION_RUN_RE = re.compile(r"START session=(\S+)")
_END_RE = re.compile(r"END session=(\S+)")
_EQUITY_RE = re.compile(r"equity \$([\d,.]+)")
_RISK_SCALE_RE = re.compile(r"RISK_SCALE=([\d.]+)")
_FILL_RE = re.compile(
    r"FILL (\S+) (BUY|SELL) ([\d.]+) (\S+)"
)
_DRY_RUN_RE = re.compile(
    r"\[DRY-RUN\] WOULD (BUY|SELL) ([\d.]+) (\S+) \((\S+)\)"
)
_ORDER_FAIL_RE = re.compile(r"ORDER_FAIL")

_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _parse_ts(line: str) -> datetime | None:
    m = _TS_RE.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), _LOG_DATEFMT)
    except ValueError:
        return None


# ── extract health data from logs ────────────────────────────────────────────


def _latest_timestamp(lines: list[str]) -> str:
    """Return the most recent log timestamp as a human string."""
    for line in reversed(lines):
        ts = _parse_ts(line)
        if ts:
            return ts.strftime("%Y-%m-%d %H:%M:%S")
    return "No logs found"


def _latest_session(lines: list[str]) -> str:
    """Return the most recent session name from START or SESSION lines."""
    for line in reversed(lines):
        m = _SESSION_RUN_RE.search(line)
        if m:
            return m.group(1)
        m = _SESSION_START_RE.search(line)
        if m:
            return m.group(1)
    return "N/A"


def _latest_equity(lines: list[str]) -> str:
    """Return the most recent equity figure found in the logs."""
    for line in reversed(lines):
        m = _EQUITY_RE.search(line)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                return f"${float(raw):,.2f}"
            except ValueError:
                continue
    return "N/A"


def _latest_risk_scale(lines: list[str]) -> str:
    """Return the most recent RISK_SCALE value."""
    for line in reversed(lines):
        m = _RISK_SCALE_RE.search(line)
        if m:
            return m.group(1)
    return "N/A"


# ── extract structured data ──────────────────────────────────────────────────


def _recent_fills(lines: list[str], limit: int = 20) -> list[dict[str, str]]:
    """Extract the most recent fill events (live + dry-run)."""
    fills: list[dict[str, str]] = []
    for line in reversed(lines):
        if len(fills) >= limit:
            break
        ts = _parse_ts(line)
        ts_str = ts.strftime("%m-%d %H:%M") if ts else "?"

        m = _FILL_RE.search(line)
        if m:
            fills.append({
                "Time": ts_str,
                "Tag": m.group(1),
                "Side": m.group(2),
                "Qty": m.group(3),
                "Symbol": m.group(4),
                "Type": "LIVE",
            })
            continue

        m = _DRY_RUN_RE.search(line)
        if m:
            fills.append({
                "Time": ts_str,
                "Tag": m.group(4),
                "Side": m.group(1),
                "Qty": m.group(2),
                "Symbol": m.group(3),
                "Type": "DRY-RUN",
            })
            continue

    return fills


def _recent_orders(lines: list[str], limit: int = 20) -> list[dict[str, str]]:
    """Extract recent order attempts (fills, dry-runs, and failures)."""
    orders: list[dict[str, str]] = []
    for line in reversed(lines):
        if len(orders) >= limit:
            break
        ts = _parse_ts(line)
        ts_str = ts.strftime("%m-%d %H:%M") if ts else "?"

        m = _FILL_RE.search(line)
        if m:
            orders.append({
                "Time": ts_str,
                "Tag": m.group(1),
                "Side": m.group(2),
                "Qty": m.group(3),
                "Symbol": m.group(4),
                "Status": "FILLED",
            })
            continue

        m = _DRY_RUN_RE.search(line)
        if m:
            orders.append({
                "Time": ts_str,
                "Tag": m.group(4),
                "Side": m.group(1),
                "Qty": m.group(2),
                "Symbol": m.group(3),
                "Status": "DRY-RUN",
            })
            continue

        if _ORDER_FAIL_RE.search(line):
            orders.append({
                "Time": ts_str,
                "Tag": "—",
                "Side": "—",
                "Qty": "—",
                "Symbol": "—",
                "Status": "FAILED",
            })
            continue

    return orders


def _warnings_errors(lines: list[str], limit: int = 30) -> list[dict[str, str]]:
    """Extract WARNING / ERROR / CRITICAL lines."""
    out: list[dict[str, str]] = []
    for line in reversed(lines):
        if len(out) >= limit:
            break
        level_m = _LEVEL_RE.search(line)
        if not level_m:
            continue
        level = level_m.group(1)
        if level not in ("WARNING", "ERROR", "CRITICAL"):
            continue
        ts = _parse_ts(line)
        ts_str = ts.strftime("%m-%d %H:%M:%S") if ts else "?"
        # Trim the timestamp + level prefix for the message
        msg = line
        ts_m = _TS_RE.match(line)
        if ts_m:
            msg = line[len(ts_m.group(0)):]
        msg = msg.lstrip(", ")
        out.append({
            "Time": ts_str,
            "Level": level,
            "Message": msg[:200],
        })
    return out


def _risk_state_rows() -> list[dict[str, Any]]:
    """Build a table of all risk_state*.json files."""
    rows: list[dict[str, Any]] = []
    try:
        files = sorted(LOG_DIR.glob("risk_state*.json"))
    except OSError:
        return rows

    for path in files:
        data = _safe_read_json(path)
        broker_name = path.stem.replace("risk_state", "").strip("_") or "default"
        if data is None:
            rows.append({
                "Broker": broker_name,
                "Month": "—",
                "Month-Start Equity": "—",
                "Peak Equity": "—",
                "Drawdown": "—",
                "Status": "Missing / unreadable",
            })
            continue

        peak = float(data.get("peak_equity", 0) or 0)
        month_start = float(data.get("month_start_equity", 0) or 0)
        dd = ""
        if peak > 0 and month_start > 0:
            dd_val = (month_start - peak) / peak
            dd = f"{dd_val:+.2%}"
        rows.append({
            "Broker": broker_name,
            "Month": str(data.get("month_key", "—")),
            "Month-Start Equity": f"${month_start:,.2f}" if month_start else "—",
            "Peak Equity": f"${peak:,.2f}" if peak else "—",
            "Drawdown": dd or "—",
            "Status": "OK",
        })
    return rows


# ── sidebar ──────────────────────────────────────────────────────────────────


def render_sidebar() -> None:
    st.sidebar.header("⚙️ Dashboard Controls")
    st.sidebar.write(f"**Logs:** `{LOG_DIR}`")

    log_files = _all_log_files()
    st.sidebar.metric("Log Files", len(log_files))

    risk_files: list[Path] = []
    try:
        risk_files = list(LOG_DIR.glob("risk_state*.json"))
    except OSError:
        pass
    st.sidebar.metric("Risk State Files", len(risk_files))

    if log_files:
        newest = log_files[0]
        try:
            size_kb = newest.stat().st_size / 1024
            st.sidebar.caption(f"Newest log: `{newest.name}` ({size_kb:.0f} KB)")
        except OSError:
            st.sidebar.caption(f"Newest log: `{newest.name}`")
    else:
        st.sidebar.warning("No log files found")

    st.sidebar.divider()
    st.sidebar.caption("🔧 **Read-only** — this dashboard never places orders.")


# ── main render ──────────────────────────────────────────────────────────────


def main() -> None:
    render_sidebar()

    # Auto-refresh every 10 seconds
    st_autorefresh = None
    try:
        from streamlit_autorefresh import st_autorefresh
    except ImportError:
        pass

    if st_autorefresh is not None:
        st_autorefresh(interval=10_000, key="dash_autorefresh")
    else:
        # Native fallback — MetaContainer <meta http-equiv="refresh">
        st.markdown(
            '<meta http-equiv="refresh" content="10">',
            unsafe_allow_html=True,
        )

    # ── read all data up front ───────────────────────────────────────────────
    all_lines = _read_all_log_lines()

    # ── title ────────────────────────────────────────────────────────────────
    st.title("📈 NAS100 Trading OS")
    st.caption("Read-only monitoring dashboard — auto-refreshes every 10 seconds.")

    # ── health cards ─────────────────────────────────────────────────────────
    latest_ts = _latest_timestamp(all_lines)
    latest_ses = _latest_session(all_lines)
    latest_eq = _latest_equity(all_lines)
    latest_risk = _latest_risk_scale(all_lines)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("🕐 Latest Log", latest_ts)
    with c2:
        st.metric("🎯 Latest Session", latest_ses)
    with c3:
        st.metric("💰 Latest Equity", latest_eq)
    with c4:
        st.metric("⚖️ Risk Scale", latest_risk)

    st.divider()

    # ── risk state table ─────────────────────────────────────────────────────
    st.subheader("📊 Risk State")
    risk_rows = _risk_state_rows()
    if risk_rows:
        st.dataframe(risk_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No risk state files found in `logs/`.")

    st.divider()

    # ── recent orders + fills side by side ───────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📤 Recent Orders")
        orders = _recent_orders(all_lines, limit=20)
        if orders:
            st.dataframe(orders, use_container_width=True, hide_index=True)
        else:
            st.info("No order events found in logs.")

    with col_right:
        st.subheader("✅ Recent Fills")
        fills = _recent_fills(all_lines, limit=20)
        if fills:
            st.dataframe(fills, use_container_width=True, hide_index=True)
        else:
            st.info("No fill events found in logs.")

    st.divider()

    # ── warnings / errors ────────────────────────────────────────────────────
    st.subheader("⚠️ Warnings & Errors")
    warns = _warnings_errors(all_lines, limit=30)
    if warns:
        st.dataframe(warns, use_container_width=True, hide_index=True)
    else:
        st.success("No warnings or errors in logs 🎉")

    st.divider()

    # ── last 100 log lines (expandable) ──────────────────────────────────────
    with st.expander("📜 Last 100 Log Lines", expanded=False):
        trader_log = LOG_DIR / "trader.log"
        last_100 = _tail_lines(trader_log, 100) if trader_log.is_file() else []
        if last_100:
            st.code("\n".join(last_100), language="log")
        else:
            # Fallback: show whatever log files exist
            any_shown = False
            for lf in _all_log_files()[:3]:
                lines = _tail_lines(lf, 50)
                if lines:
                    st.caption(f"`{lf.name}` (last 50 lines)")
                    st.code("\n".join(lines), language="log")
                    any_shown = True
            if not any_shown:
                st.warning("No log files found in `logs/`.")

    st.caption("— Dashboard loaded successfully —")


if __name__ == "__main__":
    main()
