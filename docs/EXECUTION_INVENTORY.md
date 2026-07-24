# EXECUTION_INVENTORY — PHASE 601 Stage 1

The single authoritative list of every execution-capable component in this repository. "Execution-
capable" = can send/modify/close a broker order. Derived from a full source scan
(`order_send`, `place_order*`, broker classes, `--live`, magic numbers, symbols).

## Order-sending brokers (the only code that can reach a venue)
| file | class | venue | order primitive | magic | enabled? |
|--|--|--|--|--|--|
| `mt5_broker.py` | `MT5Broker` | **MetaTrader5 (Pepperstone demo)** | `order_send` (`TRADE_ACTION_DEAL`), magic **770001** | 770001 | yes — this placed the BTC trades |
| `binance_broker.py` | `BinanceBroker` | Binance (BTC/ETH) | signed REST `place_order` | n/a | only if selected |
| `alpaca_broker.py` | `AlpacaBroker` | Alpaca (US equities) | `place_order` | n/a | only if selected |
| `ctrader_broker.py` | `CTraderBroker` | cTrader | `place_order` | n/a | only if selected |
| `tradovate_broker.py` | `TradovateBroker` | Tradovate | — | n/a | only if selected |

## Strategy processes that CALL a broker
| file | function | symbols | tag/strategy | risk / stop | enabled? | tested? | approved? |
|--|--|--|--|--|--|--|--|
| `live_trader.py` | `run_btc` | BTC | tag "BTC" (sweep pillar #3) | `RISK_BTC=0.6%`, `STOP_BTC=2.5%`, RR 3.0 | **was live (mt5)** | backtest only | **NO** |
| `live_trader.py` | `run_btc_trend` | BTC | tag "BTCTREND" (long/flat trend) | wider/floor stop | **was live (mt5)** | backtest only | **NO** |
| `live_trader.py` | `run_s1..s5` | QQQ/GLD/GDX/SLV/USO | S1–S5 | `RISK_Sx` × VIX/DD | Alpaca path | backtest | NO |
| `scripts/phase404_live.py` | `run` | XAU/EUR/GBP/JPY/CAD/CHF/NAS100 | phase404 OTE | 0.25%/trade, magic 404404 | dry-run default; `--live` demo-guarded | backtest = **−0.80R** | **NO** |
| `btc_meanrev.py` | — | BTCUSDT | BTC mean-rev | — | standalone | research | NO |
| `btc_funding_reversal.py` | — | BTCUSDT | funding reversal | — | standalone | research | NO |
| `fill_ledger.py` | records | — | order boundary logger | — | passive | — | — |

## Auto-launch / scheduling surface (VPS — verify manually)
- No repo-internal scheduler found. **Human must check the VPS**: Task Scheduler, Startup folder,
  and any `.bat`/service that relaunches `python live_trader.py --broker mt5`. That relaunch is the
  most likely reason the BTC bot kept running after restarts.

## Flags that enable live orders
- `phase404_live.py --live` (demo-guarded, magic 404404).
- `live_trader.py --broker mt5` (the BTC bleeder path; **no demo guard** — this is a gap Stage 12 fixes).

## Findings that PHASE 601 must fix
1. **`live_trader.py --broker mt5` has no demo-account guard** — it will trade a live account if pointed at one. (phase404_live has a guard; live_trader does not.)
2. **No strategy-contract / approval check anywhere** — any of the above will trade if launched; nothing verifies an approved trial, frozen version, or evidence record. This is the core hole PHASE 601 closes (Stages 2/4/6).
3. **BTC strategies were never `PAPER_APPROVED`** — they ran on backtest confidence only.
4. **Local-only protection risk**: confirm every live path submits a broker-side SL *with* the entry (Stage 7).
