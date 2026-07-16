"""emergency_protection.py -- R1: broker-side catastrophe floor for BTCTREND.

A fixed-percentage emergency stop attached to every BTCTREND position so the position is
protected even if Python, MT5, the VPS, the scheduler, or the network dies. This is a
catastrophe FLOOR, not an exit: the normal Donchian 20/10 trend exit is unchanged.

Policy (evidence-selected, research-lab experiments/r1_emergency_stop, 2019-2026 BTC):
  fixed 20% below the rebalance price, ratcheted upward at each daily run, never loosened.
  ATR-multiple floors were REJECTED: 3-6x ATR20 fire 3.6-6.9x/yr (62-94% premature,
  CAGR -1 to -9pts); the 20% floor is statistically transparent (identical CAGR/Sharpe/
  MaxDD/challenge pass-rate, 3 hits in 7.5y -- all genuine crashes) while capping the
  dead-bot giveback at -20% vs -25.9% observed unmanaged. Fixed %% also needs no
  volatility input -> no NaN-ATR failure mode.

Never optimized. Changing EMERGENCY_STOP_PCT requires re-running the evidence study.
"""
import logging
import math

logger = logging.getLogger("trader")

EMERGENCY_STOP_PCT = 0.20   # catastrophe floor distance -- evidence-selected, NOT tunable


def emergency_floor(price, side="long", pct=EMERGENCY_STOP_PCT):
    """Emergency SL level for a position at `price`. Raises on invalid input rather than
    ever returning a bogus protection level (fail safe = fail loud)."""
    if price is None or not math.isfinite(float(price)) or float(price) <= 0:
        raise ValueError(f"emergency_floor: invalid price {price!r}")
    if not (0.0 < pct < 1.0):
        raise ValueError(f"emergency_floor: invalid pct {pct!r}")
    price = float(price)
    return price * (1 - pct) if side == "long" else price * (1 + pct)


def needed_sl(current_sl, floor, side="long"):
    """The SL to set, or None if the existing stop is already at least as protective.
    NEVER loosens: for a long, only ever raises the SL; for a short, only lowers it."""
    have = float(current_sl or 0.0)
    if have == 0.0:
        return floor                       # naked -> protect
    if side == "long":
        return floor if floor > have else None
    return floor if floor < have else None


def ensure_btc_protection(broker, symbol="BTC", pct=EMERGENCY_STOP_PCT):
    """Repair path: attach/ratchet the emergency floor on any open MT5 position for
    `symbol` that is naked or has a looser stop. Verifies broker acknowledgement.

    Returns {"checked": n, "repaired": n, "failed": n, "skipped_tighter": n}.
    No-op (all zeros) when the broker has no MT5 handle (dry-run/paper broker).
    """
    out = {"checked": 0, "repaired": 0, "failed": 0, "skipped_tighter": 0}
    m = getattr(broker, "_mt5", None) or getattr(getattr(broker, "_b", None), "_mt5", None)
    if m is None:
        logger.info("ensure_btc_protection: no MT5 handle (dry-run/paper) -- skipping")
        return out
    sym = broker.SYMBOL_MAP.get(symbol, symbol) if getattr(broker, "SYMBOL_MAP", None) else symbol
    positions = m.positions_get(symbol=sym) or []
    for p in positions:
        out["checked"] += 1
        side = "long" if p.type == m.POSITION_TYPE_BUY else "short"
        tick = m.symbol_info_tick(sym)
        px = tick.bid if side == "long" else tick.ask
        try:
            floor = emergency_floor(px, side, pct)
        except ValueError as e:
            logger.error(f"PROTECTION FAIL {sym} #{p.ticket}: {e}")
            out["failed"] += 1
            continue
        sl = needed_sl(getattr(p, "sl", 0.0), floor, side)
        if sl is None:
            out["skipped_tighter"] += 1
            continue
        # clamp to the symbol's minimum stop distance (same convention as mt5_broker)
        info = m.symbol_info(sym)
        pt = getattr(info, "point", 0.0) or 0.0
        min_dist = (getattr(info, "trade_stops_level", 0) or 0) * pt
        if min_dist:
            sl = min(sl, px - min_dist) if side == "long" else max(sl, px + min_dist)
        req = {"action": m.TRADE_ACTION_SLTP, "position": p.ticket, "symbol": sym,
               "sl": float(sl), "tp": float(getattr(p, "tp", 0.0) or 0.0)}
        res = m.order_send(req)
        ok = res is not None and res.retcode == m.TRADE_RETCODE_DONE
        if ok:
            logger.info(f"PROTECTED {sym} #{p.ticket} {side}: emergency SL -> {sl:.2f} "
                        f"(was {getattr(p, 'sl', 0.0) or 'naked'})")
            out["repaired"] += 1
        else:
            rc = getattr(res, "retcode", "?")
            logger.error(f"PROTECTION FAIL {sym} #{p.ticket}: retcode={rc}")
            out["failed"] += 1
    if out["failed"]:
        try:
            import alerts
            alerts.send(f"EMERGENCY PROTECTION FAILED: {out['failed']} {symbol} "
                        f"position(s) could not be protected -- manual action needed")
        except Exception:
            pass
    return out
