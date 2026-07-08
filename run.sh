#!/bin/bash
# Daily paper run — fires all strategies on the paper accounts.
# Usage:  ./run.sh            (runs all sessions)
#         ./run.sh asian      (just the Asian sweep session)
# For real automation, schedule it with cron at the session times instead.

cd /Users/colindayer/nas100_backtest || exit 1
SESSION="${1:-all}"
echo "================ $(date '+%Y-%m-%d %H:%M') — paper run (session=$SESSION) ================"

echo ">>> Nasdaq + Gold via Alpaca (QQQ/GLD)"
python3 live_trader.py --broker alpaca --session "$SESSION"

echo ">>> BTC via Binance"
python3 live_trader.py --broker binance --session btc --dry-run

echo "================ done ================"
