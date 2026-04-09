from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import requests

TOKEN = os.getenv("BOT_TOKEN")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

stocks = {
    "AI": ["NVDA", "AMD"],
    "Space": ["RKLB"],
    "Tech": ["PLTR", "TSLA"]
}

def get_price_data(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    res = requests.get(url).json()
    return res

def technical_score(symbol):
    try:
        data = get_price_data(symbol)

        current = data.get("c")  # current price
        prev_close = data.get("pc")  # previous close

        if not current or not prev_close:
            return 0

        score = 0

        # Price up today
        if current > prev_close:
            score += 1

        # Strong move (>2%)
        if (current - prev_close) / prev_close > 0.02:
            score += 1

        # Momentum proxy
        if current > prev_close * 1.01:
            score += 1

        # Trend proxy
        if current > prev_close * 0.98:
            score += 1

        # Breakout proxy
        if current > prev_close * 1.03:
            score += 1

        return score

    except Exception as e:
        print(f"Error {symbol}: {e}")
        return 0

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):

    results = []

    for sector, tickers in stocks.items():
        for stock in tickers:
            tech = technical_score(stock)
            results.append((stock, sector, tech))

    results.sort(key=lambda x: x[2], reverse=True)

    message = "🚨 REAL ALPHA SCAN (FINNHUB LIVE)\n\n"

    for stock, sector, score in results:
        message += f"{stock} ({sector}) | Tech Score: {score}/5\n"

    await update.message.reply_text(message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Bot Online 🚀")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.run_polling()
