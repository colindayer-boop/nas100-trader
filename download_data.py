import configparser, os
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime
import pandas as pd

def _load_config(section):
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini"))
    return dict(cfg[section]) if section in cfg else {}

_cfg = _load_config("alpaca")
API_KEY    = os.environ.get("ALPACA_KEY",    _cfg.get("key", ""))
SECRET_KEY = os.environ.get("ALPACA_SECRET", _cfg.get("secret", ""))

client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

request = StockBarsRequest(
    symbol_or_symbols=["QQQ"],
    timeframe=TimeFrame.Hour,
    start=datetime(2019, 1, 1),
    end=datetime(2026, 6, 1),
)

print("Downloading 7 years of hourly QQQ data...")
bars = client.get_stock_bars(request)
df = bars.df.reset_index()
df.to_csv("/Users/colindayer/nas100_backtest/qqq_hourly_7y.csv", index=False)
print(f"Saved {len(df)} bars to qqq_hourly_7y.csv")
print(df.head())
