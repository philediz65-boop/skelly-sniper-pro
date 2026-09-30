import os, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
COINS = ["BTC","ETH","SOL","BNB","XRP","DOGE","AVAX","ADA","LINK","DOT","MATIC","LTC","BCH","UNI","ATOM","ETC","FIL","HBAR","NEAR","APT","SUI","SEI","INJ","TIA","ARB","OP","PEPE","BONK","SHIB","FLOKI","FARTCOIN","WIF","BABY","BOME","BRETT","POPCAT","TRUMP","TURBO","GOAT","PNUT","ACT","MEW","NEIRO","NOT","JUP","ENA","WLD","FET","RNDR","IMX"]

def fmt(p):
    p=float(p)
    if p<0.0001:
        return "{:.6f}".format(p)
    if p<0.01:
        return "{:.5f}".format(p)
    if p<1:
        return "{:.4f}".format(p)
    return "{:.2f}".format(p)

def get_price(symbol):
    symbol=symbol.upper()
    headers={"User-Agent":"Mozilla/5.0"}
    try:
        url=f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}USDT"
        r=requests.get(url,headers=headers,timeout=10).json()
        price=r["result"]["list"][0]["lastPrice"]
        if float(price)>0:
            return float(price)
    except:
        pass
    try:
        url=f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}USDT"
        r=requests.get(url,headers=headers,timeout=10).json()
        price=r["result"]["list"][0]["lastPrice"]
        if float(price)>0:
            return float(price)
    except:
        pass
    try:
        url=f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT"
        r=requests.get(url,headers=headers,timeout=10).json()
        return float(r["data"][0]["last"])
    except:
        pass
    try:
        url=f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"
        r=requests.get(url,headers=headers,timeout=10).json()
        return float(r["data"]["amount"])
    except:
        return None

def get_gold():
    headers={"User-Agent":"Mozilla/5.0"}
    try:
        url="https://api.bybit.com/v5/market/tickers?category=spot&symbol=PAXGUSDT"
        r=requests.get(url,headers=headers,timeout=10).json()
        price=float(r["result"]["list"][0]["lastPrice"])
        if price>0:
            return price
    except:
        pass
    try:
        url="https://www.okx.com/api/v5/market/ticker?instId=PAXG-USDT"
        r=requests.get(url,headers=headers,timeout=10).json()
        return float(r["data"][0]["last"])
    except:
        pass
    try:
        r=requests.get("https://data-asg.goldprice.org/dbXRates/USD",headers=headers,timeout=10).json()
        return float(r["items"][0]["xauPrice"])
    except:
        return 4183.64

def get_klines(symbol, category="linear"):
    headers={"User-Agent":"Mozilla/5.0"}
    try:
        url=f"https://api.bybit.com/v5/market/kline?category={category}&symbol={symbol}USDT&interval=60&limit=100"
        r=requests.get(url,headers=headers,timeout=15).json()
        klines=r["result"]["list"][::-1]
        closes=[float(k[4]) for k in klines]
        return closes
    except:
        return []

def calc_ema(prices, period):
    if len(prices)<period:
        return None
    k=2/(period+1)
    ema=prices[0]
    for p in prices[1:]:
        ema=p*k+ema*(1-k)
    return ema

def calc_sma(prices, period):
    if len(prices)<period:
        return None
    return sum(prices[-period:])/period

def calc_rsi(prices, period=14):
    if len(prices)<period+1:
        return 50
    gains=0
    losses=0
    for i in range(1, period+1):
        diff=prices[-i]-prices[-i-1]
        if diff>=0:
            gains+=diff
        else:
            losses+=-diff
    if losses==0:
        return 70
    rs=gains/losses
    return 100-(100/(1+rs))

def get_market_signal(symbol):
    closes=get_klines(symbol, "linear")
    if len(closes)<50:
        closes=get_klines(symbol, "spot")
    if len(closes)<50:
        return "LONG", 50, 0, 0
    ema20=calc_ema(closes,20)
    ema50=calc_ema(closes,50)
    sma50=calc_sma(closes,50)
    rsi=calc_rsi(closes,14)
    if rsi <= 30:
        direction="LONG"
    elif rsi >= 70:
        direction="SHORT"
    elif ema20 and ema50:
        if ema20 > ema50 * 1.002:
            direction="LONG"
        elif ema20 < ema50 * 0.998:
            direction="SHORT"
        else:
            direction="LONG" if closes[-1] > sma50 else "SHORT"
    else:
        direction="LONG" if closes[-1] > sma50 else "SHORT"
    return direction, rsi, ema20, ema50

def crypto_signal(symbol):
    price=get_price(symbol)
    if price is None:
        return f"{symbol} price loading, tap again"
    direction, rsi, ema20, ema50 = get_market_signal(symbol)
    lev="5x / 200x"
    if direction=="LONG":
        t1=price*1.011
        t2=price*1.028
        t3=price*1.047
        t4=price*1.103
        sl=price*0.95
    else:
        t1=price*0.989
        t2=price*0.972
        t3=price*0.953
        t4=price*0.897
        sl=price*1.05
    ema20_str = fmt(ema20) if ema20 else "N/A"
    ema50_str = fmt(ema50) if ema50 else "N/A"
    msg = f"{direction} - {symbol}\n\nEntry: {fmt(price)}\n\nTargets: {fmt(t1)} / {fmt(t2)} / {fmt(t3)} / {fmt(t4)}\n\nStop: {fmt(sl)}\n\nLeverage: {lev} Isolated\n\nTA: RSI {rsi:.1f} | EMA20 {ema20_str} | EMA50 {ema50_str}\nMove SL to entry after TP1."
    return msg

def gold_signal():
    p=get_gold()
    closes=get_klines("PAXG","spot")
    if len(closes)>20:
        rsi=calc_rsi(closes,14)
        ema20=calc_ema(closes,20)
        ema50=calc_ema(closes,50)
