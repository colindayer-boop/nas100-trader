# nas100-trader — Run Reference

A multi-strategy, broker-agnostic systematic trading bot. Validated edges stacked
into a diversified book (combined Sharpe 1.66, -5.8% DD, prop-viable).

## Setup (once)
```
pip install -r requirements.txt          # pandas numpy yfinance scipy alpaca-py requests
# put credentials in config.ini (gitignored) — see config.example.ini
```

## The one command that runs everything
```
python live_trader.py --broker <BROKER> --session <SESSION> [--dry-run]
```
- `--broker`: `alpaca` (US ETFs/stocks, paper), `mt5` (Pepperstone CFDs/prop),
  `binance` (crypto), `ctrader`
- `--dry-run`: print intended orders, place nothing (paper-track)

## Sessions (what each runs)
| session | what it does | when to schedule |
|---|---|---|
| `all` | S1 sweep + S2 gold + S3 vol + S4 multi-sweep + S5 ORB + **sweep basket** | 3×/day (07:30, 14:30, 21:00 UTC) |
| `sweep` | S1 Asian-sweep on the validated basket (SPY/IWM/GLD/XLK/XLE/AAPL/MSFT/NVDA/AMZN) | with `all` |
| `overnight` | long QQQ→NAS100 into Tue+Wed mornings | close 15:55 ET + open 10:00 ET |
| `btctrend` | vol-targeted Donchian trend on BTC | daily |
| `btc` | BTC Asian-sweep | hourly (08-16 UTC) |
| `rebal` | monthly cross-asset momentum | 1st of month |

## Deploy (hands-off)
- **Alpaca (equities):** GitHub Actions `.github/workflows/main.yml` (cloud, auto-pulls code).
- **MT5 (prop):** Windows VPS scheduled tasks running `--broker mt5 --session {all,overnight}`.
- **BTC:** Railway/VPS (Binance geo-blocks US cloud; yfinance fallback in binance_broker).

## Risk / prop config (`config.ini [risk]`)
```
target_drawdown = 0.08   # DD-throttle keeps live DD near this (safe under 10% prop limit)
daily_loss_limit = 0.05  # halt new orders if daily loss exceeds
monthly_loss_limit = 0.04
```
The conformal DD-throttle auto-sizes RISK_SCALE to hold the target drawdown.

## Backtests / research
```
python full_yearly.py            # S1-S5 combined, per year
python alpaca_universe_sweep.py  # sweep across a large universe (Alpaca free extended-hours)
python cot_oil_strategy.py       # (rejected) COT oil — example of the gauntlet
```
Discipline: every new edge must pass IS/OOS walk-forward + costs + correlation
(<0.3 to QQQ) + regime check. See EDGE_HUNT_BRIEF.md.

## Prop challenge (FundedNext Stellar / FTMO)
**The prop-tradeable book = 3 uncorrelated asset classes** (US stocks don't trade on prop):
| Prop instrument | Class | Edge |
|---|---|---|
| US100 | Index | Asian sweep, ORB |
| XAUUSD | Metals | sweep + FVG |
| BTC | Crypto | vol-targeted trend |

Config: `[risk] prop_mode=1, prop_vol_target=0.16` (balanced sweet spot).
Rules: +8% target, 10% max DD, 5% daily DD, **no time limit** (Stellar).

**Realistic pass odds** (16% vol, by *live* Sharpe — backtest is 1.66, expect decay):
| live Sharpe | 1mo | 2mo | 3mo | 6mo | blow-up(3mo) |
|---|---|---|---|---|---|
| 1.66 (backtest) | 16% | 41% | 58% | 79% | 9% |
| 1.2 (mild decay) | 13% | 35% | 50% | 70% | 13% |
| 0.8 (heavy decay) | 11% | 29% | 42% | 61% | 17% |

Not a one-month lottery — a **2–4 month grind at ~50% by month 3**. Confirm live
Sharpe on paper BEFORE paying a challenge fee. Biggest cost is re-fees on failed tries.

## Validated book (as of 2026-07)
- S1 sweep (9 tickers, all regimes): Sharpe ~1.0
- Overnight (Tue/Wed): Sharpe 0.68 | BTC trend (vol-targeted): Sharpe 0.67
- **Combined (risk-parity, corr ~0.05): Sharpe 1.66, -5.8% DD, +9.5%/yr**
- Prop-ready (throttle at 8%): ~+16%/yr at ~10% DD
