"""test_emergency_protection.py -- R1 tests: BTCTREND emergency broker-side floor.
Run: python -m unittest test_emergency_protection -v   (no live MT5 needed; fake terminal)
"""
import math
import os
import sys
import types
from execution_safety.execution_guard import armed
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emergency_protection import (EMERGENCY_STOP_PCT, emergency_floor, needed_sl,
                                  ensure_btc_protection)

SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_trader.py")).read()


# ---------------- fake MT5 terminal ----------------
class _Obj:
    def __init__(self, **kw): self.__dict__.update(kw)


class FakeMT5:
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_SLTP = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    ORDER_FILLING_IOC = 0
    ORDER_TIME_GTC = 0
    TRADE_RETCODE_DONE = 10009

    def __init__(self, positions=(), bid=100_000.0, ask=100_010.0, reject=False):
        self.positions = list(positions)
        self.bid, self.ask = bid, ask
        self.reject = reject
        self.sent = []          # every order_send request

    def positions_get(self, symbol=None):
        return [p for p in self.positions if symbol is None or p.symbol == symbol]

    def symbol_info_tick(self, sym): return _Obj(bid=self.bid, ask=self.ask)

    def symbol_info(self, sym):
        return _Obj(point=0.01, trade_stops_level=0, trade_contract_size=1.0,
                    volume_step=0.01, volume_min=0.01, volume_max=100.0)

    def symbol_select(self, sym, on): return True
    def terminal_info(self): return _Obj()
    def account_info(self): return _Obj()
    def last_error(self): return "rejected by fake"

    def order_send(self, req):
        self.sent.append(dict(req))
        if self.reject:
            return _Obj(retcode=10013, comment="invalid stops")
        # apply SLTP modifications to the fake position book
        if req["action"] == self.TRADE_ACTION_SLTP:
            for p in self.positions:
                if p.ticket == req["position"]:
                    p.sl = req["sl"]
        return _Obj(retcode=self.TRADE_RETCODE_DONE, price=self.ask, order=42, deal=7)


class FakeBroker:
    SYMBOL_MAP = {"BTC": "BTCUSD"}
    def __init__(self, m): self._mt5 = m


def _pos(ticket=1, sl=0.0, side="long", symbol="BTCUSD"):
    return _Obj(ticket=ticket, symbol=symbol, sl=sl, tp=0.0,
                type=FakeMT5.POSITION_TYPE_BUY if side == "long" else FakeMT5.POSITION_TYPE_SELL)


# ---------------- floor math ----------------
class FloorMath(unittest.TestCase):
    def test_long_short_levels(self):
        self.assertAlmostEqual(emergency_floor(100.0, "long"), 80.0)
        self.assertAlmostEqual(emergency_floor(100.0, "short"), 120.0)

    def test_invalid_and_nan_price_fails_safely(self):
        for bad in (None, float("nan"), float("inf"), 0.0, -5.0):
            with self.assertRaises(ValueError):
                emergency_floor(bad, "long")
        with self.assertRaises(ValueError):
            emergency_floor(100.0, "long", pct=1.5)

    def test_never_loosen(self):
        floor = 80.0
        self.assertEqual(needed_sl(0.0, floor, "long"), 80.0)      # naked -> protect
        self.assertEqual(needed_sl(70.0, floor, "long"), 80.0)     # looser -> tighten
        self.assertIsNone(needed_sl(85.0, floor, "long"))          # tighter -> keep
        self.assertEqual(needed_sl(130.0, 120.0, "short"), 120.0)  # short looser -> tighten
        self.assertIsNone(needed_sl(115.0, 120.0, "short"))        # short tighter -> keep


