from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import yfinance as yf

TOKEN = os.getenv("BOT_TOKEN")

stocks = ["NVDA", "PLTR", "RKLB", "AMD", "TSLA"]

def technical_score(ticker):
    try:
        data = yf.download(ticker, period="3mo", interval="1d")

        if data.empty:
            return 0

        data["MA50"] = data["Close"].rolling(50).mean()
        data["MA200"] = data["Close"].rolling(200).mean()

        latest = data.iloc[-1]

        score = 0

        # Price above MA50
        if latest["Close"] > latest["MA50"]:
            score += 1

        # Price above MA200
        if latest["Close"] > latest["MA200"]:
            score += 1

        # Uptrend (higher highs)
        if data["Close"].iloc[-1] > data["Close"].iloc[-5]:
            score += 1

        # Strong recent move
        if (data["Close"].iloc[-1] - data["Close"].iloc[-10]) > 0:
            score += 1

        # Volume spike
        if data["Volume"].iloc[-1] > data["Volume"].rolling(10).mean().iloc[-1]:
            score += 1

        return score

    except:
        return 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Bot Online 🚀")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    results = []

    for stock in stocks:
        tech = technical_score(stock)
        total = tech  # for now only technical

        results.append((stock, total))

    results.sort(key=lambda x: x[1], reverse=True)

    message = "🚨 REAL ALPHA SCAN (TECHNICAL)\n\n"

    for stock, score in results:
        message += f"{stock} | Tech Score: {score}/5\n"

    await update.message.reply_text(message)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.run_polling()
