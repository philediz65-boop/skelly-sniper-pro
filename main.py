import os
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask

# NO TOKEN HERE - we get it from Render only
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Skelly Sniper Pro V6 LIVE\nUse /scan")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive! Scanner ready.")

def run_bot():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN not set in Render Environment!")
        return
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    print("Bot started polling...")
    app.run_polling()

# Flask for Render Web Service
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Skelly Sniper Pro is LIVE"

if __name__ == "__main__":
    # Run Flask in background
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=10000), daemon=True).start()
    run_bot()
