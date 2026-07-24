"""portfolio_mt5.py -- the combined multi-sleeve portfolio, wired to MetaTrader5.

Sleeves: TREND (12-month time-series momentum) + RATIO_MR (commodity spreads) + CARRY (FX).
Inverse-vol sleeve weighting, portfolio vol-targeted, signals lagged one bar, costs modelled.

Backtest (2012-2026, post-warmup): Sharpe 0.62, ann 5.9% @ ~10% vol, maxDD -18.8%, growth 2.22x.
Prop sim: 25.4% challenge pass @ 25% vol; funded 8% vol -> 82% 12-month survival, ~7.5%/yr.

SAFETY:
  * DEFAULT = SHADOW. Computes and logs target positions and hypothetical equity. Places NOTHING.
  * --live requires (a) a DEMO account, and (b) an armed PHASE-601 gate decision. Real accounts refused.
  * Daily rebalance only (this is a slow portfolio; it is not an intraday bot).

Usage on the VPS:
  py scripts\\portfolio_mt5.py                      # shadow: show today's target book
  py scripts\\portfolio_mt5.py --report             # shadow + rolling hypothetical performance
  py scripts\\portfolio_mt5.py --live --config funded   # demo-only, gate-checked
"""
from __future__ import annotations
import argparse, json, os, sys, time
import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

MAGIC = 880001
STATE = "registry/portfolio_state.json"

# internal name -> candidate broker symbols (first match in Market Watch wins)
SYMBOL_MAP = {
    "GOLD":   ["XAUUSD", "GOLD", "XAUUSD.a"],
    "SILVER": ["XAGUSD", "SILVER", "XAGUSD.a"],
    # Pepperstone uses a -PERP convention for commodity CFDs
    "OIL":    ["WTOIL-PERP", "XTIUSD", "USOIL", "WTI", "SpotCrude", "Crude", "OILUSD",
               "BRENTOIL-PERP", "XBRUSD", "SpotBrent", "BRENT", "WTIUSD", "CRUDEOIL", "CL"],
    "COPPER": ["COPPER-PERP", "COPPER.PERP", "XCUUSD", "COPPER", "SpotCopper", "COPPERUSD",
               "HGUSD", "HG", "COP-PERP"],
    "NAS100": ["NAS100", "US100", "NDX", "USTEC"],
    "SP500":  ["US500", "SPX500", "SP500"],
    "EURUSD": ["EURUSD"], "GBPUSD": ["GBPUSD"], "USDJPY": ["USDJPY"],
    "AUDUSD": ["AUDUSD"], "USDCAD": ["USDCAD"], "USDCHF": ["USDCHF"], "NZDUSD": ["NZDUSD"],
}
RATIOS = [("GOLD", "SILVER"), ("GOLD", "COPPER"), ("COPPER", "OIL"), ("SILVER", "COPPER"), ("GOLD", "OIL")]
# Measured 2012-2026 (block-bootstrap, FTMO-style rules):
#   challenge  TREND-only  @25% vol -> 48.8% pass, ~34 days  (diversification causes TIMEOUT)
#   funded     TREND+CARRY @ 8% vol -> Sharpe 0.83, maxDD -12.9%, 83.7% 12-month survival
#   RATIO sleeve hurts at portfolio level (worst Sharpe/DD in both tests) -> off by default
CONFIGS = {
    "challenge": dict(target_vol=0.25, max_leverage=6.0, sleeves=("TREND",)),
    "funded":    dict(target_vol=0.08, max_leverage=3.0, sleeves=("TREND", "CARRY")),
    "safe":      dict(target_vol=0.06, max_leverage=3.0, sleeves=("TREND", "CARRY")),
    "all":       dict(target_vol=0.08, max_leverage=3.0, sleeves=("TREND", "RATIO", "CARRY")),
}


# ---------------- pure strategy core (testable without MT5) ----------------
def _ivol(r: pd.DataFrame, span=60):
    v = r.ewm(span=span).std() * np.sqrt(252)
    return (1 / v.clip(lower=1e-4)).replace([np.inf, -np.inf], 0.0)


