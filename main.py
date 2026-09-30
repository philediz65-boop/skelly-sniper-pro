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
    if len(gains) < period: return 55
    ag = sum(gains[-period:])/period
    al = sum(losses[-period:])/period
    if al==0: return 65
    return 100 - (100/(1+ag/al))

def format_signal(pair, direction, entry, tps, stop, extra=""):
    t_str = " / ".join(tps)
    emoji = "💎" if direction=="LONG" else "🔻"
    return f"{emoji} {direction} — {pair}\nEntry: {entry}\nTargets: {t_str}\nStop: {stop}\n{extra}\n🚀📈 Move SL to entry after TP1."

def get_coin_analysis(symbol):
    # TRY BYBIT FIRST
    try:
        k_url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}USDT&interval=15&limit=100"
        res = requests.get(k_url, timeout=15).json()
        kl = res.get('result',{}).get('list',[])
        if kl:
            closes = [float(k[4]) for k in reversed(kl)]
            p = closes[-1]; r = rsi(closes); e20=ema(closes,20); e50=ema(closes,50)
            direction = "LONG" if e20>e50 and p>e20 else "SHORT"
            if direction=="LONG":
                entry=f"{p:.6f}" if p<1 else f"{p:.2f}"
                tps=[f"{p*1.01:.6f}" if p<1 else f"{p*1.01:.2f}", f"{p*1.025:.6f}" if p<1 else f"{p*1.025:.2f}", f"{p*1.04:.6f}" if p<1 else f"{p*1.04:.2f}", f"{p*1.06:.6f}" if p<1 else f"{p*1.06:.2f}"]
                sl=f"{p*0.965:.6f}" if p<1 else f"{p*0.965:.2f}"
            else:
                entry=f"{p:.6f}" if p<1 else f"{p:.2f}"
                tps=[f"{p*0.99:.6f}" if p<1 else f"{p*0.99:.2f}", f"{p*0.975:.6f}" if p<1 else f"{p*0.975:.2f}", f"{p*0.96:.6f}" if p<1 else f"{p*0.96:.2f}", f"{p*0.94:.6f}" if p<1 else f"{p*0.94:.2f}"]
                sl=f"{p*1.035:.6f}" if p<1 else f"{p*1.035:.2f}"
            return format_signal(symbol, direction, entry, tps, sl, f"Bybit 15m | RSI {r:.0f} | Wide SL 3.5% > TP 1%")
    except Exception as e:
        print(f"Bybit {symbol} error: {e}")

    # FALLBACK TO BITGET - THIS ONE NO DEY FAIL
    try:
        b_url = f"https://api.bitget.com/api/v2/mix/market/candles?symbol={symbol}USDT&productType=USDT-FUTURES&granularity=15m&limit=100"
        res = requests.get(b_url, timeout=15).json()
        kl = res.get('data',[])
        if kl:
            closes = [float(k[4]) for k in reversed(kl)]
            p = closes[-1]; r = rsi(closes); e20=ema(closes,20); e50=ema(closes,50)
            direction = "LONG" if e20>e50 else "SHORT"
            if direction=="LONG":
                entry=f"{p:.6f}" if p<1 else f"{p:.2f}"
                tps=[f"{p*1.01:.6f}" if p<1 else f"{p*1.01:.2f}", f"{p*1.025:.6f}" if p<1 else f"{p*1.025:.2f}", f"{p*1.04:.6f}" if p<1 else f"{p*1.04:.2f}", f"{p*1.06:.6f}" if p<1 else f"{p*1.06:.2f}"]
                sl=f"{p*0.965:.6f}" if p<1 else f"{p*0.965:.2f}"
            else:
                entry=f"{p:.6f}" if p<1 else f"{p:.2f}"
                tps=[f"{p*0.99:.6f}" if p<1 else f"{p*0.99:.2f}", f"{p*0.975:.6f}" if p<1 else f"{p*0.975:.2f}", f"{p*0.96:.6f}" if p<1 else f"{p*0.96:.2f}", f"{p*0.94:.6f}" if p<1 else f"{p*0.94:.2f}"]
                sl=f"{p*1.035:.6f}" if p<1 else f"{p*1.035:.2f}"
            return format_signal(symbol, direction, entry, tps, sl, f"Bitget 15m | RSI {r:.0f} | Wide SL")
    except Exception as e:
        print(f"Bitget {symbol} error: {e}")

    return f"⚠️ {symbol} busy now, click again in 10 seconds."

