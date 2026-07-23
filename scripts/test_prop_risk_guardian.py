"""Unit tests for prop_risk_guardian -- run: python scripts/test_prop_risk_guardian.py"""
import sys, os, json, tempfile
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prop_risk_guardian as g

C = g.Config()
NOW = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)


def snap(**kw):
    d = dict(ts=NOW, balance=50000, equity=50000, login=61552095, server="Pepperstone-Demo", positions=[], ok=True)
    d.update(kw); return g.Snapshot(**d)


def test_stale_blocks():
    s = snap(ts=NOW - timedelta(seconds=120))
    r = g.evaluate(s, C, 50000, 50000, 0, 0, None, now=NOW)
    assert not r["allow_new_entries"] and "STALE_DATA" in r["reason_codes"]

def test_missing_stop_blocks():
    s = snap(positions=[g.Position("NAS100", 1.0, 29000, 0, 770001, -50)])   # sl=0 -> no stop
    r = g.evaluate(s, C, 50000, 50000, 0, 0, None, now=NOW)
    assert "POSITION_MISSING_STOP" in r["reason_codes"]

def test_consecutive_loss_blocks():
    r = g.evaluate(snap(), C, 50000, 50000, 3, 5, None, now=NOW)
    assert "MAX_CONSECUTIVE_LOSSES" in r["reason_codes"]

def test_daily_stop_blocks():
    s = snap(equity=49400)                                   # -600 = -1.2% > 1% internal daily
    r = g.evaluate(s, C, 50000, 50000, 0, 0, None, now=NOW)
    assert "INTERNAL_DAILY_STOP" in r["reason_codes"]

def test_total_stop_blocks():
    s = snap(equity=48400)                                   # -1600 = -3.2% > 3% internal total
    r = g.evaluate(s, C, 50000, 50000, 0, 0, None, now=NOW)
    assert "INTERNAL_TOTAL_STOP" in r["reason_codes"]

def test_averaging_into_loss_blocks():
    s = snap(positions=[g.Position("BTCUSD", 0.3, 65000, 52000, 770001, -50),
                        g.Position("BTCUSD", 0.1, 66000, 52000, 770001, -30)])
    r = g.evaluate(s, C, 50000, 50000, 0, 0, None, now=NOW)
    assert any("AVERAGING_INTO_LOSS" in x for x in r["reason_codes"])

def test_cooldown_blocks():
    r = g.evaluate(snap(), C, 50000, 50000, 0, 0, NOW + timedelta(hours=5), now=NOW)
    assert "COOLDOWN_ACTIVE" in r["reason_codes"]

def test_proposed_risk_blocks():
    r = g.evaluate(snap(), C, 50000, 50000, 0, 0, None, proposed_risk_pct=0.5, now=NOW)
    assert "PROPOSED_RISK_TOO_LARGE" in r["reason_codes"]

def test_bad_data_fail_safe():
    r = g.evaluate(snap(ok=False), C, 50000, 50000, 0, 0, None, now=NOW)
    assert not r["allow_new_entries"] and "DATA_INCONSISTENT" in r["reason_codes"]

def test_clean_allows():
    r = g.evaluate(snap(positions=[g.Position("EURUSD", 0.1, 1.08, 1.075, 770001, 5)]),
                   C, 50000, 50000, 0, 0, None, now=NOW)
    assert r["allow_new_entries"], r["reason_codes"]

def test_atomic_write():
    old = g.STATE_FILE
    g.STATE_FILE = __import__("pathlib").Path(tempfile.mkdtemp()) / "s.json"
    g.write_state_atomic({"a": 1})
    assert json.loads(g.STATE_FILE.read_text())["a"] == 1
    g.STATE_FILE = old

def test_hwm_drawdown():
    r = g.evaluate(snap(equity=49500), C, 50000, hwm=50500, consecutive_losses=0, trades_today=0, cooldown_until=None, now=NOW)
    assert r["hwm_drawdown_pct"] == round((50500-49500)/50000*100, 3)

def test_correlated_risk():
    s = snap(positions=[g.Position("BTCUSD", 5, 65000, 60000, 770001), g.Position("ETHUSD", 5, 3000, 2800, 770001)])
    r = g.evaluate(s, C, 50000, 50000, 0, 0, None, now=NOW)
    assert any("CORRELATED_RISK" in x for x in r["reason_codes"])

def test_replay_no_lookahead():
    # blocking a trade must NOT use that trade's own pnl -> decision reproducible without it
    import re, html
    # build a tiny synthetic loss cascade
    trades = [{"ts": NOW + timedelta(minutes=i), "sym": "NAS100", "pnl": p, "has_sl": True}
              for i, p in enumerate([-100, -100, -100, -500, +300])]
    g._load_closed_trades = lambda path: trades
    r = g.replay("x", C)
    # after 3 consecutive losses, the -500 must be BLOCKED (decision used prior state only)
    assert r["n_blocked"] >= 1 and r["loss_avoided"] >= 500


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} tests passed")
