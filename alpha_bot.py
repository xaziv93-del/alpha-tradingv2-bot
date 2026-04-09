from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import requests
import datetime

TOKEN = os.getenv("BOT_TOKEN")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# ---------------- SECTORS ----------------

stocks = {
    "AI": ["NVDA", "AMD", "MSFT", "GOOGL", "SMCI"],
    "Semiconductors": ["TSM", "ASML", "AVGO"],
    "Space": ["RKLB", "SPCE", "ASTS"],
    "Defense": ["LMT", "RTX", "NOC", "PLTR"],
    "Energy": ["XOM", "CVX", "NEE", "SLB"],
    "Biotech": ["MRNA", "BNTX", "CRSP", "VRTX"]
}

# ---------------- DATA ----------------

def get_price_data(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    return requests.get(url).json()

# ---------------- TECH ----------------

def technical_score(symbol):
    try:
        data = get_price_data(symbol)
        current = data.get("c")
        prev_close = data.get("pc")

        if not current or not prev_close:
            return 0

        score = 0

        if current > prev_close:
            score += 1
        if (current - prev_close) / prev_close > 0.02:
            score += 1
        if current > prev_close * 1.01:
            score += 1
        if current > prev_close * 0.98:
            score += 1
        if current > prev_close * 1.03:
            score += 1

        return score

    except:
        return 0

# ---------------- FLOW ----------------

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

# ---------------- SENTIMENT ----------------

def sentiment_score(symbol):
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        news = requests.get(url).json()

        score = 0

        for article in news[:15]:
            headline = article.get("headline", "").lower()
            if symbol.lower() in headline:
                score += 1

        if score >= 5:
            return 5, "🔥 High Hype"
        elif score >= 2:
            return score, "📢 Building Attention"
        else:
            return score, "😐 Low Buzz"

    except:
        return 0, "Error"

# ---------------- EARNINGS ----------------

def catalyst_score(symbol):
    try:
        today = datetime.datetime.utcnow().date()

        url = f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={today + datetime.timedelta(days=30)}&token={FINNHUB_API_KEY}"
        data = requests.get(url).json()

        earnings_list = data.get("earningsCalendar", [])

        for event in earnings_list:
            if event.get("symbol") == symbol:
                date = event.get("date")
                return 3, f"📅 Earnings Soon ({date})"

        return 0, "No Catalyst"

    except:
        return 0, "Error"

# ---------------- SPACE ----------------

def space_catalyst(symbol):
    if symbol in ["RKLB", "SPCE", "ASTS"]:
        return 2, "🚀 Space Activity"
    return 0, "No Space Catalyst"

# ---------------- DEFENSE ----------------

def defense_catalyst(symbol):
    if symbol in ["LMT", "RTX", "NOC", "PLTR"]:
        return 2, "🛡 Defense Activity"
    return 0, "No Defense Catalyst"

# ---------------- BIOTECH ----------------

def biotech_catalyst(symbol):
    if symbol in ["MRNA", "BNTX", "CRSP", "VRTX"]:
        return 2, "💊 FDA / Drug Catalyst"
    return 0, "No Biotech Catalyst"

# ---------------- BOT ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Bot Online 🚀")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):

    results = []
    sector_scores = {}

    for sector, tickers in stocks.items():
        sector_total = 0

        for stock in tickers:
            tech = technical_score(stock)
            flow, flow_signal = smart_money_score(stock)
            sent, sent_signal = sentiment_score(stock)
            cat, cat_signal = catalyst_score(stock)

            space, space_signal = space_catalyst(stock)
            defense, defense_signal = defense_catalyst(stock)
            bio, bio_signal = biotech_catalyst(stock)

            extra_cat = space + defense + bio
            total = tech + flow + sent + cat + extra_cat

            sector_total += total

            results.append((
                stock, sector, total,
                tech, flow, sent, cat, extra_cat,
                flow_signal, sent_signal, cat_signal,
                f"{space_signal} | {defense_signal} | {bio_signal}"
            ))

        sector_scores[sector] = round(sector_total / len(tickers), 1)

    results.sort(key=lambda x: x[2], reverse=True)

    # -------- MESSAGE --------

    message = "🚨 FULL ALPHA SCAN (ELITE MODE)\n\n"

    message += "📊 TOP SECTORS:\n"
    for sec, score in sorted(sector_scores.items(), key=lambda x: x[1], reverse=True):
        message += f"{sec}: {score}\n"

    message += "\n🔥 STOCKS:\n\n"

    for r in results[:10]:
        stock, sector, total, tech, flow, sent, cat, extra, flow_sig, sent_sig, cat_sig, extra_sig = r

        message += (
            f"{stock} ({sector}) | Score: {total}/25\n"
            f"Tech: {tech}/5 | Flow: {flow}/5 | Sent: {sent}/5 | Cat: {cat}/5 | Edge: {extra}/5\n"
            f"{flow_sig} | {sent_sig} | {cat_sig}\n"
            f"{extra_sig}\n\n"
        )

    await update.message.reply_text(message)

# ---------------- RUN ----------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.run_polling()
