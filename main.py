# ============================================================
# PHILEDIZ V2
# Live Market Analysis Bot
# Render + Telegram + Bybit + XAUUSD
# ============================================================

import os
import re
import time
import threading
import requests

from flask import Flask, jsonify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

PORT = int(os.getenv("PORT", "10000"))

BYBIT_URL = "https://api.bybit.com"

HEADERS = {
    "User-Agent": "PHILEDIZ-V2/1.0"
}

TIMEOUT = 15


# ============================================================
# FLASK SERVER
# Render needs a web server listening on PORT
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "PHILEDIZ V2 is online", 200


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "bot": "PHILEDIZ V2"
    }), 200


def run_flask():
    app.run(
        host="0.0.0.0",
        port=PORT,
        use_reloader=False
    )


# ============================================================
# SYMBOL NORMALIZATION
# ============================================================

def normalize_symbol(symbol):
    symbol = symbol.upper().strip()

    symbol = symbol.replace("/", "")
    symbol = symbol.replace("-", "")
    symbol = symbol.replace("_", "")

    # Remove common suffixes
    for suffix in ["USDT", "USD"]:
        if symbol.endswith(suffix):
            symbol = symbol[:-len(suffix)]
            break

    return symbol


# ============================================================
# SUPPORTED CRYPTO
# ============================================================

SUPPORTED_COINS = [
    "BTC",
    "ETH",
    "BNB",
    "SOL",
    "XRP",
    "DOGE",
    "ADA",
    "AVAX",
    "LINK",
    "TRX",
]


def is_supported_crypto(symbol):
    return normalize_symbol(symbol) in SUPPORTED_COINS


# ============================================================
# GET BYBIT KLINES
# ============================================================

def get_bybit_klines(symbol, interval="15", limit=200):

    base = normalize_symbol(symbol)

    if base not in SUPPORTED_COINS:
        return None

    bybit_symbol = base + "USDT"

    url = (
        f"{BYBIT_URL}/v5/market/kline"
        f"?category=linear"
        f"&symbol={bybit_symbol}"
        f"&interval={interval}"
        f"&limit={limit}"
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        if data.get("retCode") != 0:
            return None

        rows = data.get("result", {}).get("list", [])

        if not rows:
            return None

        # Bybit returns newest first.
        rows.reverse()

        candles = []

        for row in rows:
            try:
                candles.append({
                    "time": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                })
            except (ValueError, TypeError, IndexError):
                continue

        return candles

    except Exception:
        return None


# ============================================================
# LIVE BYBIT PRICE
# ============================================================

def get_bybit_price(symbol):

    base = normalize_symbol(symbol)

    if base not in SUPPORTED_COINS:
        return None

    bybit_symbol = base + "USDT"

    url = (
        f"{BYBIT_URL}/v5/market/tickers"
        f"?category=linear"
        f"&symbol={bybit_symbol}"
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        if data.get("retCode") != 0:
            return None

        items = data.get("result", {}).get("list", [])

        if not items:
            return None

        price = items[0].get("lastPrice")

        if price is None:
            return None

        return float(price)

    except Exception:
        return None


# ============================================================
# REAL BYBIT MAX LEVERAGE
# ============================================================

def get_real_leverage(symbol):

    symbol = normalize_symbol(symbol)

    if symbol not in SUPPORTED_COINS:
        return "N/A"

    try:

        url = (
            f"{BYBIT_URL}/v5/market/instruments-info"
            f"?category=linear&symbol={symbol}USDT"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        if data.get("retCode") != 0:
            return "N/A"

        items = data.get("result", {}).get("list", [])

        if not items:
            return "N/A"

        leverage_filter = items[0].get("leverageFilter", {})

        max_leverage = leverage_filter.get("maxLeverage")

        if max_leverage is None:
            return "N/A"

        return f"{float(max_leverage):g}x"

    except Exception:
        return "N/A"


# ============================================================
# EMA
# ============================================================

def calculate_ema(values, period):

    if not values or len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema = sum(values[:period]) / period

    for price in values[period:]:
        ema = (
            (price - ema) * multiplier
        ) + ema

    return ema


# ============================================================
# RSI
# ============================================================

def calculate_rsi(values, period=14):

    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(values)):
        change = values[i] - values[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):

        avg_gain = (
            (avg_gain * (period - 1))
            + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1))
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ============================================================
# ATR
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        high = current["high"]
        low = current["low"]
        previous_close = previous["close"]

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )

        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    atr = sum(true_ranges[:period]) / period

    for tr in true_ranges[period:]:
        atr = (
            (atr * (period - 1)) + tr
        ) / period

    return atr


