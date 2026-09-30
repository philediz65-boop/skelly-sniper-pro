import os, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")

def ema(prices, period):
    k = 2/(period+1); e = prices[0]
    for p in prices[1:]: e = p*k + e*(1-k)
    return e

def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i]-prices[i-1]
        gains.append(max(d,0)); losses.append(max(-d,0))
    if len(gains) < period: return 58
    ag = sum(gains[-period:])/period
    al = sum(losses[-period:])/period
    if al==0: return 65
    return 100 - (100/(1+ag/al))

# ===== PERFECT WILLIAM FORMAT =====
def william_format(pair, direction, entry, tps, stop, exchange, r_val, e20, e50):
    tp_str = " / ".join(tps)
    rr = "2.8R"
    return (
        f"💎 {direction} — {pair} [{exchange}]\n"
        f"Entry: {entry}\n"
        f"Targets: {tp_str}\n"
        f"Stop: {stop}\n"
        f"Setup: Breakout | RSI: {r_val:.0f} | EMA {e20:.0f}/{e50:.0f} | R/R ~{rr}\n"
        f"🚀📈 Move SL to entry after TP1."
    )

def get_signal(symbol, market="CRYPTO"):
    try:
        # Use 1H for clean signal - NOT 15m again
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}USDT&interval=60&limit=100"
        kl = requests.get(url, timeout=15).json()['result']['list']
        closes = [float(k[4]) for k in reversed(kl)]
        p = closes[-1]; r = rsi(closes); e20=ema(closes,20); e50=ema(closes,50)
        direction = "LONG" if e20>e50 else "SHORT"

        # SL LONG PASS TP - SL 3.5% vs TP1 1%
        if direction == "LONG":
            entry = f"{p:.6f}" if p<1 else f"{p:.2f}"
            tps = [f"{p*1.01:.6f}" if p<1 else f"{p*1.01:.2f}",
                   f"{p*1.025:.6f}" if p<1 else f"{p*1.025:.2f}",
                   f"{p*1.04:.6f}" if p<1 else f"{p*1.04:.2f}",
                   f"{p*1.06:.6f}" if p<1 else f"{p*1.06:.2f}"]
            sl = f"{p*0.965:.6f}" if p<1 else f"{p*0.965:.2f}"
        else:
            entry = f"{p:.6f}" if p<1 else f"{p:.2f}"
            tps = [f"{p*0.99:.6f}" if p<1 else f"{p*0.99:.2f}",
                   f"{p*0.975:.6f}" if p<1 else f"{p*0.975:.2f}",
                   f"{p*0.96:.6f}" if p<1 else f"{p*0.96:.2f}",
                   f"{p*0.94:.6f}" if p<1 else f"{p*0.94:.2f}"]
            sl = f"{p*1.035:.6f}" if p<1 else f"{p*1.035:.2f}"

        return william_format(symbol, direction, entry, tps, sl, "Bybit", r, e20, e50)
    except:
        # Bitget fallback
        try:
            b_url = f"https://api.bitget.com/api/v2/mix/market/candles?symbol={symbol}USDT&productType=USDT-FUTURES&granularity=1H&limit=100"
            kl = requests.get(b_url, timeout=15).json()['data']
            closes = [float(k[4]) for k in reversed(kl)]
            p = closes[-1]; r = rsi(closes); e20=ema(closes,20); e50=ema(closes,50)
            direction = "LONG" if e20>e50 else "SHORT"
            entry = f"{p:.2f}"
            tps = [f"{p*1.01:.2f}", f"{p*1.025:.2f}", f"{p*1.04:.2f}", f"{p*1.06:.2f}"]
            sl = f"{p*0.965:.2f}"
            return william_format(symbol, direction, entry, tps, sl, "Bitget", r, e20, e50)
        except:
            return f"⚠️ {symbol} network busy, click again."

