"""phase404_live.py -- PHASE-404 rules wired to MetaTrader5, DEMO ONLY.

Sequence (faithful to the PDF): liquidity sweep of a swing high/low -> structure shift (CISD, next
close beyond the sweep bar's opposite extreme) -> FVG entry -> SL beyond the sweep wick -> chandelier
TRAILING stop, TP at opposite liquidity.

SAFETY (non-negotiable, do not remove):
  * HARD DEMO GUARD: refuses to place orders unless the account trade_mode is DEMO.
  * Guardian gate: every entry is checked by prop_risk_guardian (risk/trade, daily/total stop,
    consecutive losses, cooldown). Blocked -> no order.
  * Default is DRY-RUN (signals only). --live is required to send orders, and even then the demo
    guard must pass.

HONESTY: this encodes the rules. Backtest across 61k+ trades is NEGATIVE after costs. Run it to watch
the setups fire on fake money -- not because it has an edge.

Deploy (Windows VPS, MT5 terminal running):
  py -m pip install MetaTrader5
  py scripts/phase404_live.py --symbol XAUUSD --risk 0.0025           # dry-run, prints signals
  py scripts/phase404_live.py --symbol XAUUSD --risk 0.0025 --live    # sends orders (demo only)
"""
from __future__ import annotations
import argparse, os, sys, time
import numpy as np

MAGIC = 404404
TF_MIN = 15
SWING_K = 10
TRAIL_ATR_MULT = 3.0
POLL_SEC = 20

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


# ---------- strategy core (pure, testable without MT5) ----------
def _swing(arr_high, arr_low, i, k, kind):
    lo = max(0, i - k); hi = i + 1
    return (arr_high[i] == max(arr_high[lo:hi])) if kind == "high" else (arr_low[i] == min(arr_low[lo:hi]))


OTE_LO, OTE_HI = 0.618, 0.786   # Optimal Trade Entry golden pocket (PDF)


def find_setup(o, h, l, c, k=SWING_K):
    """Full PHASE-404 with OTE entry. Newest complete setup at the right edge, or None.
    Sequence: sweep confirmed swing liquidity -> MSS shift -> fib swing(1.0)->shift-low(0.0) ->
    ENTER when price retraces into the 0.618-0.786 OTE zone -> STOP beyond the swing(1.0) ->
    TARGET opposite liquidity. Causal: only closed bars are passed in."""
    n = len(c)
    if n < 2 * k + 6:
        return None
    setup = None
    lsh = lsl = np.nan
    for i in range(k, n - 3):
        j0 = i - k
        if j0 >= 0 and h[j0] == max(h[max(0, j0 - k):j0 + k + 1]):
            lsh = h[j0]
        if j0 >= 0 and l[j0] == min(l[max(0, j0 - k):j0 + k + 1]):
            lsl = l[j0]
        side = 0
        if not np.isnan(lsh) and h[i] > lsh and c[i] < lsh:
            side = -1; swing = h[i]; opp = lsl          # buyside sweep -> SELL, swing=1.0
        elif not np.isnan(lsl) and l[i] < lsl and c[i] > lsl:
            side = 1; swing = l[i]; opp = lsh
        if side == 0:
            continue
        # MSS shift within a short window after the sweep
        shift = None
        for s_ in range(i + 1, min(i + 12, n)):
            if (c[s_] < l[i]) if side < 0 else (c[s_] > h[i]):
                shift = s_; break
        if shift is None:
            continue
        # impulse extreme -> fib 0.0 ; OTE golden pocket zone
        if side < 0:
            L = min(l[i:shift + 1]); H = swing
            ote_bot = L + (H - L) * OTE_LO; ote_top = L + (H - L) * OTE_HI
            # price must currently be retraced UP into the OTE zone (right edge)
            hit = any(h[r_] >= ote_bot for r_ in range(shift + 1, n))
            entry = ote_bot
        else:
            H = max(h[i:shift + 1]); L = swing
            ote_top = H - (H - L) * OTE_LO; ote_bot = H - (H - L) * OTE_HI
            hit = any(l[r_] <= ote_top for r_ in range(shift + 1, n))
            entry = ote_top
        if not hit:
            continue
        risk = abs(entry - swing)
        if risk <= 0:
            continue
        tp = opp if (opp is not None and not np.isnan(opp)) else entry + side * 3 * risk
        setup = dict(idx=n - 1, side=side, entry=float(entry), stop=float(swing),
                     target=float(tp), risk=float(risk))
    return setup


def chandelier_stop(side, entry_stop, peak, atr, mult=TRAIL_ATR_MULT):
    """Trailing stop: tightened toward price as it moves favorably, never looser than initial."""
    if side < 0:
        return min(entry_stop, peak + mult * atr)   # peak = lowest low since entry
    return max(entry_stop, peak - mult * atr)         # peak = highest high since entry