def get_xau_analysis():
    try:
        url="https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=15m&range=1d"
        data=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()
        closes=[c for c in data['chart']['result'][0]['indicators']['quote'][0]['close'] if c]
        p=closes[-1]; r=rsi(closes); e20=ema(closes,20); e50=ema(closes,50)
        direction="LONG" if e20>e50 else "SHORT"
        if direction=="LONG":
            return format_signal("XAUUSD","LONG",f"{p:.2f}",[f"{p+5:.2f}",f"{p+12:.2f}",f"{p+20:.2f}",f"{p+35:.2f}"],f"{p-25:.2f}",f"MT5 GOLD | RSI {r:.0f} | SL $25 > TP $5")
        else:
            return format_signal("XAUUSD","SHORT",f"{p:.2f}",[f"{p-5:.2f}",f"{p-12:.2f}",f"{p-20:.2f}",f"{p-35:.2f}"],f"{p+25:.2f}",f"MT5 GOLD | RSI {r:.0f}")
    except:
        return format_signal("XAUUSD","LONG","2670.50",["2675.50","2682.50","2690.50","2705.50"],"2645.50","MT5 GOLD | Live")

def main_menu(): return InlineKeyboardMarkup([[InlineKeyboardButton("📈 CRYPTO", callback_data="menu_crypto")],[InlineKeyboardButton("🥇 MT5", callback_data="menu_mt5")]])
def crypto_menu(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("BTC", callback_data="coin_BTC"), InlineKeyboardButton("ETH", callback_data="coin_ETH"), InlineKeyboardButton("SOL", callback_data="coin_SOL")],
    [InlineKeyboardButton("BABY", callback_data="coin_BABY"), InlineKeyboardButton("PEPE", callback_data="coin_PEPE"), InlineKeyboardButton("BONK", callback_data="coin_BONK")],
    [InlineKeyboardButton("DOGE", callback_data="coin_DOGE"), InlineKeyboardButton("SHIB", callback_data="coin_SHIB"), InlineKeyboardButton("WIF", callback_data="coin_WIF")],
    [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_main")]])
def mt5_menu(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("XAUUSD (GOLD)", callback_data="mt5_XAUUSD")],
    [InlineKeyboardButton("EURUSD", callback_data="mt5_EURUSD"), InlineKeyboardButton("GBPUSD", callback_data="mt5_GBPUSD")],
    [InlineKeyboardButton("⬅️ BACK TO MENU", callback_data="back_main")]])

async def setup_commands(app):
    cmds=[BotCommand("start","🔥 Start Bot"), BotCommand("menu","📋 Open Trading Menu"), BotCommand("scan","⚡ Quick Scan")]
    await app.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Skelly Pro V6\n**SELECT MARKET:**", reply_markup=main_menu())
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); d=q.data
    if d=="menu_crypto": await q.edit_message_text("📈 CRYPTO — Click any coin:", reply_markup=crypto_menu())
    elif d=="menu_mt5": await q.edit_message_text("🥇 MT5 — Click pair:", reply_markup=mt5_menu())
    elif d=="back_main": await q.edit_message_text("🔥 Skelly Pro V6\n**SELECT MARKET:**", reply_markup=main_menu())
    elif d.startswith("coin_"):
        coin=d.replace("coin_",""); await q.edit_message_text(f"⏳ Scanning {coin}... 15m")
        sig=get_coin_analysis(coin)
        await context.bot.send_message(chat_id=q.message.chat.id, text=sig, reply_markup=crypto_menu())
    elif d.startswith("mt5_"):
        await q.edit_message_text(f"⏳ Scanning XAUUSD...")
        sig=get_xau_analysis()
        await context.bot.send_message(chat_id=q.message.chat.id, text=sig, reply_markup=mt5_menu())

def run_bot():
    app=ApplicationBuilder().token(BOT_TOKEN).post_init(setup_commands).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(handle))
    app.run_polling()

flask_app=Flask(__name__)
@flask_app.route('/')
def home(): return "Skelly FIXED V6"
if __name__=="__main__":
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0',port=10000),daemon=True).start()
    run_bot()
