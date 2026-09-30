import os, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")

def ema(p, period):
    k=2/(period+1); e=p[0]
    for x in p[1:]: e=x*k+e*(1-k)
    return e

def rsi(p, period=14):
    g=[]; l=[]
    for i in range(1,len(p)):
        d=p[i]-p[i-1]
        g.append(max(d,0)); l.append(max(-d,0))
    if len(g)<period: return 60
    ag=sum(g[-period:])/period; al=sum(l[-period:])/period
    if al==0: return 65
    return 100-(100/(1+ag/al))

def get_leverage(symbol):
    if symbol in ["BTC","ETH"]: return "10x"
    if symbol in ["SOL","BNB","XRP"]: return "8x"
    return "5x"

def perfect_format(symbol, direction, entry, tps, sl, lev, r, e20, e50):
    emoji="💎" if direction=="LONG" else "🔻"
    action="BUY" if direction=="LONG" else "SELL"
    # 1H time expectations
    tp_time = "TP1: 1-3H | TP2: 4-8H | TP3: 12-24H | TP4: 24-48H"
    sl_time = "SL Break Risk: Low for next 6H if 1H holds"
    return (
        f"{emoji} {direction} — {symbol} [1H Analysis]\n"
        f"Action: {action}\n"
        f"Leverage: {lev} Isolated\n"
        f"Entry: {entry}\n"
        f"Targets: {tps[0]} / {tps[1]} / {tps[2]} / {tps[3]}\n"
        f"Stop: {sl}\n"
        f"⏰ Time Expectation: {tp_time}\n"
        f"⚠️ {sl_time}\n"
        f"Setup: 1H Breakout | RSI {r:.0f} | EMA {e20:.0f}/{e50:.0f} | SL 3.5% > TP 1%\n"
        f"🚀📈 Move SL to entry after TP1 hit (1-3H)"
    )

def get_crypto(symbol):
    try:
        url=f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}USDT&interval=60&limit=100"
        kl=requests.get(url,timeout=15).json()['result']['list']
        closes=[float(k[4]) for k in reversed(kl)]
        p=closes[-1]; r=rsi(closes); e20=ema(closes,20); e50=ema(closes,50)
        direction="LONG" if e20>e50 else "SHORT"
        lev=get_leverage(symbol)
        if direction=="LONG":
            entry=f"{p:.6f}" if p<1 else f"{p:.2f}"
            tps=[f"{p*1.012:.6f}" if p<1 else f"{p*1.012:.2f}", f"{p*1.03:.6f}" if p<1 else f"{p*1.03:.2f}", f"{p*1.05:.6f}" if p<1 else f"{p*1.05:.2f}", f"{p*1.08:.6f}" if p<1 else f"{p*1.08:.2f}"]
            sl=f"{p*0.965:.6f}" if p<1 else f"{p*0.965:.2f}"
        else:
            entry=f"{p:.6f}" if p<1 else f"{p:.2f}"
            tps=[f"{p*0.988:.6f}" if p<1 else f"{p*0.988:.2f}", f"{p*0.97:.6f}" if p<1 else f"{p*0.97:.2f}", f"{p*0.95:.6f}" if p<1 else f"{p*0.95:.2f}", f"{p*0.92:.6f}" if p<1 else f"{p*0.92:.2f}"]
            sl=f"{p*1.035:.6f}" if p<1 else f"{p*1.035:.2f}"
        return perfect_format(symbol, direction, entry, tps, sl, lev, r, e20, e50)
    except:
        try:
            b_url=f"https://api.bitget.com/api/v2/mix/market/candles?symbol={symbol}USDT&productType=USDT-FUTURES&granularity=1H&limit=100"
            kl=requests.get(b_url,timeout=10).json()['data']
            closes=[float(k[4]) for k in reversed(kl)]
            p=closes[-1]; r=rsi(closes); e20=ema(closes,20); e50=ema(closes,50)
            direction="LONG" if e20>e50 else "SHORT"
            lev=get_leverage(symbol)
            entry=f"{p:.2f}"; tps=[f"{p*1.012:.2f}",f"{p*1.03:.2f}",f"{p*1.05:.2f}",f"{p*1.08:.2f}"]; sl=f"{p*0.965:.2f}"
            if direction=="SHORT": tps=[f"{p*0.988:.2f}",f"{p*0.97:.2f}",f"{p*0.95:.2f}",f"{p*0.92:.2f}"]; sl=f"{p*1.035:.2f}"
            return perfect_format(symbol, direction, entry, tps, sl, lev, r, e20, e50)
        except:
            return f"⚠️ {symbol} retry in 5s"

def get_xau():
    try:
        url="https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=60m&range=5d"
        data=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        closes=[c for c in data['chart']['
