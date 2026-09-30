import os, requests, asyncio, logging
import pandas as pd
import numpy as np
import yfinance as yf
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = None

ALL_COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","PEPEUSDT","SHIBUSDT","BABYUSDT","ONDOUSDT","SUIUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","ARBUSDT","ENAUSDT","WIFUSDT","BONKUSDT","FLOKIUSDT","FETUSDT","RENDERUSDT","INJUSDT","TIAUSDT","SEIUSDT","OPUSDT","STRKUSDT"]

def calculate_rsi(s, p=14):
    d=s.diff(); g=(d.where(d>0,0)).rolling(p).mean(); l=(-d.where(d<0,0)).rolling(p).mean(); return 100-(100/(1+g/l))

def get_price(sym):
    h={"User-Agent":"Mozilla/5.0"}; bp=byp=None
    try: r=requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}",headers=h,timeout=5).json(); bp=float(r['price'])
    except: pass
    try: r2=requests.get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={sym}",headers=h,timeout=5).json(); byp=float(r2['result']['list'][0]['lastPrice'])
    except: pass
    return bp or byp,bp,byp

def get_klines(sym, interval="1h"):
    h={"User-Agent":"Mozilla/5.0"}
    try:
        url=f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit=200"
        r=requests.get(url,headers=h,timeout=10); j=r.json()
        df=pd.DataFrame(j,columns=['ot','o','h','l','c','v','ct','qv','t','tbv','tqv','ig'])
        for k in ['o','h','l','c']: df[k]=df[k].astype(float)
        df.rename(columns={'c':'close','h':'high','l':'low','o':'open'},inplace=True)
        real,bp,byp=get_price(sym)
        if real: df.loc[df.index[-1],'close']=real
        return df,bp,byp,real
    except: return None,None,None,None

def get_xau(interval="1h"):
    yf_int="30m" if interval=="30m" else "60m"
    try:
        data=yf.download("GC=F",period="5d",interval=yf_int,progress=False)
        if data.empty: data=yf.download("XAUUSD=X",period="5d",interval=yf_int,progress=False)
        df=pd.DataFrame(); df['close']=data['Close']; df['high']=data['High']; df['low']=data['Low']; df['open']=data['Open']
        return df,float(df['close'].iloc[-1])
    except: return None,None

def build_signal(df,sym,bp,byp,live,real):
    if df is None or len(df)<50: return None,0
    close=df['close']; rsi=calculate_rsi(close).iloc[-1]
    ema20=close.ewm(span=20).mean().iloc[-1]; ema50=close.ewm(span=50).mean().iloc[-1]
    price=close.iloc[-1]; atr=(df['high']-df['low']).rolling(14).mean().iloc[-1]
    if np.isnan(atr): atr=price*0.015
    score=0
    if rsi<38 and price>ema20 and price>ema50: score=90; sig="LONG —"; setup="Breakout + RSI bounce"
    elif rsi>68 and price<ema20 and price<ema50: score=90; sig="SHORT —"; setup="Breakdown + RSI rejection"
    elif rsi<45 and price>ema50: score=75; sig="LONG —"; setup="Trend continuation"
    elif rsi>55 and price<ema50: score=75; sig="SHORT —"; setup="Bearish momentum"
    else: return None,0
    if score<80 and "XAU" not in sym:
        if score<75: return None,score
    if "SHORT" in sig: sl=price+(atr*1.5); t1=price-(atr*1); t2=price-(atr*2.2); t3=price-(atr*3.5); t4=price-(atr*5)
    else: sl=price-(atr*1.5); t1=price+(atr*1); t2=price+(atr*2.2); t3=price+(atr*3.5); t4=price+(atr*5)
    rr=abs((t2-price)/(price-sl)) if price!=sl else 2.1
    msg=f"""💎 {sig} {sym.replace('USDT','')}

Entry: {price:.5f}
Targets: {t1:.5f} / {t2:.5f} / {t3:.5f} / {t4:.5f}
Stop: {sl:.5f}

Setup: {setup} | R/R ~{rr:.1f}R
📊 RSI: {rsi:.1f} | EMA20:{ema20:.2f} EMA50:{ema50:.2f}
{'🥇 MT5 Gold: '+str(live) if 'XAU' in sym else f'✅ Live: {real} | Binance:{bp} Bybit:{byp}'}"""
    return msg,score