# ============================================================
# PRICE FORMATTING
# ============================================================

def format_price(price):

    if price is None:
        return "N/A"

    if price >= 1000:
        return f"{price:,.2f}"

    if price >= 1:
        return f"{price:,.4f}"

    if price >= 0.01:
        return f"{price:.6f}"

    return f"{price:.8f}"


# ============================================================
# PERCENTAGE
# ============================================================

def percentage_difference(a, b):

    if a is None or b is None or b == 0:
        return 0

    return ((a - b) / b) * 100


# ============================================================
# CRYPTO MARKET ANALYSIS
# ============================================================

def analyze_crypto(symbol):

    symbol = normalize_symbol(symbol)

    candles = get_bybit_klines(
        symbol,
        interval="15",
        limit=200
    )

    if not candles or len(candles) < 60:
        return None

    closes = [c["close"] for c in candles]

    current_price = get_bybit_price(symbol)

    if current_price is None:
        current_price = closes[-1]

    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)

    rsi = calculate_rsi(closes, 14)

    atr = calculate_atr(candles, 14)

    if (
        ema20 is None
        or ema50 is None
        or rsi is None
        or atr is None
    ):
        return None

    # --------------------------------------------------------
    # ANALYSIS SCORE
    # --------------------------------------------------------

    bullish_score = 0
    bearish_score = 0

    # EMA relationship
    if ema20 > ema50:
        bullish_score += 1
    elif ema20 < ema50:
        bearish_score += 1

    # Current price vs EMA20
    if current_price > ema20:
        bullish_score += 1
    elif current_price < ema20:
        bearish_score += 1

    # RSI
    if rsi < 35:
        bullish_score += 2
    elif rsi > 65:
        bearish_score += 2
    elif rsi >= 50:
        bullish_score += 1
    else:
        bearish_score += 1

    # Recent momentum
    previous_close = closes[-2]

    if current_price > previous_close:
        bullish_score += 1
    elif current_price < previous_close:
        bearish_score += 1

    # --------------------------------------------------------
    # DECISION
    # --------------------------------------------------------

    if bullish_score >= 4 and bullish_score > bearish_score:
        direction = "BUY 🟢"

    elif bearish_score >= 4 and bearish_score > bullish_score:
        direction = "SELL 🔴"

    else:
        direction = "WAIT 🟡"

    # --------------------------------------------------------
    # ENTRY / SL / TP
    # --------------------------------------------------------

    entry = current_price

    if direction.startswith("BUY"):

        stop_loss = entry - (atr * 1.5)

        take_profit_1 = entry + (atr * 2.0)

        take_profit_2 = entry + (atr * 3.0)

    elif direction.startswith("SELL"):

        stop_loss = entry + (atr * 1.5)

        take_profit_1 = entry - (atr * 2.0)

        take_profit_2 = entry - (atr * 3.0)

    else:

        stop_loss = None
        take_profit_1 = None
        take_profit_2 = None

    leverage = get_real_leverage(symbol)

    return {
        "symbol": symbol + "/USDT",
        "price": current_price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "atr": atr,
        "direction": direction,
        "entry": entry,
        "sl": stop_loss,
        "tp1": take_profit_1,
        "tp2": take_profit_2,
        "leverage": leverage,
        "bullish_score": bullish_score,
        "bearish_score": bearish_score,
    }


# ============================================================
# XAUUSD LIVE DATA
#
# Uses Yahoo Finance public chart data.
# If the public source does not return usable data,
# PHILEDIZ does NOT invent a price.
# ============================================================