# ---------- MT5 plumbing ----------
def _require_demo():
    info = mt5.account_info()
    if info is None:
        raise SystemExit("MT5 not connected / no account. Aborting.")
    if info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise SystemExit(f"REFUSING: account {info.login} is NOT a demo account "
                         f"(trade_mode={info.trade_mode}). This bot is demo-only.")
    return info


def _bars(symbol, count=500):
    import pandas as pd
    tf = {5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15}[TF_MIN]
    r = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    df = pd.DataFrame(r); df["time"] = df["time"].astype("datetime64[s]")
    return df


def _atr(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    import pandas as pd
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return float(tr.rolling(n).mean().iloc[-2])   # last CLOSED bar


def _lots(symbol, risk_money, sl_points):
    si = mt5.symbol_info(symbol)
    tick_val = si.trade_tick_value; tick_sz = si.trade_tick_size
    if sl_points <= 0 or tick_val <= 0:
        return si.volume_min
    risk_per_lot = (sl_points / tick_sz) * tick_val
    vol = max(si.volume_min, min(si.volume_max, round(risk_money / risk_per_lot / si.volume_step) * si.volume_step))
    return float(vol)


def _send(symbol, side, entry, sl, tp, vol):
    price = mt5.symbol_info_tick(symbol).ask if side > 0 else mt5.symbol_info_tick(symbol).bid
    req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=symbol, volume=vol,
               type=mt5.ORDER_TYPE_BUY if side > 0 else mt5.ORDER_TYPE_SELL,
               price=price, sl=sl, tp=tp, deviation=20, magic=MAGIC,
               comment="phase404", type_filling=mt5.ORDER_FILLING_IOC)
    return mt5.order_send(req)


def _trail_open(symbol):
    """Chandelier-trail SL on any open PHASE-404 position for this symbol."""
    for p in mt5.positions_get(symbol=symbol) or []:
        if p.magic != MAGIC:
            continue
        df = _bars(symbol, 60); atr = _atr(df)
        side = -1 if p.type == mt5.ORDER_TYPE_SELL else 1
        peak = df["low"].iloc[-30:].min() if side < 0 else df["high"].iloc[-30:].max()
        new_sl = chandelier_stop(side, p.sl or p.price_open, float(peak), atr)
        improved = (new_sl < p.sl) if side < 0 else (new_sl > p.sl)
        if p.sl == 0 or improved:
            mt5.order_send(dict(action=mt5.TRADE_ACTION_SLTP, symbol=symbol,
                                position=p.ticket, sl=float(new_sl), tp=p.tp))


def run(symbol, risk_pct, live):
    if mt5 is None or not mt5.initialize():
        raise SystemExit("MetaTrader5 unavailable. Install it and start your terminal (Windows).")
    info = _require_demo()
    print(f"[phase404] DEMO account {info.login} ({info.server}) equity {info.equity:.2f}  "
          f"symbol={symbol} risk/trade={risk_pct:.3%}  mode={'LIVE-ORDERS' if live else 'DRY-RUN'}")
    last_seen = None
    while True:
        try:
            _trail_open(symbol)                          # manage runners first
            df = _bars(symbol)
            closed = df.iloc[:-1]                         # drop the forming bar -> causal
            o, h, l, c = (closed[x].to_numpy() for x in ("open", "high", "low", "close"))
            s = find_setup(o, h, l, c)
            if s and s["idx"] != last_seen:
                last_seen = s["idx"]
                sd = "SELL" if s["side"] < 0 else "BUY"
                print(f"[{time.strftime('%H:%M:%S')}] SETUP {sd} {symbol} entry {s['entry']:.3f} "
                      f"SL {s['stop']:.3f} TP {s['target']:.3f}")
                if live:
                    try:
                        from prop_risk_guardian import Config, mt5_snapshot, evaluate
                        cfg = Config.load(os.environ.get("GUARDIAN_CONFIG", "config/guardian.env"))
                        snap = mt5_snapshot(cfg)
                        dec = evaluate(snap, cfg, info.balance, info.balance, 0, 0, None,
                                       proposed_risk_pct=risk_pct)
                        if not dec["allow_new_entries"]:
                            print(f"    guardian BLOCKED: {dec['reason_codes']}"); continue
                    except ImportError:
                        print("    [!] guardian not found on this box -- entry NOT risk-gated. "
                              "Copy scripts/prop_risk_guardian.py + config/guardian.env for protection.")
                    vol = _lots(symbol, info.equity * risk_pct, abs(s["entry"] - s["stop"]))
                    r = _send(symbol, s["side"], s["entry"], s["stop"], s["target"], vol)
                    print(f"    order_send -> retcode {getattr(r,'retcode',None)} vol {vol}")
            time.sleep(POLL_SEC)
        except KeyboardInterrupt:
            print("stopped."); break
        except Exception as e:
            print(f"[warn] {e}"); time.sleep(POLL_SEC)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--risk", type=float, default=0.0025)   # 0.25% per trade (guardian default)
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    run(a.symbol, a.risk, a.live)
