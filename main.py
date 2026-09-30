import os, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ===== FORMATTING - SL LONG PASS TP =====
def ema(prices, period):
    k = 2/(period+1); e = prices[0]
    for p in prices[1:]: e = p*k + e*(1-k)
    return e

def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i]-prices[i-1]
        gains.append(max(d,0)); losses.append(max(-d,0))
    ag = sum(gains[-period:])/period
    al = sum(losses[-period:])/period
    if al==0: return 65
    return 100 - (100/(1+ag/al))

def format_signal(pair, direction, entry, tps, stop, extra=""):
    t_str = " / ".join(tps)
    emoji = "💎" if direction=="LONG" else "🔻"
    return f"{emoji} {direction} — {pair}\nEntry: {entry}\nTargets: {t_str}\nStop: {stop}\n{extra}\n🚀📈 Move SL to entry after TP1."

def get_price_analysis(symbol):
    try:
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}USDT&interval=15&limit=100"
        kl = requests.get(url, timeout=10).json()['result']['list']
        closes = [float(k[4]) for k in reversed(kl)]
        r = rsi(closes); e20=ema(closes,20); e50=ema(closes,50); p=closes[-1]
        direction = "LONG" if e20>e50 and p>e20 else "SHORT"
        if direction=="LONG":
            entry=f"{p:.5f}" if p<1 else f"{p:.2f}"
            tps=[f"{p*1.01:.5f}" if p<1 else f"{p*1.01:.2f}", f"{p*1.025:.5f}" if p<1 else f"{p*1.025:.2f}", f"{p*1.04:.5f}" if p<1 else f"{p*1.04:.2f}", f"{p*1.06:.5f}" if p<1 else f"{p*1.06:.2f}"]
            sl=f"{p*0.965:.5f}" if p<1 else f"{p*0.965:.2f}"
        else:
            entry=f"{p:.5f}" if p<1 else f"{p:.2f}"
            tps=[f"{p*0.99:.5f}" if p<1 else f"{p*0.99:.2f}", f"{p*0.975:.5f}" if p<1 else f"{p*0.975:.2f}", f"{p*0.96:.5f}" if p<1 else f"{p*0.96:.2f}", f"{p*0.94:.5f}" if p<1 else f"{p*0.94:.2f}"]
            sl=f"{p*1.035:.5f}" if p<1 else f"{p*1.035:.2f}"
        extra=f"Bybit 15m | RSI {r:.0f} | EMA {e20:.2f}/{e50:.2f} | Wide SL 3.5% > TP1 1%"
        return format_signal(symbol, direction, entry, tps, sl, extra)
    except:
        return f"💎 LONG — {symbol}\nEntry: Market\nTargets: Scanning...\nStop: Wide SL\nBybit live fetch failed, try again."

def get_xau_analysis(pair="XAUUSD"):
    try:
        url="https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=15m&range=1d"
        data=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10).json()
        closes=[c for c in data['chart']['result'][0]['indicators']['quote'][0]['close'] if c]
        p=closes[-1]; r=rsi(closes); e20=ema(closes,20); e50=ema(closes,50)
        direction="LONG" if e20>e50 else "SHORT"
        if direction=="LONG":
            return format_signal("XAUUSD","LONG",f"{p:.2f}",[f"{p+5:.2f}",f"{p+12:.2f}",f"{p+20:.2f}",f"{p+35:.2f}"],f"{p-25:.2f}",f"MT5 GOLD | RSI {r:.0f} | Wide SL $25 > TP1 $5")
        else:
            return format_signal("XAUUSD","SHORT",f"{p:.2f}",[f"{p-5:.2f}",f"{p-12:.2f}",f"{p-20:.2f}",f"{p-35:.2f}"],f"{p+25:.2f}",f"MT5 GOLD | RSI {r:.0f}")
    except:
        return format_signal("XAUUSD","LONG","2655.50",["2660.50","2667.50","2675.50","2690.50"],"2630.50","MT5 GOLD | Demo - Yahoo blocked")

# ===== MENUS =====
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 CRYPTO", callback_data="menu_crypto")],
        [InlineKeyboardButton("🥇 MT5", callback_data="menu_mt5")]
    ])

def crypto_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("BTC", callback_data="coin_BTC"), InlineKeyboardButton("ETH", callback_data="coin_ETH"), InlineKeyboardButton("SOL", callback_data="coin_SOL")],
        [InlineKeyboardButton("BABY", callback_data="coin_BABY"), InlineKeyboardButton("PEPE", callback_data="coin_PEPE"), InlineKeyboardButton("BONK", callback_data="coin_BONK")],
        [InlineKeyboardButton("DOGE", callback_data="coin_DOGE"), InlineKeyboardButton("SHIB", callback_data="coin_SHIB"), InlineKeyboardButton("WIF", callback_data="coin_WIF")],
        [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_main")]
    ])

def mt5_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("XAUUSD (GOLD)", callback_data="mt5_XAUUSD")],
        [InlineKeyboardButton("EURUSD", callback_data="mt5_EURUSD"), InlineKeyboardButton("GBPUSD", callback_data="mt5_GBPUSD")],
        [InlineKeyboardButton("USDJPY", callback_data="mt5_USDJPY"), InlineKeyboardButton("BTCUSD", callback_data="mt5_BTCUSD")],
        [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_main")]
    ])

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Skelly Pro V6\n**SELECT MARKET:**", reply_markup=main_menu())

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    d=q.data

    if d=="menu_crypto":
        await q.edit_message_text("📈 CRYPTO — Click any coin you wan trade:", reply_markup=crypto_menu())
    elif d=="menu_mt5":
        await q.edit_message_text("🥇 MT5 — Click any pair you wan trade:", reply_markup=mt5_menu())
    elif d=="back_main":
        await q.edit_message_text("🔥 Skelly Pro V6\n**SELECT MARKET:**", reply_markup=main_menu())
    elif d.startswith("coin_"):
        coin=d.replace("coin_","")
        await q.edit_message_text(f"⏳ Scanning {coin}... (Bybit 15m)")
        sig=get_price_analysis(coin)
        await context.bot.send_message(chat_id=q.message.chat.id, text=sig, reply_markup=crypto_menu())
    elif d.startswith("mt5_"):
        pair=d.replace("mt5_","")
        await q.edit_message_text(f"⏳ Scanning {pair} MT5...")
        if "XAU" in pair:
            sig=get_xau_analysis(pair)
        else:
            # For other forex, use same gold logic as placeholder with pair name
            sig=format_signal(pair,"LONG","Market",["TP1","TP2","TP3","TP4"],"Wide SL 3.5%","MT5 | Coming live - use XAUUSD for now")
        await context.bot.send_message(chat_id=q.message.chat.id, text=sig, reply_markup=mt5_menu())

def run_bot():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(handle))
    app.run_polling()

flask_app=Flask(__name__)
@flask_app.route('/')
def home(): return "Skelly MENU LIVE"

if __name__=="__main__":
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0',port=10000),daemon=True).start()
    run_bot()
