from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import requests

TOKEN = os.getenv("BOT_TOKEN")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# 🔥 Expanded sectors
stocks = {
    "AI": ["NVDA", "AMD", "SMCI", "MSFT", "GOOGL"],
    "Semiconductors": ["TSM", "ASML", "AVGO"],
    "Defense": ["LMT", "RTX", "NOC", "PLTR"],
    "Space": ["RKLB", "ASTS", "SPCE"],
    "Energy": ["XOM", "CVX", "SLB", "NEE"],
    "Biotech": ["MRNA", "BNTX", "CRSP", "VRTX"]
}

def get_price_data(symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        return requests.get(url).json()
    except:
        return {}

def technical_score(symbol):
    try:
        data = get_price_data(symbol)
        current = data.get("c")
        prev_close = data.get("pc")

        if not current or not prev_close:
            return 0

        change_pct = (current - prev_close) / prev_close

        score = 0
        if current > prev_close:
            score += 1
        if change_pct > 0.02:
            score += 1
        if current > prev_close * 1.01:
            score += 1
        if current > prev_close * 0.98:
            score += 1
        if change_pct > 0.03:
            score += 1

        return score

    except:
        return 0

def smart_money_score(symbol):
    try:
        data = get_price_data(symbol)
        current = data.get("c")
        prev_close = data.get("pc")

        if not current or not prev_close:
            return 0, "No data"

        change_pct = (current - prev_close) / prev_close

        score = 0
        if change_pct > 0.01:
            score += 1
        if change_pct > 0.02:
            score += 1
        if change_pct > 0.03:
            score += 1
        if change_pct > 0.05:
            score += 2

        if score >= 4:
            signal = "🔥 Strong Buying Pressure"
        elif score >= 2:
            signal = "📈 Accumulation"
        else:
            signal = "😐 Weak Flow"

        return min(score, 5), signal

    except:
        return 0, "Error"

def sentiment_score(symbol):
    try:
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from=2024-01-01&to=2025-12-31&token={FINNHUB_API_KEY}"
        news = requests.get(url).json()

        score = len(news[:10])

        if score >= 8:
            signal = "🔥 High Hype"
        elif score >= 3:
            signal = "📢 Building Attention"
        else:
            signal = "😐 Low Buzz"

        return min(score, 5), signal

    except:
        return 0, "Error"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Bot Online 🚀")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):

    results = []

    for sector, tickers in stocks.items():
        for stock in tickers:

            tech = technical_score(stock)
            flow, flow_signal = smart_money_score(stock)
            sent, sent_signal = sentiment_score(stock)

            total = tech + flow + sent

            results.append((stock, sector, total, tech, flow, sent, flow_signal, sent_signal))

    # 🔥 Sector ranking
    sector_scores = {}

    for stock, sector, total, *_ in results:
        if sector not in sector_scores:
            sector_scores[sector] = []
        sector_scores[sector].append(total)

    sector_avg = {
        sector: sum(scores)/len(scores)
        for sector, scores in sector_scores.items()
    }

    sorted_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)

    # Sort stocks
    results.sort(key=lambda x: x[2], reverse=True)

    # 🔥 Build message
    message = "🚨 FULL ALPHA SCAN (MARKET VIEW)\n\n"

    message += "📊 TOP SECTORS:\n"
    for sector, score in sorted_sectors:
        message += f"{sector}: {round(score,1)}\n"

    message += "\n🔥 STOCKS:\n\n"

    for stock, sector, total, tech, flow, sent, flow_signal, sent_signal in results:
        message += (
            f"{stock} ({sector}) | Score: {total}/15\n"
            f"Tech: {tech}/5 | Flow: {flow}/5 | Sent: {sent}/5\n"
            f"{flow_signal} | {sent_signal}\n\n"
        )

    await update.message.reply_text(message)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.run_polling()
