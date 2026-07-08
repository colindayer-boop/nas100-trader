import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

# Use same settings as before but limit to 2 years for speed
TICKERS = {
    "QQQ": "QQQ",
    "^FCHI": "CAC40",
    "^GDAXI": "DAX",
    "^N225": "NIKKEI",
    "^HSI": "HSI",
    "^KS11": "KOSPI",
}
END_DATE   = str(date.today())
START_DATE = str(date.today() - timedelta(days=2*365))

COST_BPS = {"QQQ":6,"CAC40":8,"DAX":8,"NIKKEI":10,"HSI":10,"KOSPI":10}

def download_daily(ticker,start,end):
    df=yf.download(ticker,start=start,end=end,progress=False,auto_adjust=True)
    if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
    df=df[["Open","High","Low","Close","Volume"]].dropna()
    df.index=pd.to_datetime(df.index);df["Date"]=df.index.date
    return df

def load_all_data():
    data={}
    for ticker,name in TICKERS.items():
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
    asian_low=df["Low"].where((df.index.hour>=18)|(df.index.hour<2)).ffill().shift(1)
    sig=np.where(df["Low"]<asian_low,1,
           np.where(df["Close"]>asian_low.shift(1),-1,0))
    return pd.Series(sig,index=df.index)
def signal_S2(df):
    df=df.copy()
    delta=df["Close"].diff()
    up=delta.clip(lower=0)
    down=-delta.clip(upper=0)
    ma_up=up.ewm(com=13,adjust=False).mean()
    ma_down=down.ewm(com=13,adjust=False).mean()
    rsi=100-(100/(1+ma_up/ma_down))
    sig=np.where(rsi<30,1,np.where(rsi>70,-1,0))
    return pd.Series(sig,index=df.index)
def signal_S3(df):
    df=df.copy()
    rng=df["High"]-df["Low"]
    avg_rng=rng.rolling(20).mean()
    breakout=rng>1.5*avg_rng
    direction=np.sign(df["Close"]-df["Open"])
    sig=np.where(breakout&(direction>0),1,
           np.where(breakout&(direction<0),-1,0))
    return pd.Series(sig,index=df.index)
def signal_S4(df):
    df=df.copy()
    ema_fast=df["Close"].ewm(span=20,adjust=False).mean()
    ema_slow=df["Close"].ewm(span=50,adjust=False).mean()
    sig=np.where(ema_fast>ema_slow,1,
           np.where(ema_fast<ema_slow,-1,0))
    return pd.Series(sig,index=df.index)
def signal_S5(df):
    df=df.copy()
    prev_high=df["High"].shift(1)
    prev_low=df["Low"].shift(1)
    sig=np.where(df["Open"]>prev_high,1,
           np.where(df["Open"]<prev_low,-1,0))
    return pd.Series(sig,index=df.index)

STRATEGY_FUNCS={"S1":signal_S1,"S2":signal_S2,"S3":signal_S3,"S4":signal_S4,"S5":signal_S5}

def build_net_ret(data):
    all_ret=[]
    for m,df in data.items():
        ret=np.log(df["Close"]/df["Close"].shift(1)).fillna(0)
        cost=COST_BPS.get(m,8)/10000
        for st,func in STRATEGY_FUNCS.items():
            sig=func(df).fillna(0)
            turn=(sig.diff().abs()).fillna(0)
            all_ret.append(pd.Series(sig*ret-turn*cost,name=f"{m}_{st}",index=df.index))
    return pd.concat(all_ret,axis=1).sort_index()

def vol_weights(ret_df,target_vol=0.12,lookback=63,max_leverage=2.0):
    vol=ret_df.rolling(lookback).std()*np.sqrt(252)
    inv_vol=1.0/vol.replace(0,np.nan)
    raw_w=inv_vol.div(inv_vol.sum(axis=1),axis=0)
    port_vol=(raw_w*vol).fillna(0).sum(axis=1)
    scale=(target_vol/port_vol).replace([np.inf,-np.inf],1.0).clip(upper=max_leverage)
    w=raw_w.mul(scale,axis=0)
    w=w.div(w.sum(axis=1),axis=0).fillna(0)
    return w

data=load_all_data()
ret=build_net_ret(data)
print("Return matrix shape:",ret.shape)
w=vol_weights(ret)
print("Weights shape:",w.shape)
print("Last 5 weights:")
print(w.tail())
port_ret=(w*ret).sum(axis=1)
cum=(1+port_ret).cumprod()
print("Cumulative return last:",cum.iloc[-1])
print("Cumulative return first:",cum.iloc[0])
# Compute metrics
ann=252
strat_ret=port_ret
total_ret=cum.iloc[-1]/cum.iloc[0]-1
years=(ret.index[-1]-ret.index[0]).days/365.25
cagr=(1+total_ret)**(1/years)-1 if years>0 else np.nan
vol_ann=np.sqrt(ann)*strat_ret.std()
sharpe=(np.sqrt(ann)*strat_ret.mean())/vol_ann if vol_ann!=0 else np.nan
down=strat_ret[strat_ret<0]
down_dev=np.sqrt(ann)*down.std() if len(down)>0 else np.nan
sortino=(np.sqrt(ann)*strat_ret.mean())/down_dev if down_dev and down_dev>0 else np.nan
roll_max=cum.cummax()
dd=(cum-roll_max)/roll_max
max_dd=dd.min()
calmar=-cagr/max_dd if max_dd!=0 else np.nan
var_95=np.percentile(strat_ret,5)
cvar_95=strat_ret[strat_ret<=var_95].mean()
tail=np.percentile(strat_ret,95)/abs(np.percentile(strat_ret,5)) if np.percentile(strat_ret,5)!=0 else np.nan
print("=== Performance (approx full-sample) ===")
print(f"CAGR: {cagr:.2%}")
print(f"Ann. Vol: {vol_ann:.2%}")
print(f"Sharpe: {sharpe:.2f}")
print(f"Sortino: {sortino:.2f}")
print(f"Max DD: {max_dd:.2%}")
print(f"Calmar: {calmar:.2f}")
print(f"VaR 95%: {var_95:.4f}")
print(f"CVaR 95%: {cvar_95:.4f}")
print(f"Tail Ratio: {tail:.2f}")