def get_xauusd_data():

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        "XAUUSD=X"
        "?interval=5m&range=1d"
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        result = data.get("chart", {}).get("result")

        if not result:
            return None

        result = result[0]

        indicators = result.get("indicators", {})
        quote_list = indicators.get("quote", [])

        if not quote_list:
            return None

        quote = quote_list[0]

        closes = quote.get("close", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])

        candles = []

        for i in range(len(closes)):

            if (
                closes[i] is None
                or highs[i] is None
                or lows[i] is None
            ):
                continue

            candles.append({
                "close": float(closes[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
            })

        if len(candles) < 60:
            return None

        closes = [c["close"] for c in candles]

        price = closes[-1]

        ema20 = calculate_ema(closes, 20)

        ema50 = calculate_ema(closes, 50)

        rsi = calculate_rsi(closes, 14)

        # Convert XAU candles into ATR-compatible structure
        atr_candles = []

        for c in candles:
            atr_candles.append({
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
            })

        atr = calculate_atr(
            atr_candles,
            14
        )

        if (
            ema20 is None
            or ema50 is None
            or rsi is None
            or atr is None
        ):
            return None

        bullish_score = 0
        bearish_score = 0

        if ema20 > ema50:
            bullish_score += 1
        elif ema20 < ema50:
            bearish_score += 1

        if price > ema20:
            bullish_score += 1
        elif price < ema20:
            bearish_score += 1

        if rsi < 35:
            bullish_score += 2
        elif rsi > 65:
            bearish_score += 2
        elif rsi >= 50:
            bullish_score += 1
        else:
            bearish_score += 1

        if closes[-1] > closes[-2]:
            bullish_score += 1
        elif closes[-1] < closes[-2]:
            bearish_score += 1

        if bullish_score >= 4 and bullish_score > bearish_score:
            direction = "BUY 🟢"

        elif bearish_score >= 4 and bearish_score > bullish_score:
            direction = "SELL 🔴"

        else:
            direction = "WAIT 🟡"

        entry = price

        if direction.startswith("BUY"):

            sl = entry - (atr * 1.5)

            tp1 = entry + (atr * 2.0)

            tp2 = entry + (atr * 3.0)

        elif direction.startswith("SELL"):

            sl = entry + (atr * 1.5)

            tp1 = entry - (atr * 2.0)

            tp2 = entry - (atr * 3.0)

        else:

            sl = None
            tp1 = None
            tp2 = None

        return {
            "symbol": "XAUUSD",
            "price": price,
            "ema20": ema20,
            "ema50": ema50,
            "rsi": rsi,
            "atr": atr,
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "leverage": "N/A",
        }

    except Exception:
        return None


# ============================================================
# FORMAT CRYPTO ANALYSIS
# ============================================================

def format_crypto_analysis(data):

    if not data:
        return (
            "❌ PHILEDIZ could not obtain usable live "
            "market data right now.\n\n"
            "No price or analysis has been invented."
        )

    text = (
        "🤖 PHILEDIZ V2 ANALYSIS\n\n"
        f"🪙 Symbol: {data['symbol']}\n"
        f"💰 Live Price: {format_price(data['price'])}\n"
        "⏱ Timeframe: 15M\n\n"
        f"📊 RSI(14): {data['rsi']:.2f}\n"
        f"📈 EMA20: {format_price(data['ema20'])}\n"
        f"📉 EMA50: {format_price(data['ema50'])}\n"
        f"〽️ ATR(14): {format_price(data['atr'])}\n\n"
        f"🧠 Analysis: {data['direction']}\n"
        f"🟢 Bullish factors: {data['bullish_score']}\n"
        f"🔴 Bearish factors: {data['bearish_score']}\n\n"
        f"🎯 Entry: {format_price(data['entry'])}\n"
    )

    if data["sl"] is not None:

        text += (
            f"🛑 Stop Loss: {format_price(data['sl'])}\n"
            f"🎯 TP1: {format_price(data['tp1'])}\n"
            f"🎯 TP2: {format_price(data['tp2'])}\n"
        )

    else:

        text += (
            "🛑 Stop Loss: Not set\n"
            "🎯 TP: Not set while signal is WAIT\n"
        )

    text += (
        f"\n⚡ Bybit maximum leverage: "
        f"{data['leverage']}\n"
        "⚠️ Maximum leverage is the exchange limit, "
        "not a recommended leverage level.\n\n"
        "📌 Data source: Bybit public market data.\n"
        "PHILEDIZ does not invent unavailable prices."
    )

    return text


# ============================================================
# FORMAT XAUUSD
# ============================================================

def format_xau_analysis(data):

    if not data:

        return (
            "❌ PHILEDIZ could not obtain usable live "
            "XAUUSD data right now.\n\n"
            "No price or analysis has been invented."
        )

    text = (
        "🤖 PHILEDIZ V2 ANALYSIS\n\n"
        "🥇 Symbol: XAUUSD\n"
        f"💰 Live Price: {format_price(data['price'])}\n"
        "⏱ Timeframe: 5M\n\n"
        f"📊 RSI(14): {data['rsi']:.2f}\n"
        f"📈 EMA20: {format_price(data['ema20'])}\n"
        f"📉 EMA50: {format_price(data['ema50'])}\n"
        f"〽️ ATR(14): {format_price(data['atr'])}\n\n"
        f"🧠 Analysis: {data['direction']}\n\n"
        f"🎯 Entry: {format_price(data['entry'])}\n"
    )

    if data["sl"] is not None:

        text += (
            f"🛑 Stop Loss: {format_price(data['sl'])}\n"
            f"🎯 TP1: {format_price(data['tp1'])}\n"
            f"🎯 TP2: {format_price(data['tp2'])}\n"
        )

    else:

        text += (
            "🛑 Stop Loss: Not set while signal is WAIT\n"
            "🎯 TP: Not set while signal is WAIT\n"
        )

    text += (
        "\n📌 XAUUSD public-data source may differ slightly "
        "from your broker's quote.\n"
        "PHILEDIZ does not invent unavailable prices.\n"
        "⚡ Leverage: Broker-specific / N/A"
    )

    return text


# ============================================================
# TELEGRAM /START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = (
        "🤖 PHILEDIZ V2 is online!\n\n"
        "Send a symbol to analyse it.\n\n"
        "Examples:\n"
        "• BTC\n"
        "• BTCUSDT\n"
        "• ETH\n"
        "• SOL\n"
        "• XAUUSD\n\n"
        "Commands:\n"
        "/analyze BTC\n"
        "/analyze ETH\n"
        "/analyze XAUUSD\n"
        "/help"
    )

    await update.message.reply_text(message)


# ============================================================
# TELEGRAM /HELP
# ============================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = (
        "🤖 PHILEDIZ V2\n\n"
        "Available crypto:\n"
        "BTC, ETH, BNB, SOL, XRP,\n"
        "DOGE, ADA, AVAX, LINK, TRX\n\n"
        "Gold:\n"
        "XAUUSD\n\n"
        "Examples:\n"
        "/analyze BTC\n"
        "/analyze BTCUSDT\n"
        "/analyze XAUUSD\n\n"
        "Or simply send:\n"
        "BTC\n"
        "ETH\n"
        "XAUUSD"
    )

    await update.message.reply_text(message)


