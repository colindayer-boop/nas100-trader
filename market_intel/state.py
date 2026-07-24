"""state.py -- PHASE 701 market state classifier. Reads live MT5 bars, classifies session /
kill zone / structure / levels / volatility. Produces EVIDENCE ONLY. This module imports no broker
order functions and can never place a trade.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, time as dtime
import numpy as np, pandas as pd

# UTC session + ICT kill-zone windows (user-configurable)
SESSIONS = {"asia": (dtime(23, 0), dtime(7, 0)), "london": (dtime(7, 0), dtime(12, 0)),
            "newyork": (dtime(12, 0), dtime(21, 0))}
KILLZONES = {"london_kz": (dtime(6, 0), dtime(9, 0)), "ny_am_kz": (dtime(12, 0), dtime(15, 0)),
             "ny_pm_kz": (dtime(18, 0), dtime(20, 0)), "asia_kz": (dtime(23, 0), dtime(2, 0))}


def _in_window(now: dtime, start: dtime, end: dtime) -> bool:
    return (start <= now < end) if start < end else (now >= start or now < end)


def active_sessions(ts: datetime) -> dict:
    t = ts.timetz().replace(tzinfo=None)
    return {"session": next((k for k, (s, e) in SESSIONS.items() if _in_window(t, s, e)), "off"),
            "kill_zones": [k for k, (s, e) in KILLZONES.items() if _in_window(t, s, e)]}


@dataclass
class MarketState:
    symbol: str
    ts: str
    price: float
    session: str
    kill_zones: list
    trend: str
    trend_strength: float
    atr: float
    atr_pct: float
    volatility_regime: str
    prev_day_high: float
    prev_day_low: float
    prev_week_high: float
    prev_week_low: float
    opening_range_high: float
    opening_range_low: float
    vwap: float
    dist_vwap_pct: float
    liquidity_sweep: str          # "none" | "buyside" | "sellside"
    fvg: str                      # "none" | "bullish" | "bearish"
    order_block: str
    structure: str                # "bullish_bos" | "bearish_bos" | "range"
    nearest_resistance: float
    nearest_support: float

    def to_dict(self): return asdict(self)


def classify(symbol: str, m5: pd.DataFrame, d1: pd.DataFrame, now: datetime | None = None) -> MarketState:
    """m5: recent 5-min OHLC (index=datetime, UTC). d1: daily OHLC. Pure function -> testable."""
    now = now or (m5.index[-1].to_pydatetime().replace(tzinfo=timezone.utc))
    c, h, l = m5["close"], m5["high"], m5["low"]
    price = float(c.iloc[-1])

    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    atr_pct = float((tr.rolling(14).mean() / c).rolling(500, min_periods=50).rank(pct=True).iloc[-1])
    ema20, ema100 = c.ewm(span=20).mean(), c.ewm(span=100).mean()
    tstr = float(ema20.iloc[-1] / ema100.iloc[-1] - 1)
    trend = "up" if price > ema100.iloc[-1] and ema20.iloc[-1] > ema100.iloc[-1] else \
            "down" if price < ema100.iloc[-1] and ema20.iloc[-1] < ema100.iloc[-1] else "range"
    volq = float(c.pct_change().rolling(20).std().rolling(500, min_periods=50).rank(pct=True).iloc[-1])
    vol_regime = "high" if volq > 0.7 else "low" if volq < 0.3 else "normal"

    pdh = float(d1["high"].iloc[-2]) if len(d1) > 1 else np.nan
    pdl = float(d1["low"].iloc[-2]) if len(d1) > 1 else np.nan
    pwh = float(d1["high"].iloc[-6:-1].max()) if len(d1) > 6 else np.nan
    pwl = float(d1["low"].iloc[-6:-1].min()) if len(d1) > 6 else np.nan

    today = m5.index.normalize() == m5.index[-1].normalize()
    td = m5[today]
    orb = td.head(6)                                   # first 30 minutes
    orh = float(orb["high"].max()) if len(orb) else np.nan
    orl = float(orb["low"].min()) if len(orb) else np.nan
    tp = (td["high"] + td["low"] + td["close"]) / 3
    vwap = float(tp.mean()) if len(td) else price

    sweep = "none"
    if not np.isnan(pdh) and float(h.iloc[-1]) > pdh and price < pdh: sweep = "buyside"
    elif not np.isnan(pdl) and float(l.iloc[-1]) < pdl and price > pdl: sweep = "sellside"

    fvg = "none"
    if len(m5) >= 3:
        if float(l.iloc[-1]) > float(h.iloc[-3]): fvg = "bullish"
        elif float(h.iloc[-1]) < float(l.iloc[-3]): fvg = "bearish"

    ob = "none"
    if len(m5) >= 4:
        body = (m5["close"] - m5["open"]).iloc[-3:]
        if body.iloc[0] < 0 and body.iloc[1] > 0 and body.iloc[2] > 0: ob = "bullish_ob"
        elif body.iloc[0] > 0 and body.iloc[1] < 0 and body.iloc[2] < 0: ob = "bearish_ob"

    sw_hi = float(h.rolling(20).max().iloc[-1]); sw_lo = float(l.rolling(20).min().iloc[-1])
    structure = "bullish_bos" if price >= sw_hi else "bearish_bos" if price <= sw_lo else "range"

    ss = active_sessions(now)
    return MarketState(symbol=symbol, ts=now.isoformat(), price=price, session=ss["session"],
        kill_zones=ss["kill_zones"], trend=trend, trend_strength=round(tstr, 5), atr=round(atr, 5),
        atr_pct=round(atr_pct, 3) if not np.isnan(atr_pct) else 0.0, volatility_regime=vol_regime,
        prev_day_high=pdh, prev_day_low=pdl, prev_week_high=pwh, prev_week_low=pwl,
        opening_range_high=orh, opening_range_low=orl, vwap=round(vwap, 5),
        dist_vwap_pct=round((price / vwap - 1) if vwap else 0.0, 5),
        liquidity_sweep=sweep, fvg=fvg, order_block=ob, structure=structure,
        nearest_resistance=sw_hi, nearest_support=sw_lo)
