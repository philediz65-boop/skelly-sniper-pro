import os
import time
import yfinance as yf
import pandas as pd
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
import threading

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

# === SKELLY V6 SCANNER LOGIC ===
def scan_market():
    # We scan top crypto + stocks
    symbols = ["BTC-USD", "ETH-USD", "SOL-USD", "AAPL", "TSLA", "NVDA"]
    results = []
    for sym in symbols:
        try:
            df = yf.download(sym, period="1d", interval="15m", progress=False)
            if len(df) < 20: continue
            # Simple momentum breakout
            last = df['Close'].iloc[-1]
            sma = df['Close'].rolling(20).mean().iloc[-1]
            if last > sma * 1.01:
                results.append(f"✅ {sym} - Bullish Breakout: ${last:.2f} > SMA ${sma:.2f}")
            else:
                results.append(f"⚪ {sym} - Waiting: ${last:.2f}")
        except Exception as e:
            results.append(f"❌ {sym} Error")
    return "\n".join(results) if results else "No data yet."

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Skelly Sniper Pro V6 LIVE\n\nCommands:\n/scan - Scan Now\n/start - Menu")

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Scanning market... please wait 10s")
    result = scan_market()
    await update.message.reply_text(f"📊 SKELLY V6 RESULTS:\n\n{result}\n\n_Updated: Just now_", parse_mode="Markdown")

def main():
    print("V6 LIVE - Starting bot polling...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.run_polling()

# === FLASK FOR RENDER FREE WEB SERVICE ===
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Skelly V6 LIVE - Bot is running"

def run_flask():
    flask_app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    main()
