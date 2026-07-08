import pandas as pd, numpy as np
# reuse from earlier
import warnings
warnings.filterwarnings("ignore")
import yfinance as yf
from datetime import date

TICKERS={"QQQ":"QQQ","^FCHI":"CAC40","^GDAXI":"DAX","^N225":"NIKKEI","^HSI":"HSI","^KS11":"KOSPI"}
START_DATE="2000-01-01"
END_DATE=str(date.today())
def download_daily(ticker,start,end):
    df=yf.download(ticker,start=start,end=end,progress=False,auto_adjust=True)
    if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
    df=df[["Open","High","Low","Close","Volume"]].dropna()
    df.index=pd.to_datetime(df.index);df["Date"]=df.index.date
    return df
data={}
for t,name in TICKERS.items():
    data[name]=download_daily(t,START_DATE,END_DATE)
all_dates=pd.date_range(start=min(df_.index.min() for df_ in data.values()),end=max(df_.index.max() for df_ in data.values()),freq="B")
for n,df in data.items():
    df=df.reindex(all_dates).ffill()
    df["Date"]=df.index.date
    data[n]=df
def signal_S1(df):
    df=df.copy()
    asian_low=df["Low"].where((df.index.hour>=18)|(df.index.hour<2)).ffill().shift(1)
    sig=np.where(df["Low"]<asian_low,1,
           np.where(df["Close"]>asian_low.shift(1),-1,0))
    return pd.Series(sig,index=df.index)
all_ret=[]
for m,df in data.items():
    ret=np.log(df["Close"]/df["Close"].shift(1)).fillna(0)
    cost={"QQQ":6,"CAC40":8,"DAX":8,"NIKKEI":10,"HSI":10,"KOSPI":10}.get(m,8)/10000
    sig=signal_S1(df)
    turn=(sig.diff().abs()).fillna(0)
    all_ret.append(pd.Series(sig*ret-turn*cost,name=f"{m}_S1",index=df.index))
ret=pd.concat(all_ret,axis=1)
print("Ret shape:",ret.shape)
# define functions as in ensemble
def vol_target_weights(ret_df,target_vol=0.12,lookback=63,max_leverage=2.0):
    vol=ret_df.rolling(lookback).std()*np.sqrt(252)
    inv_vol=1.0/vol.replace(0,np.nan)
    raw_w=inv_vol.div(inv_vol.sum(axis=1),axis=0)
    port_vol=(raw_w*vol).fillna(0).sum(axis=1)
    scale=(target_vol/port_vol).replace([np.inf,-np.inf],1.0).clip(upper=max_leverage)
    weights=raw_w.mul(scale,axis=0)
    weights=weights.div(weights.sum(axis=1),axis=0).fillna(0)
    return weights
def walk_forward_returns(ret_df,n_splits=5,purge_days=5):
    n=len(ret_df)
    split_size=n//n_splits
    equity=[1.0]
    dates=[ret_df.index[0]]
    for i in range(n_splits):
        train_end=(i+1)*split_size
        test_start=train_end+purge_days
        test_end=min((i+2)*split_size,n)
        if test_start>=n:
            break
        train=ret_df.iloc[:train_end]
        test=ret_df.iloc[test_start:test_end]
        w=vol_target_weights(train)
        w_test=w.reindex(test.index).ffill().fillna(0)
        port_ret=(w_test*test).sum(axis=1)
        daily_growth=1+port_ret
        equity.extend((equity[-1]*daily_growth).tolist())
        dates.extend(test.index.tolist())
    return pd.Series(equity,index=pd.to_datetime(dates))
eq=walk_forward_returns(ret)
print("Equity tail:",eq.tail())
print("Equity head:",eq.head())
print("Length equity:",len(eq))
print("Unique values in equity (first 10):",eq.unique()[:10])