# ---------------- repair path ----------------
class RepairPath(unittest.TestCase):
    def test_naked_long_repaired_and_verified(self):
        m = FakeMT5(positions=[_pos(sl=0.0)])
        r = ensure_btc_protection(FakeBroker(m), "BTC")
        self.assertEqual((r["checked"], r["repaired"], r["failed"]), (1, 1, 0))
        self.assertAlmostEqual(m.positions[0].sl, m.bid * (1 - EMERGENCY_STOP_PCT))
        self.assertEqual(m.sent[0]["action"], FakeMT5.TRADE_ACTION_SLTP)

    def test_naked_short_repaired(self):
        m = FakeMT5(positions=[_pos(sl=0.0, side="short")])
        r = ensure_btc_protection(FakeBroker(m), "BTC")
        self.assertEqual(r["repaired"], 1)
        self.assertAlmostEqual(m.positions[0].sl, m.ask * (1 + EMERGENCY_STOP_PCT))

    def test_tighter_stop_never_loosened(self):
        tight = 95_000.0                                   # tighter than the 80k floor
        m = FakeMT5(positions=[_pos(sl=tight)])
        r = ensure_btc_protection(FakeBroker(m), "BTC")
        self.assertEqual((r["repaired"], r["skipped_tighter"]), (0, 1))
        self.assertEqual(m.positions[0].sl, tight)
        self.assertEqual(m.sent, [])                       # nothing sent to the broker

    def test_idempotent_rerun(self):
        m = FakeMT5(positions=[_pos(sl=0.0)])
        b = FakeBroker(m)
        ensure_btc_protection(b, "BTC")
        sent_after_first = len(m.sent)
        r2 = ensure_btc_protection(b, "BTC")               # restart / re-run
        self.assertEqual(len(m.sent), sent_after_first)    # no duplicate modification
        self.assertEqual((r2["repaired"], r2["skipped_tighter"]), (0, 1))

    def test_broker_rejection_logged_not_silent(self):
        m = FakeMT5(positions=[_pos(sl=0.0)], reject=True)
        r = ensure_btc_protection(FakeBroker(m), "BTC")
        self.assertEqual((r["repaired"], r["failed"]), (0, 1))
        self.assertEqual(m.positions[0].sl, 0.0)           # honest: still naked, alerted

    def test_dry_run_broker_noop(self):
        r = ensure_btc_protection(types.SimpleNamespace(), "BTC")
        self.assertEqual(r, {"checked": 0, "repaired": 0, "failed": 0, "skipped_tighter": 0})


# ---------------- entry path: atomic protection through the real MT5Broker code ----------------
class EntryProtection(unittest.TestCase):
    def _broker(self, m):
        from mt5_broker import MT5Broker
        b = MT5Broker.__new__(MT5Broker)                   # bypass live login
        b._mt5 = m
        b.SYMBOL_MAP = {"BTC": "BTCUSD"}
        return b

    def test_new_entry_carries_sl_in_same_request(self):
        m = FakeMT5()
        b = self._broker(m)
        with armed("TEST-DECISION"):
            b.place_order("BTC", 0.5, "buy", "BTCTREND", sl=emergency_floor(m.ask, "long"))
        req = m.sent[0]
        self.assertEqual(req["action"], FakeMT5.TRADE_ACTION_DEAL)
        self.assertIn("sl", req)                           # SL atomic with the entry
        self.assertAlmostEqual(req["sl"], m.ask * (1 - EMERGENCY_STOP_PCT))

    def test_rejection_raises_no_naked_position(self):
        m = FakeMT5(reject=True)
        b = self._broker(m)
        with self.assertRaises(RuntimeError):              # entry rejected -> raises
            with armed("TEST-DECISION"):
                b.place_order("BTC", 0.5, "buy", "BTCTREND",
                              sl=emergency_floor(m.ask, "long"))
        self.assertEqual(m.positions, [])                  # nothing opened


# ---------------- behavior preservation (source-level wiring locks) ----------------
class BehaviorUnchanged(unittest.TestCase):
    def test_donchian_logic_untouched(self):
        # the exact normal-exit signal lines are still present, unmodified
        self.assertIn('H = close.rolling(20).max().shift(1); L = close.rolling(10).min().shift(1)', SRC)
        self.assertIn('elif p == 1 and c < (L.iloc[i] if pd.notna(L.iloc[i]) else 0): p = 0', SRC)
        self.assertIn('BTC_TREND_VOLTARGET = 0.20', SRC)

    def test_buy_carries_emergency_sl_sell_does_not(self):
        # buys (exposure increases) attach the floor; reductions never carry an SL
        # (hedging-safe close_into, or plain sell on netting fallback brokers)
        self.assertIn('sl=emergency_floor(price, "long")', SRC)
        seg = SRC[SRC.index("def run_btc_trend"):SRC.index("SWEEP_BASKET")]
        sell_branch = seg[seg.index("else:", seg.index("sl=emergency_floor")):]
        self.assertNotIn("sl=", sell_branch)                   # no SL on closing orders

    def test_no_take_profit_added(self):
        # R1 mandate: no TP unless evidence-supported -- BTCTREND must not gain one
        seg = SRC[SRC.index("def run_btc_trend"):SRC.index("SWEEP_BASKET")]
        self.assertNotIn("tp=", seg)

    def test_repair_runs_before_tolerance_return(self):
        seg = SRC[SRC.index("def run_btc_trend"):SRC.index("SWEEP_BASKET")]
        self.assertLess(seg.index("ensure_btc_protection"),
                        seg.index("within tolerance"))     # held positions protected daily

    def test_other_strategies_untouched(self):
        # no other run_* function references the new module
        for fn in ("run_s1", "run_s2", "run_s3", "run_s4", "run_s5",
                   "run_btc(", "run_overnight"):
            start = SRC.index(f"def {fn}" if not fn.endswith("(") else f"def {fn[:-1]}(")
            end = SRC.index("def ", start + 10)
            self.assertNotIn("emergency_", SRC[start:end], fn)


if __name__ == "__main__":
    unittest.main(verbosity=2)
