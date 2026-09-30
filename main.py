import os, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
COINS = ["BTC","ETH","SOL","BNB","XRP","DOGE","AVAX","ADA","LINK","DOT","MATIC","LTC","BCH","UNI","ATOM","ETC","FIL","HBAR","NEAR","APT","SUI","SEI","INJ","TIA","ARB","OP","PEPE","BONK","SHIB","FLOKI","FARTCOIN","WIF","BABY","BOME","BRETT","POPCAT","TRUMP","TURBO","GOAT","PNUT","ACT","MEW","NEIRO","NOT","JUP","ENA","WLD","FET","RNDR","IMX"]

def fmt(p):
    if p < 0.0001:
        return "{:.6f}".format(p)
    if p < 0.01:
        return "{:.5f}".format(p)
    if p < 1:
        return "{:.4f}".format(p)
    return "{:.2f}".format(p)

def get_price(s):
    try:
        u = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=" + s + "USDT"
        r = requests.get(u, timeout=10).json()
        return float(r["result"]["list"][0]["lastPrice"])
    except:
        try:
            u = "https://api.binance.com/api/v3/ticker/price?symbol=" + s + "USDT"
            r = requests.get(u, timeout=10).json()
            return float(r["price"])
        except:
            return None

def get_gold():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        return float(r["price"])
    except:
        return 4153.0

def crypto_signal(s):
    price = get_price(s)
    if price is None:
        return s + " price not found. Try BTC ETH SOL FARTCOIN"
    t1 = price * 1.011
    t2 = price * 1.028
    t3 = price * 1.047
    t4 = price * 1.103
    sl = price * 0.95
    lev = "10x" if s in ["BTC","ETH"] else "5x"
    msg = "LONG - " + s + "\n\n"
    msg += "Entry: " + fmt(price) + "\n\n"
    msg += "Targets: " + fmt(t1) + " / " + fmt(t2) + " / " + fmt(t3) + " / " + fmt(t4) + "\n\n"
    msg += "Stop: " + fmt(sl) + "\n\n"
    msg += "Leverage: " + lev + " Isolated\n\n"
    msg += "Move SL to entry after TP1."
    return msg

def gold_signal():
    p = get_gold()
    msg = "XAUUSD BUY " + fmt(p) + "/" + fmt(p-5) + "\n"
    msg += "SL " + fmt(p-13) + "\n"
    msg += "TP " + fmt(p+5) + "\n"
    msg += "TP " + fmt(p+12) + "\n"
    msg += "TP " + fmt(p+47) + "\n\n"
    msg += "Leverage: 20x Isolated"
    return msg

def menu(page):
    per = 12
    start = page * per
    chunk = COINS[start:start+per]
    btns = []
    row = []
    for c in chunk:
        row.append(InlineKeyboardButton(c, callback_data="C_" + c))
        if len(row) == 3:
            btns.append(row)
            row = []
    if len(row) > 0:
        btns.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("Prev", callback_data="P_" + str(page-1)))
    if start + per < len(COINS):
        nav.append(InlineKeyboardButton("Next", callback_data="P_" + str(page+1)))
    if len(nav) > 0:
        btns.append(nav)
    btns.append([InlineKeyboardButton("XAUUSD GOLD - 3 TP 1 SL", callback_data="GOLD")])
    return InlineKeyboardMarkup(btns)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Skelly 50 Coins - REAL PRICE Live - Select:", reply_markup=menu(0))

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d.startswith("P_"):
        p = int(d.replace("P_", ""))
        await q.edit_message_text("Page " + str(p+1) + " - 50 Coins:", reply_markup=menu(p))
        return
    if d == "GOLD":
        await q.edit_message_text("Fetching GOLD real price...")
        s = gold_signal()
        await context.bot.send_message(chat_id=q.message.chat.id, text=s, reply_markup=menu(0))
        return
    if d.startswith("C_"):
        sym = d.replace("C_", "")
        await q.edit_message_text("Fetching " + sym + " real price...")
        s = crypto_signal(sym)
        await context.bot.send_message(chat_id=q.message.chat.id, text=s, reply_markup=menu(0))

def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle))
    app.run_polling()

flask_app = Flask(__name__)
@flask_app.route("/")
def home():
    return "Skelly Bot Live"

if __name__ == "__main__":
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=10000), daemon=True).start()
    run_bot()