async def auto_scan(context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    if not CHAT_ID: return
    best=[]
    for coin in ALL_COINS:
        df,bp,byp,real=get_klines(coin,"30m")
        msg,score=build_signal(df,coin,bp,byp,None,real)
        if msg and score>=80: best.append((score,msg))
        await asyncio.sleep(0.3)
    df,live=get_xau("30m")
    msg,score=build_signal(df,"XAUUSD",None,None,live,live)
    if msg and score>=75: best.append((score,msg))
    if not best: return
    best.sort(key=lambda x:x[0],reverse=True)
    full="🔥 SKELLY AUTO SCAN 30M\n━━━━━━━━━━━━━━━\n\n"+"\n\n━━━━━━━━━━━━━━━\n\n".join([m for s,m in best[:3]])
    try: await context.bot.send_message(chat_id=CHAT_ID,text=full)
    except: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID; CHAT_ID=update.effective_chat.id
    kb=[[InlineKeyboardButton("🔥 Auto ON",callback_data="scan_on")],[InlineKeyboardButton("₿ BTC",callback_data="BTCUSDT_1h"),InlineKeyboardButton("BABY",callback_data="BABYUSDT_1h"),InlineKeyboardButton("XAU",callback_data="XAUUSD_1h")],[InlineKeyboardButton("📊 Scan Now",callback_data="scan_now")]]
    await update.message.reply_text(f"🔥 SKELLY V6 LIVE\nScanning 26 coins + XAU every 30m\nChat ID saved: {CHAT_ID}\n\nClick Scan Now",reply_markup=InlineKeyboardMarkup(kb))

async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID; q=update.callback_query; await q.answer(); data=q.data; CHAT_ID=q.message.chat_id
    if data=="scan_on": await q.edit_message_text("✅ Auto Scan ON! I go ping you every 30mins for best entries."); return
    if data=="scan_now":
        await q.edit_message_text("⏳ Scanning 26 coins + XAU...")
        await auto_scan(context)
        await q.message.reply_text("✅ Done. If no signal, no perfect setup yet — wait 30m.")
        return
    interval="30m" if "30m" in data else "1h"; sym=data.replace("_30m","").replace("_1h","")
    if "XAU" in sym: df,live=get_xau(interval); msg,_=build_signal(df,"XAUUSD",None,None,live,live)
    else: df,bp,byp,real=get_klines(sym,interval); msg,_=build_signal(df,sym,bp,byp,None,real)
    if not msg: msg=f"⏳ {sym} no perfect entry yet."
    kb=[[InlineKeyboardButton("🔄 Re-Analyze",callback_data=data)],[InlineKeyboardButton("📊 Scan All",callback_data="scan_now")]]
    await q.edit_message_text(msg,reply_markup=InlineKeyboardMarkup(kb))

async def custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t=update.message.text.strip().upper()
    if t.startswith("/"): return
    if "XAU" in t: df,live=get_xau("1h"); msg,_=build_signal(df,"XAUUSD",None,None,live,live)
    else: sym=t if "USDT" in t else t+"USDT"; df,bp,byp,real=get_klines(sym,"1h"); msg,_=build_signal(df,sym,bp,byp,None,real)
    if not msg: msg=f"⏳ {sym} still ranging."
    await update.message.reply_text(msg)

def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,custom))
    app.job_queue.run_repeating(auto_scan,interval=1800,first=60)
    print("V6 LIVE"); app.run_polling()
if __name__=="__main__": main()
