"""test_btctrend_rebalance.py -- hedging-account-safe BTCTREND rebalance.
Bug fixed: on a hedging account, a plain opposite-side deal OPENED a stray short
(observed live: long 0.38 + short 0.05, both tagged BTCTREND, state file blind to it).
Run: python -m unittest test_btctrend_rebalance -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_emergency_protection import FakeMT5, _Obj, _pos

SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_trader.py")).read()


class FakeMT5Hedging(FakeMT5):
    """Extends the fake terminal: DEAL with position=<ticket> reduces/closes that ticket
    (hedging-correct); DEAL without position= opens a NEW position (the hedging trap)."""

    def order_send(self, req):
        self.sent.append(dict(req))
        if self.reject:
            return _Obj(retcode=10013, comment="invalid stops")
        if req["action"] == self.TRADE_ACTION_SLTP:
            for p in self.positions:
                if p.ticket == req["position"]:
                    p.sl = req["sl"]
        elif req["action"] == self.TRADE_ACTION_DEAL and "position" in req:
            for p in list(self.positions):
                if p.ticket == req["position"]:
                    p.volume = round(p.volume - req["volume"], 8)
                    if p.volume <= 1e-9:
                        self.positions.remove(p)
        elif req["action"] == self.TRADE_ACTION_DEAL:
            side = "long" if req["type"] == self.ORDER_TYPE_BUY else "short"
            newp = _pos(ticket=100 + len(self.positions), sl=req.get("sl", 0.0), side=side)
            newp.volume = req["volume"]; newp.comment = req.get("comment", "")
            self.positions.append(newp)
        return _Obj(retcode=self.TRADE_RETCODE_DONE, price=self.ask, order=42, deal=7)


def _tagged(ticket, vol, side="long", sl=0.0, comment="BTCTREND"):
    p = _pos(ticket=ticket, sl=sl, side=side)
    p.volume = vol; p.comment = comment
    return p


def _broker(m):
    from mt5_broker import MT5Broker
    b = MT5Broker.__new__(MT5Broker)
    b._mt5 = m
    b.SYMBOL_MAP = {"BTC": "BTCUSD"}
    b._ensure_connected = lambda: True
    return b


class NetQty(unittest.TestCase):
    def test_broker_truth_nets_long_and_short(self):
        # the exact live book: long 0.38 + short 0.05, both BTCTREND
        m = FakeMT5Hedging(positions=[_tagged(1, 0.38), _tagged(2, 0.05, "short")])
        self.assertAlmostEqual(_broker(m).net_qty("BTC", tag="BTCTREND"), 0.33)

    def test_tag_filter_excludes_sweep_positions(self):
        m = FakeMT5Hedging(positions=[_tagged(1, 0.38), _tagged(3, 0.10, comment="BTC")])
        self.assertAlmostEqual(_broker(m).net_qty("BTC", tag="BTCTREND"), 0.38)


class CloseInto(unittest.TestCase):
    def test_reduction_closes_into_long_never_opens_short(self):
        m = FakeMT5Hedging(positions=[_tagged(1, 0.38)])
        closed = _broker(m).close_into("BTC", 0.10, "long", tag="BTCTREND")
        self.assertAlmostEqual(closed, 0.10)
        self.assertAlmostEqual(m.positions[0].volume, 0.28)
        self.assertEqual(len(m.positions), 1)                  # no new position
        self.assertIn("position", m.sent[0])                   # ticket-targeted close

    def test_full_reduction_removes_position(self):
        m = FakeMT5Hedging(positions=[_tagged(1, 0.38)])
        closed = _broker(m).close_into("BTC", 0.38, "long", tag="BTCTREND")
        self.assertAlmostEqual(closed, 0.38)
        self.assertEqual(m.positions, [])

    def test_buy_delta_first_closes_stray_short(self):
        # self-healing of the live stray-short book
        m = FakeMT5Hedging(positions=[_tagged(1, 0.38), _tagged(2, 0.05, "short")])
        closed = _broker(m).close_into("BTC", 0.05, "short", tag="BTCTREND")
        self.assertAlmostEqual(closed, 0.05)
        self.assertEqual([p.ticket for p in m.positions], [1])  # short leg gone

    def test_reduce_spans_multiple_tickets(self):
        m = FakeMT5Hedging(positions=[_tagged(1, 0.10), _tagged(2, 0.10)])
        closed = _broker(m).close_into("BTC", 0.15, "long", tag="BTCTREND")
        self.assertAlmostEqual(closed, 0.15)
        self.assertAlmostEqual(sum(p.volume for p in m.positions), 0.05)

    def test_never_closes_more_than_held(self):
        m = FakeMT5Hedging(positions=[_tagged(1, 0.10)])
        closed = _broker(m).close_into("BTC", 0.50, "long", tag="BTCTREND")
        self.assertAlmostEqual(closed, 0.10)                    # capped at holdings
        self.assertEqual(m.positions, [])


class WiringLocks(unittest.TestCase):
    def test_broker_is_source_of_truth(self):
        self.assertIn('net_qty("BTC", tag="BTCTREND")', SRC)
        self.assertIn("state drift", SRC)                       # divergence logged

    def test_sell_path_never_plain_opposite_deal_on_mt5(self):
        seg = SRC[SRC.index("def run_btc_trend"):SRC.index("SWEEP_BASKET")]
        self.assertIn('close_into("BTC", rest, "long"', seg)    # reductions close into longs
        self.assertIn("NOT opening a short", seg)               # long/flat invariant kept

    def test_buy_path_heals_stray_short_then_buys_with_sl(self):
        seg = SRC[SRC.index("def run_btc_trend"):SRC.index("SWEEP_BASKET")]
        self.assertIn('close_into("BTC", rest, "short"', seg)
        self.assertLess(seg.index('close_into("BTC", rest, "short"'),
                        seg.index('sl=emergency_floor'))        # heal first, then protected buy

    def test_donchian_signal_still_untouched(self):
        self.assertIn('H = close.rolling(20).max().shift(1); L = close.rolling(10).min().shift(1)', SRC)
        self.assertIn('BTC_TREND_VOLTARGET = 0.20', SRC)


if __name__ == "__main__":
    unittest.main(verbosity=2)
