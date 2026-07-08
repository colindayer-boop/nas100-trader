import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date

# Use same settings as ensemble_backtest
TICKERS = {"QQQ":"QQQ","^FCHI":"CAC40","^GDAXI":"DAX","^N225":"NIKKEI","^HSI":"HSI","^KS11":"KOSPI"}
START_DATE="2000-01-01"
END_DATE=str(date.today())
def download_daily(ticker,start,end):
    df=yf.download(ticker,start=start,end=end,progress=False,auto_adjust=True)
    if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    df=df[["Open","High","Low","Close","Volume"]].dropna()
    df.index=pd.to_datetime(df.index); df["Date"]=df.index.date
    return df
data={}
for t,name in TICKERS.items():
    data[name]=download_daily(t,START_DATE,END_DATE)
# align
all_dates=pd.date_range(start=min(df.index.min() for df in data.values()),end=max(df.index.max() for df in data.values()),freq="B")
for name,df in data.items():
    df=df.reindex(all_dates).ffill()
    df["Date"]=df.index.date
    data[name]=df

# compute returns
ret_df_list=[]
for market,df in data.items():
    ret=np.log(df["Close"]/df["Close"].shift(1)).fillna(0)
    cost_bps={"QQQ":6,"CAC40":8,"DAX":8,"NIKKEI":10,"HSI":10,"KOSPI":10}.get(market,8)
    cost=cost_bps/10000
    # simple signal: +1 if close>open else -1 (just for test)
    sig=np.where(df["Close"]>df["Open"],1,-1)
    turnover=pd.Series(sig,index=df.index).diff().abs().fillna(0)
    net=sig*ret - turnover*cost
    ret_df_list.append(pd.Series(net,name=f"{market}_S1",index=df.index))
ret_df=pd.concat(ret_df_list,axis=1).sort_index()
print("Ret df shape:",ret_df.shape)
print("First few rows:")
print(ret_df.head())
# compute vol target weights
def vol_target_weights(ret_df,target_vol=0.12,lookback=63,max_leverage=2.0):
    vol=ret_df.rolling(lookback).std()*np.sqrt(252)
    inv_vol=1.0/vol.replace(0,np.nan)
    raw_w=inv_vol.div(inv_vol.sum(axis=1),axis=0)
    port_vol=(raw_w*vol).fillna(0).sum(axis=1)
    scale=(target_vol/port_vol).replace([np.inf,-np.inf],1.0).clip(upper=max_leverage)
    weights=raw_w.mul(scale,axis=0)
    weights=weights.div(weights.sum(axis=1),axis=0).fillna(0)
    return weights
w=vol_target_weights(ret_df)
print("\nWeights first 5 rows:")
print(w.head())
print("\nWeights sum per row:")
print(w.sum(axis=1).head())
print("\nPortfolio return first 5:")
port_ret=(w*ret_df).sum(axis=1)
print(port_ret.head())
print("\nCumulative product:")
cum=(1+port_ret).cumprod()
print(cum.head())