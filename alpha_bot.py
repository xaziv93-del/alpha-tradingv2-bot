from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import yfinance as yf

TOKEN = os.getenv("BOT_TOKEN")

# Focus sectors (your blueprint)
stocks = {
    "AI": ["NVDA", "AMD"],
    "Space": ["RKLB"],
    "Tech": ["PLTR", "TSLA"]
}

def technical_score(ticker):
    try:
        data = yf.download(ticker, period="6mo", interval="1d")

        if data.empty or len(data) < 50:
            return 0

        data["MA50"] = data["Close"].rolling(50).mean()

        latest = data.iloc[-1]
        prev = data.iloc[-5]

        score = 0

        # Above MA50
        if latest["Close"] > latest["MA50"]:
            score += 1

        # Momentum
        if latest["Close"] > prev["Close"]:
            score += 1

        # Strong trend
        if data["Close"].iloc[-1] > data["Close"].iloc[-20]:
            score += 1

        # Volume spike
        if latest["Volume"] > data["Volume"].rolling(10).mean().iloc[-1]:
            score += 1

        # Breakout
        if latest["Close"] == data["Close"].max():
            score += 1

        return score

    except:
        return 0

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):

    results = []

    for sector, tickers in stocks.items():
        for stock in tickers:
            tech = technical_score(stock)
            results.append((stock, sector, tech))

    results.sort(key=lambda x: x[2], reverse=True)

    message = "🚨 REAL ALPHA SCAN (TECH + SECTOR)\n\n"

    for stock, sector, score in results:
        message += f"{stock} ({sector}) | Tech Score: {score}/5\n"

    await update.message.reply_text(message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Bot Online 🚀")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.run_polling()
