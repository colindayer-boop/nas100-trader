"""
test_order.py -- place ONE minimum-size MT5 DEMO order WITH sl/tp, bypassing all
strategy filters, so you can visually confirm the S/L and T/P columns populate in
the MT5 terminal. DEMO ONLY. Close the position afterwards (or let it hit SL/TP).

Usage:  python test_order.py [SYMBOL] [buy|sell]
        python test_order.py BTC buy     (default)
        python test_order.py QQQ buy     (-> NAS100)
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from mt5_broker import MT5Broker

internal = sys.argv[1] if len(sys.argv) > 1 else "BTC"
side     = sys.argv[2] if len(sys.argv) > 2 else "buy"

b = MT5Broker()
m = b._mt5
sym = b.map(internal)
b._ensure_symbol(sym)

tick = m.symbol_info_tick(sym)
info = m.symbol_info(sym)
price = tick.ask if side == "buy" else tick.bid

STOP, RR = 0.015, 3.0
if side == "buy":
    sl = price * (1 - STOP); tp = price * (1 + STOP * RR)
else:
    sl = price * (1 + STOP); tp = price * (1 - STOP * RR)

# minimum tradeable size: volume_min lots -> convert to the 'units' place_order expects
cs = getattr(info, "trade_contract_size", 1.0) or 1.0
units = (getattr(info, "volume_min", 0.01) or 0.01) * cs

print(f"TEST ORDER (demo, bypasses filters): {side} {internal} -> {sym}")
print(f"  price ~{price:.2f} | SL={sl:.2f} | TP={tp:.2f} | min lot")
try:
    oid = b.place_order(internal, units, side, "TEST", sl=sl, tp=tp)
    print(f"  PLACED ok -- order/ticket id: {oid}")
    print("  -> Check the MT5 'Trade' tab: the position should show S/L and T/P filled.")
    print("  -> Close it when done: right-click the position -> Close Order.")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
