#!/usr/bin/env python3
"""
NAS100 Asian Sweep Paper Trader
Auto-executes on OANDA practice account via REST API.
Deploy to Railway.app — runs 24/7, wakes up once per hour.

Setup:
  1. OANDA practice account at oanda.com → get API key + account ID
  2. Telegram bot via @BotFather → get bot token, then message the bot to get your chat ID
  3. Set env vars (in Railway dashboard or .env file)
  4. Deploy: railway up
"""

import os, time, logging
from datetime import datetime, timedelta
import pytz
import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── CREDENTIALS — set these as env vars in Railway ─────────────────────
OANDA_KEY  = os.environ.get("OANDA_API_KEY",       "YOUR_OANDA_API_KEY")
OANDA_ACCT = os.environ.get("OANDA_ACCOUNT_ID",    "YOUR_ACCOUNT_ID")
TG_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN",  "")
TG_CHAT    = os.environ.get("TELEGRAM_CHAT_ID",    "")

OANDA_BASE = "https://api-fxpractice.oanda.com/v3"
INSTRUMENT = "NAS100_USD"
NY         = pytz.timezone("America/New_York")

# ── STRATEGY PARAMS (matched to backtest) ──────────────────────────────
STOP_PCT       = 0.015   # 1.5% stop loss
TARGET_RR      = 3.0     # 3R take profit
RISK_PCT       = 0.008   # 0.8% of account per trade (keeps max DD under 10%)
DAILY_LOSS_CAP = 0.05    # halt for the day if down 5%
MAX_DRAWDOWN   = 0.10    # halt permanently if down 10% from start
ATR_PERIOD     = 14
ATR_AVG_PERIOD = 200
ATR_MULT       = 1.5     # skip if current ATR > 1.5× its 200-bar average
RANGE_LOW      = 0.6     # daily range filter: lower bound (× 14d avg range)
RANGE_HIGH     = 1.4     # daily range filter: upper bound

# Asia session: 7pm – 2am NY.  London: 2am – 5am.  NY: 9:30am – noon.
ASIA_START_H   = 19
ASIA_END_H     = 2


# ── STATE (persists across hourly checks within one process run) ────────
state: dict = {
    "initial_balance":    None,
    "day_start_balance":  None,
    "current_day":        None,
    "daily_trade_taken":  False,
    "last_closed_trades": set(),   # trade IDs we've already notified on
}


# ── OANDA API ──────────────────────────────────────────────────────────
def _headers():
    return {"Authorization": f"Bearer {OANDA_KEY}", "Content-Type": "application/json"}


