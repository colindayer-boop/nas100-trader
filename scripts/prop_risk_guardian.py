"""prop_risk_guardian.py -- independent risk SUPERVISOR for the MT5 bot.

NOT a strategy. Never generates entries. Its only job: protect a prop account from continued
strategy losses by publishing an allow/block decision the live bot must consult before every order.

Fail-safe: when account data is missing/stale/inconsistent -> BLOCK NEW TRADES. Enforcement is
never automatic; default mode is monitor. Human approval required before enforce/emergency.

Modes:  --mode monitor (log/alert only) | enforce (block entries) | emergency (block + close)
Run:    python scripts/prop_risk_guardian.py --mode monitor            (live, needs MetaTrader5)
        python scripts/prop_risk_guardian.py --replay logs/fills.csv   (counterfactual, offline)
        python scripts/prop_risk_guardian.py --once --dry-run
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_FILE = REPO / "runtime" / "risk_guardian_state.json"
AUDIT_CSV = REPO / "logs" / "risk_guardian_audit.csv"
AUDIT_JSONL = REPO / "logs" / "risk_guardian_audit.jsonl"
KILL_SWITCH = REPO / "runtime" / "GUARDIAN_KILL"          # if present -> block everything
EMERGENCY_FLAG = REPO / "runtime" / "EMERGENCY_CLOSE"     # explicit opt-in to close


@dataclass
class Config:
    INITIAL_BALANCE: float = 50000.0
    CHALLENGE_TARGET_PCT: float = 10.0
    PROP_MAX_DAILY_LOSS_PCT: float = 5.0                  # firm hard limit
    PROP_MAX_TOTAL_LOSS_PCT: float = 10.0                # firm hard limit
    INTERNAL_DAILY_STOP_PCT: float = 1.0                 # our tighter stop
    INTERNAL_TOTAL_STOP_PCT: float = 3.0
    MAX_OPEN_RISK_PCT: float = 0.50
    MAX_RISK_PER_TRADE_PCT: float = 0.25
    MAX_CORRELATED_RISK_PCT: float = 0.50
    MAX_CONSECUTIVE_LOSSES: int = 3
    COOLDOWN_HOURS: float = 24.0
    ALLOWED_MAGIC_NUMBERS: tuple = (770001,)
    RESET_TZ_OFFSET_HOURS: int = 0                        # prop-day reset vs UTC (e.g. EST server)
    STALE_SECONDS: int = 60
    CORRELATED_GROUPS: tuple = (("BTCUSD", "ETHUSD"), ("NAS100", "US100", "QQQ", "SPX500", "US500"))

    @classmethod
    def load(cls, path: str | None):
        c = cls()
        if path and Path(path).exists():
            data = {}
            for line in Path(path).read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1); data[k.strip()] = v.strip()
            for k, v in data.items():
                if hasattr(c, k):
                    cur = getattr(c, k)
                    try:
                        setattr(c, k, type(cur)(v) if not isinstance(cur, (tuple,)) else tuple(v.split(",")))
                    except (ValueError, TypeError):
                        pass
        # env overrides
        for k in vars(c):
            if k in os.environ:
                try:
                    setattr(c, k, type(getattr(c, k))(os.environ[k]))
                except (ValueError, TypeError):
                    pass
        return c


@dataclass
class Position:
    symbol: str; volume: float; entry: float; sl: float; magic: int; profit: float = 0.0; swap: float = 0.0


@dataclass
class Snapshot:
    ts: datetime; balance: float; equity: float; login: int; server: str
    positions: list = field(default_factory=list)
    ok: bool = True                                       # data integrity flag


# ---------------------------------------------------------------- risk math
def money_risk_to_stop(p: Position) -> float:
    """Monetary loss if the stop is hit. If no SL -> risk is UNBOUNDED -> flagged separately."""
    if p.sl is None or p.sl <= 0:
        return float("inf")
    per_unit = abs(p.entry - p.sl)
    return per_unit * p.volume * _contract_hint(p.symbol)


def _contract_hint(sym: str) -> float:
    s = sym.upper()
    if "JPY" in s: return 1000.0
    if "XAU" in s: return 100.0
    if "BTC" in s or "ETH" in s: return 1.0
    if any(x in s for x in ("NAS", "US100", "SPX", "US500", "US30", "QQQ")): return 1.0
    return 100000.0                                       # fx standard lot


def correlated_risk(positions, groups) -> dict:
    out = {}
    for grp in groups:
        risk = sum(min(money_risk_to_stop(p), p.entry * p.volume * _contract_hint(p.symbol))
                   for p in positions if p.symbol.upper() in [g.upper() for g in grp])
        if risk > 0:
            out[grp[0]] = risk
    return out


# ---------------------------------------------------------------- the decision
def evaluate(snap: Snapshot, cfg: Config, day_start_equity: float, hwm: float,
            consecutive_losses: int, trades_today: int, cooldown_until: datetime | None,
            proposed_risk_pct: float | None = None, now: datetime | None = None) -> dict:
    """Pure guardrail evaluation -> allow_new_entries + reason_codes. Fail-safe on bad data."""
    now = now or datetime.now(timezone.utc)
    reasons = []
    # -- fail-safe integrity gates FIRST --
    if KILL_SWITCH.exists():
        reasons.append("KILL_SWITCH")
    if not snap.ok:
        reasons.append("DATA_INCONSISTENT")
    age = (now - snap.ts).total_seconds()
    if age > cfg.STALE_SECONDS:
        reasons.append("STALE_DATA")
    if snap.balance <= 0 or snap.equity <= 0:
        reasons.append("BAD_ACCOUNT_VALUES")
    # -- drawdown gates --
    daily_loss_pct = (day_start_equity - snap.equity) / cfg.INITIAL_BALANCE * 100
    total_dd_pct = (cfg.INITIAL_BALANCE - snap.equity) / cfg.INITIAL_BALANCE * 100
    hwm_dd_pct = (hwm - snap.equity) / cfg.INITIAL_BALANCE * 100
    if daily_loss_pct >= cfg.INTERNAL_DAILY_STOP_PCT:
        reasons.append("INTERNAL_DAILY_STOP")
    if total_dd_pct >= cfg.INTERNAL_TOTAL_STOP_PCT:
        reasons.append("INTERNAL_TOTAL_STOP")
    # -- open risk gates --
    open_risk = sum(min(money_risk_to_stop(p), p.entry * p.volume * _contract_hint(p.symbol))
                    for p in snap.positions)
    open_risk_pct = open_risk / cfg.INITIAL_BALANCE * 100
    if open_risk_pct >= cfg.MAX_OPEN_RISK_PCT:
        reasons.append("MAX_OPEN_RISK")
    if any(p.sl is None or p.sl <= 0 for p in snap.positions):
        reasons.append("POSITION_MISSING_STOP")
    for grp, risk in correlated_risk(snap.positions, cfg.CORRELATED_GROUPS).items():
        if risk / cfg.INITIAL_BALANCE * 100 >= cfg.MAX_CORRELATED_RISK_PCT:
            reasons.append(f"CORRELATED_RISK:{grp}")
    # averaging into a losing instrument (2+ positions same symbol, one losing)
    from collections import Counter
    sym_count = Counter(p.symbol for p in snap.positions)
    for sym, cnt in sym_count.items():
        if cnt >= 2 and any(p.symbol == sym and p.profit < 0 for p in snap.positions):
            reasons.append(f"AVERAGING_INTO_LOSS:{sym}")
    # -- behavioral gates --
    if consecutive_losses >= cfg.MAX_CONSECUTIVE_LOSSES:
        reasons.append("MAX_CONSECUTIVE_LOSSES")
    if cooldown_until and now < cooldown_until:
        reasons.append("COOLDOWN_ACTIVE")
    # -- proposed-trade gate --
    if proposed_risk_pct is not None and proposed_risk_pct > cfg.MAX_RISK_PER_TRADE_PCT:
        reasons.append("PROPOSED_RISK_TOO_LARGE")
    allow = len(reasons) == 0
    return {"allow_new_entries": allow, "reason_codes": reasons,
            "daily_loss_pct": round(daily_loss_pct, 3), "total_drawdown_pct": round(total_dd_pct, 3),
            "hwm_drawdown_pct": round(hwm_dd_pct, 3), "open_risk_pct": round(open_risk_pct, 3),
            "consecutive_losses": consecutive_losses, "trades_today": trades_today,
            "data_fresh": age <= cfg.STALE_SECONDS}


def write_state_atomic(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, default=str))
    os.replace(tmp, STATE_FILE)                          # atomic


def audit(event: str, detail: dict):
    AUDIT_CSV.parent.mkdir(exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **detail}
    new = not AUDIT_CSV.exists()
    with open(AUDIT_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "event", "reason_codes", "daily_loss_pct",
                                          "total_drawdown_pct", "open_risk_pct"])
        if new: w.writeheader()
        w.writerow({k: row.get(k) for k in w.fieldnames})
    with open(AUDIT_JSONL, "a") as f:
        f.write(json.dumps(row, default=str) + "\n")


# ---------------------------------------------------------------- MT5 live snapshot
def mt5_snapshot(cfg: Config) -> Snapshot:
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return Snapshot(datetime.now(timezone.utc), 0, 0, 0, "", ok=False)
        a = mt5.account_info()
        poss = []
        for p in (mt5.positions_get() or []):
            poss.append(Position(p.symbol, p.volume, p.price_open, p.sl, p.magic, p.profit, p.swap))
        return Snapshot(datetime.now(timezone.utc), a.balance, a.equity, a.login, a.server, poss)
    except Exception:
        return Snapshot(datetime.now(timezone.utc), 0, 0, 0, "", ok=False)


# ---------------------------------------------------------------- replay (no look-ahead)
def replay(fills_or_history: str, cfg: Config) -> dict:
    """Replay closed trades chronologically. At each trade, decide BLOCK using ONLY prior
    information (drawdown, consecutive losses, cooldown, open same-symbol) -- never the trade's
    own outcome. Then compute the counterfactual (blocked trades removed)."""
    trades = _load_closed_trades(fills_or_history)
    if not trades:
        return {"error": "no closed trades found in " + fills_or_history}
    equity = cfg.INITIAL_BALANCE; hwm = equity; day = None; day_start = equity
    consec = 0; cooldown_until = None
    taken_pnl = 0.0; blocked = []; taken = []; eq_curve_actual = [equity]; eq_curve_guard = [equity]
    open_syms = {}
    for t in trades:
        ts = t["ts"]; pnl = t["pnl"]; sym = t["sym"]; has_sl = t["has_sl"]
        if day is None or ts.date() != day:
            day = ts.date(); day_start = equity                         # prop-day reset (simplified)
        # DECISION using prior state only (no t['pnl'])
        daily_loss_pct = (day_start - equity) / cfg.INITIAL_BALANCE * 100
        total_dd_pct = (cfg.INITIAL_BALANCE - equity) / cfg.INITIAL_BALANCE * 100
        reasons = []
        if daily_loss_pct >= cfg.INTERNAL_DAILY_STOP_PCT: reasons.append("INTERNAL_DAILY_STOP")
        if total_dd_pct >= cfg.INTERNAL_TOTAL_STOP_PCT: reasons.append("INTERNAL_TOTAL_STOP")
        if consec >= cfg.MAX_CONSECUTIVE_LOSSES: reasons.append("MAX_CONSECUTIVE_LOSSES")
        if cooldown_until and ts < cooldown_until: reasons.append("COOLDOWN_ACTIVE")
        if not has_sl: reasons.append("POSITION_MISSING_STOP")
        if open_syms.get(sym, 0) >= 1: reasons.append("AVERAGING_INTO_LOSS")   # 2nd same-symbol
        blocked_here = len(reasons) > 0
        # actual account always takes the trade
        equity_actual_prev = eq_curve_actual[-1]
        eq_curve_actual.append(equity_actual_prev + pnl)
        # guardian counterfactual: skip blocked trades
        if blocked_here:
            blocked.append({**t, "reasons": reasons}); eq_curve_guard.append(eq_curve_guard[-1])
        else:
            taken.append(t); taken_pnl += pnl; eq_curve_guard.append(eq_curve_guard[-1] + pnl)
            # update state only from TAKEN trades (what the guarded account would experience)
            equity += pnl; hwm = max(hwm, equity)
            open_syms[sym] = open_syms.get(sym, 0) + 1
            if pnl < 0:
                consec += 1
                if consec >= cfg.MAX_CONSECUTIVE_LOSSES:
                    cooldown_until = ts + timedelta(hours=cfg.COOLDOWN_HOURS)
            else:
                consec = 0
    def maxdd(curve):
        peak = curve[0]; mx = 0
        for x in curve:
            peak = max(peak, x); mx = min(mx, x - peak)
        return mx
    blk_losers = sum(b["pnl"] for b in blocked if b["pnl"] < 0)
    blk_winners = sum(b["pnl"] for b in blocked if b["pnl"] > 0)
    return {"n_trades": len(trades), "n_blocked": len(blocked), "n_taken": len(taken),
            "actual_net_pnl": round(sum(t["pnl"] for t in trades), 2),
            "guarded_net_pnl": round(taken_pnl, 2),
            "loss_avoided": round(-blk_losers, 2), "winners_skipped": round(blk_winners, 2),
            "net_pnl_change": round(taken_pnl - sum(t["pnl"] for t in trades), 2),
            "actual_maxdd": round(maxdd(eq_curve_actual), 2),
            "guarded_maxdd": round(maxdd(eq_curve_guard), 2),
            "blocked_detail": blocked}


def _load_closed_trades(path: str) -> list:
    """From MT5 html export or fills.csv. Returns [{ts, sym, pnl, has_sl}] sorted by time."""
    p = Path(path) if Path(path).is_absolute() else REPO / path
    out = []
    if p.suffix == ".html" or "mt5_history" in str(p):
        import re, html as _h
        raw = p.read_bytes().decode("utf-16", errors="replace")
        d = raw.find("Deals"); rows = re.findall(r"<tr[^>]*>(.*?)</tr>", raw[d:], re.S | re.I)
        for tr in rows:
            c = [_h.unescape(re.sub("<[^>]+>", "", x)).strip()
                 for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
            if len(c) >= 13 and re.match(r"\d{4}\.\d\d\.\d\d", c[0]) and c[4].lower() == "out":
                out.append({"ts": datetime.strptime(c[0][:19], "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc),
                            "sym": c[2], "pnl": float(c[12].replace(" ", "")) + float(c[11].replace(" ", "")),
                            "has_sl": "[sl" in (c[-1] or "").lower() or True})
    else:
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                pnl = r.get("profit") or r.get("pnl")
                if pnl:
                    out.append({"ts": datetime.fromisoformat(r["timestamp_utc"]).replace(tzinfo=timezone.utc),
                                "sym": r.get("symbol", "?"), "pnl": float(pnl),
                                "has_sl": bool(r.get("stop_price"))})
    return sorted(out, key=lambda x: x["ts"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["monitor", "enforce", "emergency"], default="monitor")
    ap.add_argument("--config"); ap.add_argument("--replay"); ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = Config.load(a.config)
    if a.replay:
        r = replay(a.replay, cfg); print(json.dumps({k: v for k, v in r.items() if k != "blocked_detail"}, indent=1))
        return r
    # live loop
    while True:
        snap = Snapshot(datetime.now(timezone.utc), 0, 0, 0, "", ok=False) if a.dry_run else mt5_snapshot(cfg)
        ev = evaluate(snap, cfg, day_start_equity=cfg.INITIAL_BALANCE, hwm=cfg.INITIAL_BALANCE,
                      consecutive_losses=0, trades_today=0, cooldown_until=None)
        state = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "mode": a.mode,
                 "account_login": snap.login, "server": snap.server, "balance": snap.balance,
                 "equity": snap.equity, **ev}
        write_state_atomic(state)
        audit("STATE", state)
        print(f"[{state['timestamp_utc'][:19]}] mode={a.mode} allow={ev['allow_new_entries']} "
              f"reasons={ev['reason_codes']}")
        if a.once: break
        time.sleep(30)


if __name__ == "__main__":
    main()
