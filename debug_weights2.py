#!/usr/bin/env python
# -*- coding: utf-8 -*-
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import date

TICKERS = {
    "QQQ": "QQQ",
    "^FCHI": "CAC40",
    "^GDAXI": "DAX",
    "^N225": "NIKKEI",
    "^HSI": "HSI",
    "^KS11": "KOSPI",
}
START_DATE = "2000-01-01"
END_DATE   = str(date.today())
def download_daily(ticker, start, end):
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open","High","Low","Close","Volume"]].dropna()
    df.index = pd.to_datetime(df.index)
    df["Date"] = df.index.date
    return df
def load_all_data():
    data={}
    for ticker,name in TICKERS.items():
        print(f"Downloading {ticker} ({name})")
        data[name]=download_daily(ticker,START_DATE,END_DATE)
    all_dates=pd.date_range(start=min(df.index.min() for df in data.values()),
                            end=max(df.index.max() for df in data.values()),
                            freq="B")
    aligned={}
    for name,df in data.items():
        df=df.reindex(all_dates).ffill()
        df["Date"]=df.index.date
        aligned[name]=df
    return aligned
def signal_S1(df):
    df=df.copy()
    asian_low = df["Low"].where((df.index.hour >= 18) | (df.index.hour < 2)).ffill().shift(1)
    signal = np.where(df["Low"] < asian_low, 1,
               np.where(df["Close"] > asian_low.shift(1), -1, 0))
    return pd.Series(signal, index=df.index)
def build_net_return_matrix(data):
    all_ret=[]
    for market,df in data.items():
        ret=np.log(df["Close"]/df["Close"].shift(1)).fillna(0)
        cost_bps = {"QQQ":6,"CAC40":8,"DAX":8,"NIKKEI":10,"HSI":10,"KOSPI":10}.get(market,8)
        cost_ret=cost_bps/10000
        for strat_name,func in [("S1",signal_S1)]:
            sig=func(df).fillna(0)
            turnover=(sig.diff().abs()).fillna(0)
            net=sig*ret - turnover*cost_ret
            col_name=f"{market}_{strat_name}"
            all_ret.append(pd.Series(net,name=col_name,index=df.index))
    return pd.concat(all_ret,axis=1).sort_index()
def vol_target_weights(ret_df,target_vol=0.12,lookback=63,max_leverage=2.0):
    vol=ret_df.rolling(lookback).std()*np.sqrt(252)
    print("vol sample:", vol.iloc[70:75].values)
    inv_vol=1.0/vol.replace(0,np.nan)
    print("inv_vol sample:", inv_vol.iloc[70:75].values)
    raw_w=inv_vol.div(inv_vol.sum(axis=1),axis=0)
    print("raw_w sample:", raw_w.iloc[70:75].values)
    port_vol=(raw_w*vol).fillna(0).sum(axis=1)
    print("port_vol sample:", port_vol.iloc[70:75].values)
    scale=(target_vol/port_vol).replace([np.inf,-np.inf],1.0).clip(upper=max_leverage)
    print("scale sample:", scale.iloc[70:75].values)
    weights=raw_w.mul(scale,axis=0)
    print("weights sample:", weights.iloc[70:75].values)
    weights=weights.div(weights.sum(axis=1),axis=0).fillna(0)
    print("weights after norm sample:", weights.iloc[70:75].values)
    return weights
data=load_all_data()
ret=build_net_return_matrix(data)
print("Return dataframe shape:",ret.shape)
print(ret.head())
w=vol_target_weights(ret)
print("Weights shape:",w.shape)
print("First non-zero weight row:")
print((w!=0).any(axis=1))
print("First row with any non-zero weight:")
print(w[(w!=0).any(axis=1)].head())