def get_account() -> dict:
    r = requests.get(f"{OANDA_BASE}/accounts/{OANDA_ACCT}/summary", headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()["account"]


def get_candles(granularity: str, count: int) -> pd.DataFrame:
    params = {"granularity": granularity, "count": count, "price": "M"}
    r = requests.get(f"{OANDA_BASE}/instruments/{INSTRUMENT}/candles",
                     headers=_headers(), params=params, timeout=20)
    r.raise_for_status()
    rows = []
    for c in r.json()["candles"]:
        if not c.get("complete", True):
            continue
        m = c["mid"]
        rows.append({
            "time":   pd.Timestamp(c["time"]).tz_convert(NY),
            "open":   float(m["o"]),
            "high":   float(m["h"]),
            "low":    float(m["l"]),
            "close":  float(m["c"]),
        })
    return pd.DataFrame(rows).set_index("time")


def get_open_trades() -> list:
    r = requests.get(f"{OANDA_BASE}/accounts/{OANDA_ACCT}/openTrades",
                     headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()["trades"]


def get_recent_closed_trades() -> list:
    params = {"instrument": INSTRUMENT, "count": 10, "state": "CLOSED"}
    r = requests.get(f"{OANDA_BASE}/accounts/{OANDA_ACCT}/trades",
                     headers=_headers(), params=params, timeout=15)
    r.raise_for_status()
    return r.json()["trades"]


def place_order(direction: int, stop: float, target: float, units: int) -> dict:
    body = {
        "order": {
            "type":        "MARKET",
            "instrument":  INSTRUMENT,
            "units":       str(units) if direction == 1 else str(-units),
            "timeInForce": "FOK",
            "stopLossOnFill":   {"price": f"{stop:.1f}"},
            "takeProfitOnFill": {"price": f"{target:.1f}"},
        }
    }
    r = requests.post(f"{OANDA_BASE}/accounts/{OANDA_ACCT}/orders",
                      headers=_headers(), json=body, timeout=15)
    r.raise_for_status()
    return r.json()


# ── TELEGRAM ────────────────────────────────────────────────────────────
def notify(msg: str):
    log.info(f"NOTIFY: {msg}")
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")


# ── SIGNAL DETECTION ────────────────────────────────────────────────────
def asian_session_window(now: datetime):
    """Return (start, end) datetimes for the current/most-recent Asian session."""
    if now.hour >= ASIA_START_H:
        # Asia started today at 7pm, ends tomorrow at 2am
        start = now.replace(hour=ASIA_START_H, minute=0, second=0, microsecond=0)
        end   = start + timedelta(hours=7)          # 7pm + 7h = 2am next day
    else:
        # Asia started yesterday at 7pm, ends today at 2am
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=ASIA_START_H, minute=0, second=0, microsecond=0)
        end   = now.replace(hour=ASIA_END_H,   minute=0, second=0, microsecond=0)
    return start, end


def compute_signal(df_h1: pd.DataFrame, df_d: pd.DataFrame):
    """
    Returns (direction, entry, stop, target) if a setup is found, else (0, None, None, None).
    direction: 1=long, -1=short
    """
    if len(df_h1) < ATR_AVG_PERIOD + 20 or len(df_d) < 16:
        log.info("Not enough candle history yet")
        return 0, None, None, None

    now = datetime.now(NY)
    bar = df_h1.iloc[-1]   # most recently completed hourly bar

    # ── Session gate ────────────────────────────────────────────────────
    h, m = bar.name.hour, bar.name.minute
    in_london = 2 <= h < 5
    in_ny     = (h == 9 and m >= 30) or (10 <= h < 12)
    if not (in_london or in_ny):
        log.info(f"Bar at {bar.name.strftime('%H:%M')} NY — outside London/NY session")
        return 0, None, None, None

    # ── Asian session H/L ────────────────────────────────────────────────
    asia_start, asia_end = asian_session_window(now)
    asia_bars = df_h1[(df_h1.index >= asia_start) & (df_h1.index < asia_end)]
    if len(asia_bars) < 2:
        log.info("Too few Asian session bars — range not established yet")
        return 0, None, None, None

    asian_high = asia_bars["high"].max()
    asian_low  = asia_bars["low"].min()
    log.info(f"Asian range: {asian_low:.1f} – {asian_high:.1f}")

    # ── ATR volatility filter ────────────────────────────────────────────
    prev_close = df_h1["close"].shift(1)
    tr = pd.concat([
        df_h1["high"] - df_h1["low"],
        (df_h1["high"] - prev_close).abs(),
        (df_h1["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr     = tr.rolling(ATR_PERIOD).mean()
    atr_avg = atr.rolling(ATR_AVG_PERIOD).mean()
    if atr.iloc[-1] > ATR_MULT * atr_avg.iloc[-1]:
        log.info(f"High volatility — ATR {atr.iloc[-1]:.1f} > {ATR_MULT}× avg {atr_avg.iloc[-1]:.1f}")
        return 0, None, None, None

    # ── Daily range filter ───────────────────────────────────────────────
    d_range = df_d["high"] - df_d["low"]
    d_avg   = d_range.rolling(14).mean()
    yest_r  = d_range.iloc[-2]
    yest_avg = d_avg.iloc[-2]
    if not (RANGE_LOW * yest_avg <= yest_r <= RANGE_HIGH * yest_avg):
        log.info(f"Daily range out of band: {yest_r:.0f} vs avg {yest_avg:.0f}")
        return 0, None, None, None

    # ── Bull regime filter: daily EMA50 above daily EMA200 ───────────────
    d_close  = df_d["close"]
    ema50    = d_close.ewm(span=50).mean()
    ema200   = d_close.ewm(span=200).mean()
    in_uptrend = (d_close.iloc[-1] > ema50.iloc[-1]) and (ema50.iloc[-1] > ema200.iloc[-1])
    if not in_uptrend:
        log.info("Not in bull regime (daily EMA50 < EMA200 or price < EMA50) — longs only, skipping")
        return 0, None, None, None

    # ── Previous-day low ────────────────────────────────────────────────
    # Get yesterday's low from daily candles
    prev_day_low  = df_d["low"].iloc[-2]
    prev_day_high = df_d["high"].iloc[-2]

    # ── Sweep detection: Asian low OR previous-day low (long-only) ───────
    asian_sweep_long = bar["low"] < asian_low  and bar["close"] > asian_low
    pd_sweep_long    = bar["low"] < prev_day_low and bar["close"] > prev_day_low

    if asian_sweep_long or pd_sweep_long:
        sweep_type = "Asian" if asian_sweep_long else "PrevDay"
        log.info(f"{sweep_type} low sweep detected — LONG signal")
        direction = 1
    else:
        log.info(f"No long sweep — bar H={bar['high']:.1f} L={bar['low']:.1f} C={bar['close']:.1f}")
        return 0, None, None, None

    entry  = bar["close"]
    stop   = entry * (1 - STOP_PCT)
    risk   = abs(entry - stop)
    target = entry + risk * TARGET_RR

    return direction, entry, stop, target


# ── CLOSED TRADE NOTIFICATIONS ──────────────────────────────────────────
def check_closed_trades():
    try:
        trades = get_recent_closed_trades()
    except Exception:
        return
    for t in trades:
        tid = t["id"]
        if tid in state["last_closed_trades"]:
            continue
        state["last_closed_trades"].add(tid)
        pnl   = float(t.get("realizedPL", 0))
        units = int(t.get("initialUnits", 0))
        emoji = "✅" if pnl >= 0 else "❌"
        notify(
            f"{emoji} Trade closed\n"
            f"Units: {units:+d}  P&L: ${pnl:+.0f}\n"
            f"Reason: {t.get('closingTransactionIDs', ['?'])[-1]}"
        )


# ── MAIN HOURLY CHECK ───────────────────────────────────────────────────
def run_check():
    now_ny = datetime.now(NY)
    log.info(f"=== {now_ny.strftime('%Y-%m-%d %H:%M %Z')} ===")

    acct    = get_account()
    balance = float(acct["balance"])
    nav     = float(acct["NAV"])

    # First-run init
    if state["initial_balance"] is None:
        state["initial_balance"]   = balance
        state["day_start_balance"] = balance
        state["current_day"]       = now_ny.date()
        notify(
            f"📊 *NAS100 paper trader started*\n"
            f"Balance: ${balance:,.0f}\nInstrument: {INSTRUMENT}"
        )

    # Daily reset
    today = now_ny.date()
    if state["current_day"] != today:
        state["current_day"]       = today
        state["day_start_balance"] = balance
        state["daily_trade_taken"] = False
        log.info(f"New trading day — balance ${balance:,.0f}")

    # Check for closed trades we should notify on
    check_closed_trades()

    # Prop firm risk guards
    daily_dd = (nav - state["day_start_balance"]) / state["day_start_balance"]
    total_dd = (nav - state["initial_balance"])   / state["initial_balance"]
    log.info(f"NAV ${nav:,.0f}  daily {daily_dd:+.1%}  total {total_dd:+.1%}")

    if daily_dd <= -DAILY_LOSS_CAP:
        log.info(f"Daily loss cap hit ({daily_dd:.1%}) — sitting out today")
        return
    if total_dd <= -MAX_DRAWDOWN:
        notify(f"🛑 *Max drawdown hit* ({total_dd:.1%}) — trader halted. Check account.")
        log.warning("Max drawdown limit — halting")
        time.sleep(86400)  # sleep 24h before next check
        return

    # Already in a trade?
    open_trades = get_open_trades()
    if open_trades:
        t   = open_trades[0]
        pnl = float(t["unrealizedPL"])
        log.info(f"Holding {t['currentUnits']} units  unrealised P&L ${pnl:+.0f}")
        return

    # Already traded today?
    if state["daily_trade_taken"]:
        log.info("One trade already taken today — waiting for tomorrow")
        return

    # Fetch candles and check signal
    df_h1 = get_candles("H1", 500)
    df_d  = get_candles("D",   30)

    direction, entry, stop, target = compute_signal(df_h1, df_d)

    if direction == 0:
        log.info("No signal this hour")
        return

    # Position size
    risk_cash = nav * RISK_PCT
    stop_dist = abs(entry - stop)
    units     = int(risk_cash / stop_dist)

    if units < 1:
        log.warning(f"Position too small (risk ${risk_cash:.0f} / dist {stop_dist:.1f} = {units})")
        return

    label = "LONG" if direction == 1 else "SHORT"
    log.info(f"SIGNAL {label}  entry={entry:.1f}  stop={stop:.1f}  target={target:.1f}  units={units}")

    result = place_order(direction, stop, target, units)
    state["daily_trade_taken"] = True

    notify(
        f"{'🟢 *LONG*' if direction == 1 else '🔴 *SHORT*'} NAS100 entered\n"
        f"Entry:  {entry:.1f}\n"
        f"Stop:   {stop:.1f}  ({STOP_PCT:.1%})\n"
        f"Target: {target:.1f}  ({TARGET_RR}R)\n"
        f"Units:  {units}   Risk: ${risk_cash:.0f}"
    )


# ── SCHEDULER ───────────────────────────────────────────────────────────
def secs_to_next_check() -> int:
    """Sleep until 90 seconds past the next hour boundary."""
    now = datetime.now()
    elapsed = now.minute * 60 + now.second
    return max(60, 3600 - elapsed + 90)


if __name__ == "__main__":
    log.info("NAS100 Asian Sweep paper trader starting up")
    while True:
        try:
            run_check()
        except Exception as e:
            log.error(f"Unhandled error: {e}", exc_info=True)
            notify(f"⚠️ Paper trader error: {e}")
        wait = secs_to_next_check()
        log.info(f"Sleeping {wait // 60}m {wait % 60}s")
        time.sleep(wait)