# ============================================================
# TELEGRAM ANALYZE COMMAND
# ============================================================

async def analyze_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:

        await update.message.reply_text(
            "Please provide a symbol.\n\n"
            "Example:\n"
            "/analyze BTC\n"
            "/analyze ETH\n"
            "/analyze XAUUSD"
        )

        return

    symbol = context.args[0].upper().strip()

    await process_symbol(
        update,
        symbol
    )


# ============================================================
# NORMAL TEXT MESSAGE
# ============================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text.strip().upper()

    # Extract common symbols from messages
    match = re.search(
        r"\b(XAUUSD|BTCUSDT|ETHUSDT|BNBUSDT|SOLUSDT|"
        r"XRPUSDT|DOGEUSDT|ADAUSDT|AVAXUSDT|LINKUSDT|"
        r"TRXUSDT|BTC|ETH|BNB|SOL|XRP|DOGE|ADA|AVAX|"
        r"LINK|TRX)\b",
        text
    )

    if not match:
        await update.message.reply_text(
            "🤖 PHILEDIZ V2\n\n"
            "Send a supported symbol such as:\n"
            "BTC\n"
            "ETH\n"
            "SOL\n"
            "XAUUSD"
        )

        return

    symbol = match.group(1)

    await process_symbol(
        update,
        symbol
    )


# ============================================================
# PROCESS SYMBOL
# ============================================================

async def process_symbol(
    update: Update,
    symbol
):

    symbol = symbol.upper().strip()

    waiting = await update.message.reply_text(
        "⏳ PHILEDIZ is obtaining live market data..."
    )

    # XAUUSD
    if symbol == "XAUUSD":

        data = get_xauusd_data()

        message = format_xau_analysis(data)

    # Crypto
    else:

        data = analyze_crypto(symbol)

        message = format_crypto_analysis(data)

    try:

        await waiting.edit_text(message)

    except Exception:

        await update.message.reply_text(message)


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "Telegram error:",
        context.error
    )


# ============================================================
# MAIN BOT
# ============================================================

def main():

    print("========================================")
    print("🤖 PHILEDIZ V2 starting...")
    print("📊 Live market analysis enabled")
    print("📈 RSI + EMA20 + EMA50 + ATR enabled")
    print("⚡ Real Bybit max leverage enabled")
    print("🥇 XAUUSD enabled")
    print("🌐 Render web server enabled")
    print("========================================")

    # Start Flask in background
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()

    # Create Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "analyze",
            analyze_command
        )
    )

    # Normal messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    application.add_error_handler(
        error_handler
    )

    print("🤖 PHILEDIZ V2 Telegram bot is running...")

    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
