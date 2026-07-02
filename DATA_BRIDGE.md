# Futures Data Bridge — spec (v2, build only if going the futures route)

Closes the biggest sim-to-live gap: the intraday sweep/ORB pillars are modeled on
ETF proxies (QQQ/GLD) that **don't contain the overnight session** where the edge
lives. This wires **Databento (history) + Rithmic (live)** to model and trade the
*exact* exchange instrument (NQ/GC/CL), on the real ~23h book.

Do NOT build this until: (1) the CFD live-paper edge confirms, AND (2) you've
chosen the futures route (Topstep/Apex) over CFD. It's a deliberate v2, not a
prerequisite for the first funded challenge.

---

## 1. Instruments (map the CFD proxies → real futures)
| Pillar | Current proxy | Real future | Micro (small accts) | Exchange |
|---|---|---|---|---|
| US100 sweep/ORB | QQQ ETF | **NQ** | **MNQ** (1/10) | CME Globex |
| Gold sweep/FVG | GLD ETF | **GC** | **MGC** (1/10) | COMEX |
| (optional) oil | USO ETF | **CL** | **MCL** (1/10) | NYMEX |
| BTC trend | BTC-USD spot | **BTC**/**MBT** | MBT | CME |

Micros (MNQ/MGC/MCL) make sizing granular enough for a $50k challenge — use them.

## 2. History — Databento
- Product: **CME Globex** via Databento (pay-per-use; a few symbols of 1-min +
  daily history is cheap — estimate <$50 one-time for the backtest window).
- Dataset: `GLBX.MDP3`. Schema: **`ohlcv-1m`** (1-min bars) for sweep/ORB;
  `ohlcv-1d` for the trend pillar.
- Symbology: **continuous front-month** — use `stype_in="continuous"` with the
  roll rule (e.g. `NQ.c.0`) so you get a clean back-adjusted series WITHOUT the
  roll artifacts that corrupted the yfinance `CL=F` test (see EDGE_HUNT_BRIEF trap).
- Session: request **full session** (Globex ~23h) — this is the whole point; the
  Tokyo/overnight range the ETF proxy lacks is now present.
- Timezone: bars come UTC; convert to ET for the Asian-session logic
  (`_asian_sweep_fires` already keys off ET hours).

Pull once, cache to parquet under `data/`, backtest offline (same `--sweep` gauntlet).

## 3. Live — Rithmic
- Rithmic = low-latency execution/data feed used by Topstep/Apex/Tradovate.
- Wiring: new `rithmic_broker.py` implementing the same `Broker` ABC
  (`get_bars/get_account/get_positions/place_order/close_position`) as the MT5/
  Binance adapters — the strategy code (`run_s1`, `run_overnight`, etc.) is
  unchanged; only the execution layer swaps.
- Auth: Rithmic uses a gateway + user/pw/system-name (from the prop firm). Put in
  `config.ini [rithmic]` (gitignored), never in chat.
- Order type: market or stop-limit on the micro contract; qty in **contracts**
  (integer) — replace the fractional-share sizing with a contracts calc:
  `contracts = floor((equity * risk_frac) / (stop_ticks * tick_value))`.

## 4. Re-model the sweep on real session data (the actual fix)
1. Load NQ 1-min full-session from Databento → build the **Asian range** from the
   *real* overnight bars (not missing, as with QQQ).
2. Re-run the sweep gauntlet (`edge_hunt.py`-style IS/OOS + `--sweep` robustness)
   on NQ/GC. **Re-validate** — the ETF-proxy Sharpe does NOT transfer; prove the
   edge exists on the real instrument before trusting it.
3. Add realistic futures costs: commission + exchange fee + 1-tick slippage per
   side (NQ tick = 0.25 = $5 on NQ / $0.50 on MNQ).

## 5. Prop-rule difference to bake in
Futures firms use **intraday trailing drawdown** (tightens against peak tick-by-
tick) — harsher than FTMO's EOD. Update `prop_sim.py`: change the max-DD check to
trail off the running intra-path peak *within* the day, not just close-to-close.
Re-run pass odds under the harsher rule before committing to a firm.

## 6. Build order (when the time comes)
1. Databento pull + parquet cache (1 script, offline).
2. Re-validate sweep/ORB on NQ/GC via `--sweep`. **Gate: 6/6 or stop.**
3. `rithmic_broker.py` (execution ABC) + `config.ini [rithmic]`.
4. `prop_sim.py` intraday-trailing mode; re-check pass odds.
5. Paper-trade on the firm's Rithmic demo before any challenge fee.

## Cost summary
- Databento history: ~<$50 one-time (few symbols, backtest window).
- Rithmic live: bundled in the prop firm's platform fee (~$100–150/mo while active).
- vs CFD: challenge fee only, no data cost, already wired.
