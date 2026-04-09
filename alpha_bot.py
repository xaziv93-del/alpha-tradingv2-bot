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

        if data.empty or len(data) < 20:
            return 0

        closes = data["Close"]

        latest = closes.iloc[-1]
        prev5 = closes.iloc[-5]
        prev20 = closes.iloc[-20]

        score = 0

        # Simple momentum (short-term)
        if latest > prev5:
            score += 1

        # Medium trend
        if latest > prev20:
            score += 1

        # Moving average (safe version)
        ma20 = closes.rolling(20).mean().iloc[-1]
        if latest > ma20:
            score += 1

        # Recent strength
        if (latest - prev5) / prev5 > 0.02:
            score += 1

        # Volatility breakout (looser)
        if latest > closes.iloc[-10:].max() * 0.98:
            score += 1

        return score

    except Exception as e:
        print(f"Error on {ticker}: {e}")
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