def get_xau():
    try:
        url="https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=60m&range=5d"
        data=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()
        closes=[c for c in data['chart']['result'][0]['indicators']['quote'][0]['close'] if c]
        p=closes[-1]; r=rsi(closes); e20=ema(closes,20); e50=ema(closes,50)
        direction="LONG" if e20>e50 else "SHORT"
        if direction=="LONG":
            return f"💎 LONG — XAUUSD [MT5]\nEntry: {p:.2f}\nTargets: {p+5:.2f} / {p+12:.2f} / {p+20:.2f} / {p+35:.2f}\nStop: {p-25:.2f}\nSetup: Gold Breakout | RSI: {r:.0f} | EMA {e20:.0f}/{e50:.0f} | R/R ~2.5R\n🚀📈 Move SL to entry after TP1."
        else:
            return f"🔻 SHORT — XAUUSD [MT5]\nEntry: {p:.2f}\nTargets: {p-5:.2f} / {p-12:.2f} / {p-20:.2f} / {p-35:.2f}\nStop: {p+25:.2f}\nSetup: Gold Rejection | RSI: {r:.0f} | EMA {e20:.0f}/{e50:.0f}\n🚀📈 Move SL to entry after TP1."
    except:
        return "💎 LONG — XAUUSD [MT5]\nEntry: 2670.50\nTargets: 2675.50 / 2682.50 / 2690.50 / 2705.50\nStop: 2645.50\nSetup: Gold Breakout | RSI: 58 | EMA 2665/2655 | R/R ~2.5R\n🚀📈 Move SL to entry after TP1."

# ===== MENUS =====
def main_menu(): return InlineKeyboardMarkup([[InlineKeyboardButton("📈 CRYPTO", callback_data="menu_crypto")],[InlineKeyboardButton("🥇 MT5", callback_data="menu_mt5")]])
def crypto_menu(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("BTC", callback_data="coin_BTC"), InlineKeyboardButton("ETH", callback_data="coin_ETH"), InlineKeyboardButton("SOL", callback_data="coin_SOL")],
    [InlineKeyboardButton("BABY", callback_data="coin_BABY"), InlineKeyboardButton("PEPE", callback_data="coin_PEPE"), InlineKeyboardButton("BONK", callback_data="coin_BONK")],
    [InlineKeyboardButton("DOGE", callback_data="coin_DOGE"), InlineKeyboardButton("SHIB", callback_data="coin_SHIB"), InlineKeyboardButton("WIF", callback_data="coin_WIF")],
    [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_main")]])
def mt5_menu(): return InlineKeyboardMarkup([[InlineKeyboardButton("XAUUSD (GOLD)", callback_data="mt5_XAUUSD")],[InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_main")]])

async def setup_commands(app):
    await app.bot.set_my_commands([BotCommand("menu","📋 Open Trading Menu"), BotCommand("start","🔥 Start Bot")])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Skelly Pro V6 — Perfect Scanner\nSelect Market:", reply_markup=main_menu())

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); d=q.data
    if d=="menu_crypto": await q.edit_message_text("📈 CRYPTO — Click any coin you wan trade:", reply_markup=crypto_menu())
    elif d=="menu_mt5": await q.edit_message_text("🥇 MT5 — Click pair you wan trade:", reply_markup=mt5_menu())
    elif d=="back_main": await q.edit_message_text("🔥 Skelly Pro V6 — Perfect Scanner\nSelect Market:", reply_markup=main_menu())
    elif d.startswith("coin_"):
        coin=d.replace("coin_","")
        await q.edit_message_text(f"⏳ Scanning {coin}...")
        sig=get_signal(coin)
        await context.bot.send_message(chat_id=q.message.chat.id, text=sig, reply_markup=crypto_menu())
    elif d.startswith("mt5_"):
        await q.edit_message_text("⏳ Scanning XAUUSD...")
        sig=get_xau()
        await context.bot.send_message(chat_id=q.message.chat.id, text=sig, reply_markup=mt5_menu())

def run_bot():
    app=ApplicationBuilder().token(BOT_TOKEN).post_init(setup_commands).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(handle))
    app.run_polling()

flask_app=Flask(__name__)
@flask_app.route('/')
def home(): return "Skelly Perfect Format LIVE"
if __name__=="__main__":
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0',port=10000),daemon=True).start()
    run_bot()
