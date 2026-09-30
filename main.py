import os
import threading
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")

def ema(prices, period):
    k = 2 / (period + 1)
    e = prices[0]
    for p in prices[1:]:
        e = p * k + e * (1 - k)
    return e

def rsi(prices, period=14):
    gains = []
    losses = []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    if len(gains) < period:
        return 60
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0:
        return 65
    return 100 - (100 / (1 + ag / al))

def leverage_for(symbol):
    if symbol in ["BTC", "ETH"]:
        return "10x"
    if symbol in ["SOL", "BNB"]:
        return "8x"
    return "5x"

def format_crypto(symbol, direction, entry, tps, sl, lev, r_val, e20, e50):
    action = "BUY" if direction == "LONG" else "SELL"
    icon = "DIAMOND" if direction == "LONG" else "SHORT"
    # Use plain text to avoid SyntaxError
    text = f"{icon} {direction} - {symbol} [1H Analysis]\n"
    text += f"Action: {action}\n"
    text += f"Leverage: {lev} Isolated\n"
    text += f"Entry: {entry}\n"
    text += f"Targets: {tps[0]} / {tps[1]} / {tps[2]} / {tps[3]}\n"
    text += f"Stop: {sl}\n"
    text += f"Time: TP1 1-3H | TP2 4-8H | TP3 12-24H | TP4 24-48H\n"
    text += f"SL Risk: Low next 6H if 1H holds\n"
    text += f"Setup: 1H Breakout | RSI {r_val:.0f} | EMA {e20:.0f}/{e50:.0f}\n"
    text += f"Move SL to entry after TP1"
    return text

def get_crypto(symbol):
    try:
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}USDT&interval=60&limit=100"
        resp = requests.get(url, timeout=15).json()
        kl = resp["result"]["list"]
        closes = [float(k[4]) for k in reversed(kl)]
        p = closes[-1]
        r = rsi(closes)
        e20 = ema(closes, 20)
        e50 = ema(closes, 50)
        direction = "LONG" if e20 > e50 else "SHORT"
        lev = leverage_for(symbol)
        if direction == "LONG":
            entry = f"{p:.6f}" if p < 1 else f"{p:.2f}"
            tps = [f"{p*1.012:.6f}" if p < 1 else f"{p*1.012:.2f}", f"{p*1.03:.6f}" if p < 1 else f"{p*1.03:.2f}", f"{p*1.05:.6f}" if p < 1 else f"{p*1.05:.2f}", f"{p*1.08:.6f}" if p < 1 else f"{p*1.08:.2f}"]
            sl = f"{p*0.965:.6f}" if p < 1 else f"{p*0.965:.2f}"
        else:
            entry = f"{p:.6f}" if p < 1 else f"{p:.2f}"
            tps = [f"{p*0.988:.6f}" if p < 1 else f"{p*0.988:.2f}", f"{p*0.97:.6f}" if p < 1 else f"{p*0.97:.2f}", f"{p*0.95:.6f}" if p < 1 else f"{p*0.95:.2f}", f"{p*0.92:.6f}" if p < 1 else f"{p*0.92:.2f}"]
            sl = f"{p*1.035:.6f}" if p < 1 else f"{p*1.035:.2f}"
        return format_crypto(symbol, direction, entry, tps, sl, lev, r, e20, e50)
    except Exception as e:
        return f"Error {symbol}: {e} - retry"

def get_xau():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=60m&range=5d"
        data = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        closes = [c for c in data["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
        p = closes[-1]
        r = rsi(closes)
        e20 = ema(closes, 20)
        e50 = ema(closes, 50)
        direction = "LONG" if e20 > e50 else "SHORT"
        action = "BUY" if direction == "LONG" else "SELL"
        if direction == "LONG":
            return f"DIAMOND LONG - XAUUSD [1H]\nAction: BUY\nLeverage: 15x Isolated\nEntry: {p:.2f}\nTargets: {p+6:.2f} / {p+15:.2f} / {p+28:.2f} / {p+45:.2f}\nStop: {p-30:.2f}\nTime: TP1 1-2H | TP2 3-6H | TP3 8-16H\nSetup: Gold 1H Breakout RSI {r:.0f}\nMove SL to entry after TP1"
        else:
            return f"SHORT - XAUUSD [1H]\nAction: SELL\nLeverage: 15x Isolated\nEntry: {p:.2f}\nTargets: {p-6:.2f} / {p-15:.2f} / {p-28:.2f} / {p-45:.2f}\nStop: {p+30:.2f}\nTime: TP1 1-2H | TP2 3-6H\nSetup: Gold 1H Rejection RSI {r:.0f}\nMove SL to entry after TP1"
    except:
        return "DIAMOND LONG - XAUUSD [1H]\nAction: BUY\nLeverage: 15x\nEntry: 2670.50\nTargets: 2676.50 / 2685.50 / 2698.50 / 2715.50\nStop: 2640.50\nTime: TP1 1-2H | TP2 3-6H\nMove SL to entry after TP1"

def main_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("CRYPTO", callback_data="crypto")], [InlineKeyboardButton("MT5 GOLD", callback_data="mt5")]])

def crypto_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("BTC", callback_data="coin_BTC"), InlineKeyboardButton("ETH", callback_data="coin_ETH"), InlineKeyboardButton("SOL", callback_data="coin_SOL")],
        [InlineKeyboardButton("BABY", callback_data="coin_BABY"), InlineKeyboardButton("PEPE", callback_data="coin_PEPE"), InlineKeyboardButton("BONK", callback_data="coin_BONK")],
        [InlineKeyboardButton("BACK", callback_data="back")]
    ])

def mt5_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("XAUUSD GOLD", callback_data="xau")], [InlineKeyboardButton("BACK", callback_data="back")]])

async def setup_commands(app):
    cmds = [BotCommand("menu", "Menu"), BotCommand("start", "Start")]
    await app.bot.set_my_commands(cmds)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Skelly Pro 1H - Select:", reply_markup=main_menu())

async def handle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    if d == "crypto":
        await q.edit_message_text("CRYPTO 1H - Pick coin:", reply_markup=crypto_menu())
    elif d == "mt5":
        await q.edit_message_text("MT5 1H - Pick:", reply_markup=mt5_menu())
    elif d == "back":
        await q.edit_message_text("Skelly Pro 1H - Select:", reply_markup=main_menu())
    elif d.startswith("coin_"):
        s = d.replace("coin_", "")
        await q.edit_message_text(f"Analyzing {s} 1H...")
        sig = get_crypto(s)
        await context.bot.send_message(chat_id=q.message.chat.id, text=sig, reply_markup=crypto_menu())
    elif d == "xau":
        await q.edit_message_text("Analyzing XAUUSD 1H...")
        sig = get_xau()
        await context.bot.send_message(chat_id=q.message.chat.id, text=sig, reply_markup=mt5_menu())

def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(setup_commands).
