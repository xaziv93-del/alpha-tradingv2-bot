from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import requests
import datetime
from datetime import time

TOKEN = os.getenv("BOT_TOKEN")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# ---------------- STOCK UNIVERSE ----------------

stocks = {
    "AI": ["NVDA","AMD","MSFT","GOOGL","META","AMZN","ORCL","ADBE","CRM","NOW"],
    "Semiconductors": ["TSM","ASML","AVGO","MU","INTC","QCOM","TXN","LRCX","KLAC","AMAT"],
    "Defense": ["LMT","RTX","NOC","GD","BA","HII","LHX","PLTR"],
    "Energy": ["XOM","CVX","NEE","SLB","COP","EOG","ENB","ET"],
    "Biotech": ["MRNA","BNTX","CRSP","VRTX","REGN","ILMN","NBIX","ALNY","BIIB","GILD"],
    "Space": ["RKLB","SPCE","ASTS"]
}

# ---------------- DATA ----------------

def get_price_data(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    return requests.get(url).json()

# ---------------- TECH ----------------

def technical_score(symbol):
    try:
        data = get_price_data(symbol)
        c = data.get("c")
        pc = data.get("pc")
        if not c or not pc:
            return 0

        score = 0
        if c > pc: score += 1
        if (c - pc)/pc > 0.02: score += 1
        if c > pc * 1.01: score += 1
        if c > pc * 0.98: score += 1
        if c > pc * 1.03: score += 1

        return score
    except:
        return 0

# ---------------- FLOW ----------------

def smart_money_score(symbol):
    try:
        data = get_price_data(symbol)
        c = data.get("c")
        pc = data.get("pc")

        if not c or not pc:
            return 0, "No data"

        change = (c - pc) / pc
        score = 0

        if change > 0.01: score += 1
        if change > 0.02: score += 1
        if change > 0.03: score += 1
        if change > 0.05: score += 2

        if score >= 4:
            return score, "🔥 Strong Buying Pressure"
        elif score >= 2:
            return score, "📈 Accumulation"
        else:
            return score, "😐 Weak Flow"

    except:
        return 0, "Error"

# ---------------- SENTIMENT ----------------

def sentiment_score(symbol):
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        news = requests.get(url).json()

        score = 0
        for article in news[:20]:
            if symbol.lower() in article.get("headline","").lower():
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

        for e in data.get("earningsCalendar", []):
            if e.get("symbol") == symbol:
                return 3, f"📅 Earnings ({e.get('date')})"

        return 0, "No Catalyst"
    except:
        return 0, "Error"

# ---------------- EDGE CATALYSTS ----------------

def space_catalyst(symbol):
    return (2, "🚀 Space Activity") if symbol in ["RKLB","SPCE","ASTS"] else (0,"")

def defense_catalyst(symbol):
    return (2, "🛡 Defense Flow") if symbol in ["LMT","RTX","NOC","GD","PLTR","LHX"] else (0,"")

def biotech_catalyst(symbol):
    return (2, "💊 FDA Catalyst") if symbol in ["MRNA","BNTX","CRSP","VRTX","REGN"] else (0,"")

# ---------------- AI SCORE ----------------

def ai_score(tech, flow, sent, cat, edge):
    score = (
        tech * 0.25 +
        flow * 0.30 +
        sent * 0.15 +
        cat * 0.15 +
        edge * 0.15
    )
    return round(score, 2)

# ---------------- CRASH DETECTOR ----------------

def market_crash_signal():
    try:
        spy = get_price_data("SPY")
        qqq = get_price_data("QQQ")

        sp = (spy.get("c") - spy.get("pc")) / spy.get("pc")
        qq = (qqq.get("c") - qqq.get("pc")) / qqq.get("pc")

        if sp < -0.02 and qq < -0.02:
            return "🔴 RISK-OFF: Market under pressure"
        elif sp > 0.01 and qq > 0.01:
            return "🟢 RISK-ON: Bullish conditions"
        else:
            return "🟡 NEUTRAL MARKET"

    except:
        return "Market data unavailable"

# ---------------- BOT ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Bot Online 🚀")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):

    results = []
    sector_scores = {}

    for sector, tickers in stocks.items():
        total_sector = 0

        for stock in tickers:
            tech = technical_score(stock)
            flow, fs = smart_money_score(stock)
            sent, ss = sentiment_score(stock)
            cat, cs = catalyst_score(stock)

            sp, _ = space_catalyst(stock)
            df, _ = defense_catalyst(stock)
            bt, _ = biotech_catalyst(stock)

            edge = sp + df + bt
            total = tech + flow + sent + cat + edge
            ai = ai_score(tech, flow, sent, cat, edge)

            total_sector += total

            results.append((stock, sector, total, ai, tech, flow, sent, cat, edge, fs, ss, cs))

        sector_scores[sector] = round(total_sector / len(tickers), 1)

    results.sort(key=lambda x: x[3], reverse=True)  # sort by AI score

    message = "🚨 FULL ALPHA SCAN (AI MODE)\n\n"
    message += f"{market_crash_signal()}\n\n"

    message += "📊 TOP SECTORS:\n"
    for sec, sc in sorted(sector_scores.items(), key=lambda x: x[1], reverse=True):
        message += f"{sec}: {sc}\n"

    message += "\n🔥 TOP 8 PLAYS:\n\n"

    for r in results[:8]:
        stock, sector, total, ai, tech, flow, sent, cat, edge, fs, ss, cs = r

        message += (
            f"{stock} ({sector})\n"
            f"AI Score: {ai} | Total: {total}/25\n\n"
            f"Technical: {tech}/5\n"
            f"Smart Money Flow: {flow}/5\n"
            f"Sentiment: {sent}/5\n"
            f"Catalyst: {cat}/5\n"
            f"Edge Catalysts: {edge}/5\n\n"
            f"{fs}\n{ss}\n{cs}\n\n"
        )

    await update.message.reply_text(message)

# ---------------- AUTO DAILY ----------------

async def auto_scan(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=8655837636, text="⏰ Daily Alpha Scan Running...")
    await scan(type('obj', (object,), {"message": None}), context)

# ---------------- RUN ----------------

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.job_queue.run_daily(auto_scan, time=time(hour=14, minute=45))

app.run_polling()