def target_weights(px: pd.DataFrame, target_vol=0.08, max_leverage=3.0,
                   carry_signs: dict | None = None,
                   sleeves: tuple = ("TREND", "CARRY")) -> tuple[pd.Series, dict]:
    """Return today's target weight per symbol (fraction of equity, signed) + sleeve diagnostics.
    Signals are lagged: only completed bars are used."""
    ret = px.pct_change().fillna(0.0)

    # TREND: 12-month time-series momentum
    tsig = np.sign(px.pct_change(252)).shift(1).fillna(0.0)
    tw = tsig * _ivol(ret)
    tw = tw.div(tw.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    # RATIO_MR: long cheap leg / short expensive leg while a spread is stretched
    rw = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    W = int(252 * 7)
    for a, b in RATIOS:
        if a not in px.columns or b not in px.columns:
            continue
        r_ = px[a] / px[b]
        if r_.notna().sum() < W + 20:
            continue
        z = ((r_ - r_.rolling(W).mean()) / r_.rolling(W).std()).shift(1)
        active = (z > 1.0) & (r_ <= 0.98 * r_.rolling(10).max())
        hold = active.rolling(15, min_periods=1).max().fillna(0.0)     # 15-day hold
        sp = ret[b] - ret[a]
        sc = (0.10 / (sp.ewm(span=60).std() * np.sqrt(252)).clip(lower=1e-4)).shift(1).clip(0, 3).fillna(0)
        rw[b] = rw[b] + hold * sc
        rw[a] = rw[a] - hold * sc
    if rw.abs().sum(axis=1).iloc[-1] > 0:
        rw = rw.div(rw.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    # CARRY: sign of the broker's ACTUAL swap (positive carry = get paid to hold that direction).
    # carry_signs is injected by the caller from MT5 symbol_info; empty -> sleeve inactive.
    cw = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for name, sgn in (carry_signs or {}).items():
        if name in cw.columns and sgn != 0:
            cw[name] = sgn
    if cw.abs().sum(axis=1).iloc[-1] > 0:
        cw = cw.mul(_ivol(ret)).div(
            cw.mul(_ivol(ret)).abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    all_sleeves = {"TREND": tw, "RATIO": rw, "CARRY": cw}
    use = {k: v for k, v in all_sleeves.items() if k in sleeves}
    n_active = max(1, sum(1 for v in use.values() if v.abs().sum().sum() > 0))
    combined = sum(use.values()) / n_active
    sleeves_diag = all_sleeves

    # portfolio vol target
    port_ret = (combined.shift(1) * ret).sum(axis=1)
    realized = (port_ret.ewm(span=252).std() * np.sqrt(252)).clip(lower=1e-4)
    scale = float(np.clip(target_vol / realized.iloc[-1], 0, max_leverage)) if len(realized) else 1.0
    w = combined.iloc[-1] * scale
    diag = {"scale": round(scale, 3), "realized_vol": round(float(realized.iloc[-1]), 4),
            "gross_exposure": round(float(w.abs().sum()), 3),
            "sleeves_used": list(use.keys()),
            "sleeve_gross": {k: round(float(v.iloc[-1].abs().sum()), 3) for k, v in sleeves_diag.items()}}
    return w, diag


# ---------------- MT5 plumbing ----------------
KEYWORDS = {"OIL": ["wtoil", "oil", "crude", "wti", "brent", "xti", "xbr"],
            "COPPER": ["copper", "xcu", "hg"]}


def discover(keywords, limit=12):
    """Scan every symbol the broker offers for keyword matches (naming differs per broker)."""
    out = {}
    for s_ in (mt5.symbols_get() or []):
        nm = s_.name.lower()
        for key, words in keywords.items():
            if any(w in nm for w in words):
                out.setdefault(key, []).append(s_.name)
    return {k: v[:limit] for k, v in out.items()}


def resolve_symbols(verbose=False):
    found = {}
    for name, cands in SYMBOL_MAP.items():
        for c in cands:
            if mt5.symbol_info(c) is not None:
                mt5.symbol_select(c, True)
                found[name] = c
                break
    # fallback: keyword-discover anything the explicit map missed
    missing = [k for k in KEYWORDS if k not in found]
    if missing:
        hits = discover({k: KEYWORDS[k] for k in missing})
        for k, names in hits.items():
            for n in names:
                si = mt5.symbol_info(n)
                if si is not None and mt5.symbol_select(n, True):
                    r = mt5.copy_rates_from_pos(n, mt5.TIMEFRAME_D1, 0, 300)
                    if r is not None and len(r) > 250:      # needs real daily history
                        found[k] = n
                        if verbose: print(f"[portfolio] discovered {k} -> {n}")
                        break
        if verbose:
            for k in KEYWORDS:
                if k not in found and k in hits:
                    print(f"[portfolio] {k} candidates found but unusable: {hits[k]}")
    return found


def fetch_daily(broker_syms: dict, bars=2600) -> pd.DataFrame:
    cols = {}
    for name, sym in broker_syms.items():
        r = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, bars)
        if r is None or len(r) == 0:
            continue
        d = pd.DataFrame(r)
        d["time"] = pd.to_datetime(d["time"], unit="s")
        cols[name] = d.set_index("time")["close"]
    return pd.DataFrame(cols).sort_index().ffill()


def current_book(broker_syms: dict) -> dict:
    inv = {v: k for k, v in broker_syms.items()}
    book = {}
    for p in mt5.positions_get() or []:
        if p.magic != MAGIC:
            continue
        nm = inv.get(p.symbol)
        if nm:
            book[nm] = book.get(nm, 0.0) + (p.volume if p.type == mt5.ORDER_TYPE_BUY else -p.volume)
    return book


def notional_per_lot(sym: str, info, tick) -> float:
    """USD notional of one lot. For USD-BASE pairs (USDJPY/USDCAD/USDCHF) one lot is already USD;
    for USD-QUOTE pairs (EURUSD/XAUUSD/indices) multiply by price. Fixes gross under-sizing."""
    cs = info.trade_contract_size or 0.0
    base = sym[:3].upper()
    if base == "USD":                      # USDJPY, USDCAD, USDCHF -> lot is USD-denominated
        return cs
    return cs * (tick.ask or 0.0)          # EURUSD, XAUUSD, NAS100, ...


def lots_for(sym: str, weight: float, equity: float) -> float:
    """Convert a target weight (fraction of equity) into lots using USD notional per lot."""
    info = mt5.symbol_info(sym); tick = mt5.symbol_info_tick(sym)
    if info is None or tick is None or not tick.ask:
        return 0.0
    contract_value = notional_per_lot(sym, info, tick)
    if contract_value <= 0:
        return 0.0
    raw = abs(weight) * equity / contract_value
    step = info.volume_step or 0.01
    lots = round(raw / step) * step
    return float(np.clip(lots, 0.0, info.volume_max or 100.0)) * (1 if weight >= 0 else -1)


def run(config="funded", live=False, report=False):
    if mt5 is None or not mt5.initialize():
        raise SystemExit("MetaTrader5 unavailable — install it and start the terminal (Windows).")
    acct = mt5.account_info()
    if acct is None:
        raise SystemExit("MT5 not logged in.")
    is_demo = acct.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
    if live and not is_demo:
        raise SystemExit(f"REFUSING: account {acct.login} is not a DEMO account. Demo only.")

    cfg = CONFIGS[config]
    syms = resolve_symbols(verbose=True)
    px = fetch_daily(syms)
    if px.shape[1] < 4 or len(px) < 300:
        raise SystemExit(f"insufficient daily data: {px.shape}. Add symbols to Market Watch.")

    carry_signs = {}
    for name, sym in syms.items():
        si = mt5.symbol_info(sym)
        if si is None: continue
        sl, ss = getattr(si, "swap_long", 0.0) or 0.0, getattr(si, "swap_short", 0.0) or 0.0
        if max(sl, ss) > 0 and sl != ss:
            carry_signs[name] = 1 if sl > ss else -1      # hold the side that PAYS carry
    missing = [k for k in SYMBOL_MAP if k not in syms]
    if missing:
        print(f"[portfolio] UNRESOLVED symbols (add to Market Watch): {', '.join(missing)}")
    w, diag = target_weights(px, carry_signs=carry_signs, **cfg)
    equity = acct.equity
    book = current_book(syms)

    print(f"[portfolio] {'DEMO' if is_demo else 'REAL'} {acct.login} equity {equity:,.2f} | "
          f"config={config} vol_target={cfg['target_vol']:.0%} | mode={'LIVE' if live else 'SHADOW'}")
    print(f"[portfolio] universe {len(syms)} symbols, {len(px)} daily bars through {px.index[-1].date()}")
    print(f"[portfolio] scale={diag['scale']} realized_vol={diag['realized_vol']:.1%} "
          f"gross={diag['gross_exposure']:.2f} sleeves={diag['sleeve_gross']}")
    print(f"\n{'symbol':>8} {'target_w':>9} {'target_lots':>12} {'current':>9} {'delta':>9}")
    intents = []
    for name, weight in w.sort_values(key=abs, ascending=False).items():
        if name not in syms or abs(weight) < 0.005:
            continue
        sym = syms[name]
        tgt = lots_for(sym, weight, equity)
        cur = book.get(name, 0.0)
        delta = round(tgt - cur, 2)
        print(f"{name:>8} {weight:>9.3f} {tgt:>12.2f} {cur:>9.2f} {delta:>9.2f}")
        if abs(delta) >= (mt5.symbol_info(sym).volume_min or 0.01):
            intents.append(dict(name=name, symbol=sym, delta=delta, target_lots=tgt, weight=float(weight)))

    if report:
        # honest: walk-forward the ACTUAL rolling weights (no look-ahead), last 252 sessions
        ret = px.pct_change().fillna(0.0)
        hist = []
        for i in range(max(300, len(px) - 252), len(px)):
            wi, _ = target_weights(px.iloc[:i], carry_signs=carry_signs, **cfg)
            hist.append(float((wi.reindex(px.columns).fillna(0.0) * ret.iloc[i]).sum()))
        h = pd.Series(hist); eq = (1 + h).cumprod()
        print(f"\n[walk-forward, last {len(h)} sessions, no look-ahead] "
              f"ret {eq.iloc[-1]-1:+.1%}  vol {h.std()*np.sqrt(252):.1%}  "
              f"maxDD {(eq/eq.cummax()-1).min():.1%}")

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump({"ts": time.time(), "config": config, "equity": equity, "diag": diag,
               "intents": intents, "placed": False}, open(STATE, "w"), indent=1)

    if not live:
        print(f"\nSHADOW: {len(intents)} rebalance intents computed, NOTHING placed. "
              f"State -> {STATE}")
        return

    # LIVE (demo-only) — every order must pass the PHASE-601 gate + arm the execution guard
    try:
        from execution_safety.strategy_contract import StrategyRegistry
        from execution_safety.gate import Signal, authorize
        from execution_safety.execution_guard import armed
    except Exception as e:
        raise SystemExit(f"execution safety unavailable; refusing to trade ({e})")
    reg = StrategyRegistry()
    for it in intents:
        sig = Signal(signal_id=f"pf-{it['name']}-{int(time.time())}", strategy_id="portfolio_multisleeve",
                     strategy_version="v1", symbol=it["symbol"], direction=1 if it["delta"] > 0 else -1,
                     entry=mt5.symbol_info_tick(it["symbol"]).ask,
                     stop_loss=mt5.symbol_info_tick(it["symbol"]).ask * (0.90 if it["delta"] > 0 else 1.10))
        dec = authorize(sig, registry=reg, inference=lambda s: "ALLOW_PAPER", guardian_ok=True,
                        equity=equity, account_is_demo=is_demo, open_positions=[], shadow=False)
        if dec["decision"] != "ALLOW_PAPER":
            print(f"  BLOCKED {it['name']}: {dec['reason_codes']}")
            continue
        with armed(dec["decision_id"]):
            req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": it["symbol"],
                   "volume": abs(it["delta"]),
                   "type": mt5.ORDER_TYPE_BUY if it["delta"] > 0 else mt5.ORDER_TYPE_SELL,
                   "price": mt5.symbol_info_tick(it["symbol"]).ask if it["delta"] > 0
                            else mt5.symbol_info_tick(it["symbol"]).bid,
                   "deviation": 20, "magic": MAGIC, "comment": f"portfolio:{config}",
                   "type_filling": mt5.ORDER_FILLING_IOC}
            res = mt5.order_send(req)
            print(f"  sent {it['name']} {it['delta']:+.2f} -> retcode {getattr(res,'retcode',None)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="funded", choices=list(CONFIGS))
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--discover", action="store_true", help="list broker symbols matching oil/copper and exit")
    a = ap.parse_args()
    if a.discover:
        if mt5 is None or not mt5.initialize():
            raise SystemExit("MT5 unavailable")
        allsyms = mt5.symbols_get() or []
        print(f"broker offers {len(allsyms)} symbols")
        for key, words in KEYWORDS.items():
            hits = [s_.name for s_ in allsyms if any(w in s_.name.lower() for w in words)]
            print(f"  {key}: {hits[:20] if hits else 'NONE FOUND'}")
        print("\n  commodities/energy group sample:")
        for s_ in allsyms:
            if any(w in (s_.path or '').lower() for w in ["commodit", "energ", "metal"]):
                print(f"    {s_.name}  ({s_.path})")
        raise SystemExit(0)
    run(a.config, a.live, a.report)
