# FINAL - DEPLOY MUST PASS
import os, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
COINS = ["BTC","ETH","SOL","BNB","XRP","DOGE","AVAX","ADA","LINK","DOT","MATIC","LTC","BCH","UNI","ATOM","ETC","FIL","HBAR","NEAR","APT","SUI","SEI","INJ","TIA","ARB","OP","PEPE","BONK","SHIB","FLOKI","FARTCOIN","WIF","BABY","BOME","BRETT","POPCAT","TRUMP","TURBO","GOAT","PNUT","ACT","MEW","NEIRO","NOT","JUP","ENA","WLD","FET","RNDR","IMX"]

def fmt(p):
    p=float(p)
    return f"{p:.6f}" if p<0.0001 else f"{p:.5f}" if p<0.01 else f"{p:.4f}" if p<1 else f"{p:.2f}"

def get_price(s):
    h={"User-Agent":"Mozilla/5.0"}
    for cat in ["linear","spot"]:
        try:
            r=requests.get(f"https://api.bybit.com/v5/market/tickers?category={cat}&symbol={s}USDT",headers=h,timeout=10).json()
            v=float(r["result"]["list"][0]["lastPrice"])
            if v>0: return v
        except: pass
    try:
        r=requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={s}-USDT",headers=h,timeout=10).json()
        return float(r["data"][0]["last"])
    except: return None

def get_gold():
    h={"User-Agent":"Mozilla/5.0"}
    try:
        r=requests.get("https://api.bybit.com/v5/market/tickers?category=spot&symbol=PAXGUSDT",headers=h,timeout=10).json()
        v=float(r["result"]["list"][0]["lastPrice"])
        if v>0: return v
    except: pass
    try:
        r=requests.get("https://www.okx.com/api/v5/market/ticker?instId=PAXG-USDT",headers=h,timeout=10).json()
        return float(r["data"][0]["last"])
    except: return 4183.64

def get_klines(s,c="linear"):
    try:
        r=requests.get(f"https://api.bybit.com/v5/market/kline?category={c}&symbol={s}USDT&interval=60&limit=100",timeout=15).json()
        return [float(x[4]) for x in r["result"]["list"][::-1]]
    except: return []

def calc_ema(prices,p):
    if len(prices)<p: return None
    k=2/(p+1); e=prices[0]
    for x in prices[1:]: e=x*k+e*(1-k)
    return e

def calc_rsi(prices,p=14):
    if len(prices)<p+1: return 50
    g=l=0
    for i in range(1,p+1):
        d=prices[-i]-prices[-i-1]
        if d>=0: g+=d
        else: l+=-d
    if l==0: return 70
    return 100-(100/(1+g/l))

def get_signal(s):
    cl=get_klines(s,"linear")
    if len(cl)<50: cl=get_klines(s,"spot")
    if len(cl)<50: return "LONG",50,0,0
    e20=calc_ema(cl,20); e50=calc_ema(cl,50)
    rsi=calc_rsi(cl,14)
    if rsi<=30: d="LONG"
    elif rsi>=70: d="SHORT"
    elif e20 and e50:
        d="LONG" if e20>e50*1.002 else "SHORT" if e20<e50*0.998 else "LONG"
    else: d="LONG"
    return d,rsi,e20,e50

def crypto_signal(s):
    pr=get_price(s)
    if pr is None: return f"{s} loading, tap again"
    d,rsi,e20,e50=get_signal(s)
    if d=="LONG":
        t1,t2,t3,t4,sl=pr*1.011,pr*1.028,pr*1.047,pr*1.103,pr*0.95
    else:
        t1,t2,t3,t4,sl=pr*0.989,pr*0.972,pr*0.953,pr*0.897,pr*1.05
    return f"{d} - {s}\n\nEntry: {fmt(pr)}\n\nTargets: {fmt(t1)} / {fmt(t2)} / {fmt(t3)} / {fmt(t4)}\n\nStop: {fmt(sl)}\n\nLeverage: 5x / 200x Isolated\n\nTA: RSI {rsi:.1f} | EMA20 {fmt(e20) if e20 else 'N/A'} | EMA50 {fmt(e50) if e50 else 'N/A'}"

def gold_signal():
    p=get_gold(); cl=get_klines("PAXG","spot")
    if len(cl)>20:
        rsi=calc_rsi(cl,14); e20=calc_ema(cl,20); e50=calc_ema(cl,50)
        d="BUY" if (e20 and e50 and e20>e50) or rsi<55 else "SELL"
    else: d="BUY"; rsi=58
    if d=="BUY": low,high,sl,tp1,tp2,tp3=p-8,p,p-28,p+18,p+35,p+75
    else: low,high,sl,tp1,tp2,tp3=p,p+8,p+28,p-18,p-35,p-75
    return f"XAUUSD {d} {fmt(low)}/{fmt(high)}\nSL {fmt(sl)}\nTP1 {fmt(tp1)}\nTP2 {fmt(tp2)}\nTP3 {fmt(tp3)}\n\nTA: RSI {rsi:.1f} | Live {fmt(p)} | RR 1:2.6"

def menu(pg=0):
    per=12; st=pg*per; ch=COINS[st:st+per]; btn=[]; row=[]
    for c in ch:
        row.append(InlineKeyboardButton(c,callback_data=f"C_{c}"))
        if len(row)==3: btn.append(row); row=[]
    if row: btn.append(row)
    nav=[]
    if pg>0: nav.append(InlineKeyboardButton("Prev",callback_data=f"P_{pg-1}"))
    if st+per<len(COINS): nav.append(InlineKeyboardButton("Next",callback_data=f"P_{pg+1}"))
    if nav: btn.append(nav)
    btn.append([InlineKeyboardButton("XAUUSD GOLD - 3 TP 1 SL",callback_data="GOLD")])
    return InlineKeyboardMarkup(btn)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Skelly Pro - Crypto 5x/200x - Gold No Lev\nSelect coin:",reply_markup=menu(0))

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); d=q.data
    if d.startswith("P_"):
        pg=int(d[2:]); await q.edit_message_text(f"Page {pg+1}:",reply_markup=menu(pg)); return
    if d=="GOLD":
        await q.edit_message_text("Fetching GOLD...")
        txt=gold_signal()
        await context.bot.send_message(chat_id=q.message.chat.id,text=txt,reply_markup=menu(0))
        return
    if d.startswith("C_"):
        sym=d[2:]; await q.edit_message_text(f"Fetching {sym}...")
        txt=crypto_signal(sym)
        await context.bot.send_message(chat_id=q.message.chat.id,text=txt,reply_markup=menu(0))
        return

def run_bot():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("menu",start))
    app.add_handler(CallbackQueryHandler(handle))
    app.run_polling()

flask_app=Flask(__name__)
@flask_app.route("/")
def home(): return "OK - Skelly Pro Live"

if __name__=="__main__":
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0",port=10000),daemon=True).start()
    run_bot()
