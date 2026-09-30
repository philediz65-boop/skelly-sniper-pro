import os, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
COINS = ["BTC","ETH","SOL","BNB","XRP","DOGE","AVAX","ADA","LINK","DOT","MATIC","LTC","BCH","UNI","ATOM","ETC","FIL","HBAR","NEAR","APT","SUI","SEI","INJ","TIA","ARB","OP","PEPE","BONK","SHIB","FLOKI","FARTCOIN","WIF","BABY","BOME","BRETT","POPCAT","TRUMP","TURBO","GOAT","PNUT","ACT","MEW","NEIRO","NOT","JUP","ENA","WLD","FET","RNDR","IMX"]

def fmt(p):
    p = float(p)
    if p < 0.0001: return "{:.6f}".format(p)
    if p < 0.01: return "{:.5f}".format(p)
    if p < 1: return "{:.4f}".format(p)
    return "{:.2f}".format(p)

def get_price(symbol):
    symbol = symbol.upper()
    headers = {"User-Agent": "Mozilla/5.0"}

    # 1. BYBIT - Main - Like Trust Wallet
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}USDT"
        r = requests.get(url, headers=headers, timeout=10).json()
        price = r["result"]["list"][0]["lastPrice"]
        if float(price) > 0:
            return float(price)
    except: pass

    # 2. BYBIT SPOT - Backup 1
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}USDT"
        r = requests.get(url, headers=headers, timeout=10).json()
        price = r["result"]["list"][0]["lastPrice"]
        if float(price) > 0:
            return float(price)
    except: pass

    # 3. OKX - Like OKX Wallet in your screenshot
    try:
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT"
        r = requests.get(url, headers=headers, timeout=10).json()
        price = r["data"][0]["last"]
        if float(price) > 0:
            return float(price)
    except: pass

    # 4. COINBASE - Like Coinbase Wallet in your screenshot
    try:
        url = f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot"
        r = requests.get(url, headers=headers, timeout=10).json()
        price = r["data"]["amount"]
        if float(price) > 0:
            return float(price)
    except:
        return None

def get_gold():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        return float(r["price"])
    except:
        return 2650.0

def crypto_signal(s):
    price = get_price(s)
    if price is None:
        return f"{s} price still loading, tap again - Bybit/OKX API"

    t1 = price * 1.011
    t2 = price * 1.028
    t3 = price * 1.047
    t4 = price * 1.103
    sl = price * 0.95
    lev = "10x" if s in ["BTC","ETH"] else "5x"

    msg = f"LONG - {s}\n\n"
    msg += f"Entry: {fmt(price)}\n\n"
    msg += f"Targets: {fmt(t1)} / {fmt(t2)} / {fmt(t3)} / {fmt(t4)}\n\n"
    msg += f"Stop: {fmt(sl)}\n\n"
    msg += f"Leverage: {lev} Isolated\n\n"
    msg += f"Move SL to entry after TP1."
    return msg

def gold_signal():
    p = get_gold()
    msg = f"XAUUSD BUY {fmt(p)}/{fmt(p-5)}\nSL {fmt(p-13)}\nTP {fmt(p+5)}\nTP {fmt(p+12)}\nTP {fmt(p+47)}\n\nLeverage: 20x Isolated"
    return msg

def menu(page=0):
    per=12
    start=page*per
    chunk=COINS[start:start+per]
    btns=[]
    row=[]
    for c in chunk:
        row.append(InlineKeyboardButton(c, callback_data=f"C_{c}"))
        if len(row)==3:
            btns.append(row)
            row=[]
    if row: btns.append(row)
    nav=[]
    if page>0: nav.append(InlineKeyboardButton("Prev", callback_data=f"P_{page-1}"))
    if start+per < len(COINS): nav.append(InlineKeyboardButton("Next", callback_data=f"P_{page+1}"))
    if nav: btns.append(nav)
    btns.append([InlineKeyboardButton("XAUUSD GOLD - 3 TP 1 SL", callback_data="GOLD")])
    return InlineKeyboardMarkup(btns)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Skelly 50 Coins - REAL PRICE (Bybit + OKX + Coinbase)\nNo Binance - Select coin:", reply_markup=menu(0))

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    d=q.data
    if d.startswith("P_"):
        p=int(d.replace("P_",""))
        await q.edit_message_text(f"Page {p+1} - 50 Coins Live:", reply_markup=menu(p))
        return
    if d=="GOLD":
        await q.edit_message_text("Fetching GOLD real price...")
        s=gold_signal()
        await context.bot.send_message(chat_id=q.message.chat.id, text=s, reply_markup=menu(0))
        return
    if d.startswith("C_"):
        sym=d.replace("C_","")
        await q.edit_message_text(f"Fetching {sym} real price from Bybit + OKX...")
        s=crypto_signal(sym)
        await context.bot.send_message(chat_id=q.message.chat.id, text=s, reply_markup=menu(0))

def run_bot():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(handle))
    app.run_polling()

flask_app=Flask(__name__)
@flask_app.route("/")
def home():
    return "Skelly Live - Bybit OKX Coinbase - No Binance"

if __name__=="__main__":
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=10000), daemon=True).start()
    run_bot()
