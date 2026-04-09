from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import requests
from datetime import time

TOKEN = os.getenv("BOT_TOKEN")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

CHAT_ID = 8655837636

stocks = {
    "AI": ["NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "SMCI"],
    "Semiconductors": ["TSM", "ASML", "AVGO", "MU", "INTC"],
    "Defense": ["LMT", "RTX", "NOC", "GD"],
    "Space": ["RKLB", "SPCE"],
    "Energy": ["XOM", "CVX", "SLB", "NEE"],
    "Biotech": ["MRNA", "BNTX", "VRTX", "CRSP"]
}

def get_price(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    return requests.get(url).json()

# -------- TECH --------
def technical_score(symbol):
    data = get_price(symbol)
    c = data.get("c")
    pc = data.get("pc")

    if not c or not pc:
        return 0

    score = 0
    if c > pc: score += 1
    if (c - pc) / pc > 0.02: score += 1
    if c > pc * 1.01: score += 1
    if c > pc * 0.98: score += 1
    if c > pc * 1.03: score += 1

    return score

# -------- FLOW --------
def smart_money(symbol):
    data = get_price(symbol)
    c = data.get("c")
    pc = data.get("pc")

    if not c or not pc:
        return 0, "No Data"

    change = (c - pc) / pc

    score = 0
    if change > 0.01: score += 1
    if change > 0.02: score += 1
    if change > 0.03: score += 1
    if change > 0.05: score += 2

    if score >= 4:
        signal = "🔥 Strong Buying Pressure"
    elif score >= 2:
        signal = "📈 Accumulation"
    else:
        signal = "😐 Weak Flow"

    return min(score, 5), signal

# -------- OPTIONS FLOW (PROXY) --------
def options_flow(symbol):
    data = get_price(symbol)
    c = data.get("c")
    pc = data.get("pc")

    if not c or not pc:
        return 0, "No Data"

    move = (c - pc) / pc

    score = 0

    if move > 0.02:
        score += 2
    if move > 0.04:
        score += 2
    if move > 0.06:
        score += 1

    if score >= 4:
        signal = "💰 Heavy Options Activity"
    elif score >= 2:
        signal = "📊 Unusual Options Interest"
    else:
        signal = "😐 Normal Options"

    return min(score, 5), signal

# -------- SENTIMENT --------
def sentiment(symbol):
    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
    news = requests.get(url).json()

    score = 0
    for n in news[:10]:
        if symbol.lower() in n.get("headline", "").lower():
            score += 1

    if score >= 5:
        return 5, "🔥 High Hype"
    elif score >= 2:
        return score, "📢 Building Attention"
    else:
        return score, "😐 Low Buzz"

# -------- AI SCORE V2 --------
def ai_score(tech, flow, sent, opt):
    score = (
        tech * 0.25 +
        flow * 0.35 +
        opt * 0.25 +
        sent * 0.15
    )
    return round(score, 2)

# -------- CRASH DETECTOR --------
def crash_detector(results):
    weak = sum(1 for r in results if r[2] < 6)
    return weak > len(results) * 0.6

# -------- SCAN --------
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = []

    for sector, tickers in stocks.items():
        for stock in tickers:
            tech = technical_score(stock)
            flow, flow_signal = smart_money(stock)
            opt, opt_signal = options_flow(stock)
            sent, sent_signal = sentiment(stock)

            ai = ai_score(tech, flow, sent, opt)
            total = tech + flow + sent + opt

            results.append((stock, sector, total, tech, flow, sent, opt, ai, flow_signal, sent_signal, opt_signal))

    results.sort(key=lambda x: x[7], reverse=True)

    crash = crash_detector(results)

    msg = "🚨 FULL ALPHA SCAN (AI V2 + OPTIONS FLOW)\n\n"

    if crash:
        msg += "⚠️ MARKET WARNING: Weak conditions\n\n"

    msg += "🔥 TOP PLAYS:\n\n"

    for r in results[:8]:
        stock, sector, total, tech, flow, sent, opt, ai, flow_sig, sent_sig, opt_sig = r

        msg += (
            f"{stock} ({sector})\n"
            f"AI Score: {ai} | Total: {total}/20\n\n"
            f"Technical: {tech}/5\n"
            f"Flow: {flow}/5\n"
            f"Options: {opt}/5\n"
            f"Sentiment: {sent}/5\n\n"
            f"{flow_sig}\n{opt_sig}\n{sent_sig}\n\n"
        )

    await update.message.reply_text(msg)

# -------- ALERT SYSTEM --------
async def auto_scan(context: ContextTypes.DEFAULT_TYPE):
    alerts = []

    for sector, tickers in stocks.items():
        for stock in tickers:
            tech = technical_score(stock)
            flow, _ = smart_money(stock)
            opt, _ = options_flow(stock)
            sent, _ = sentiment(stock)

            ai = ai_score(tech, flow, sent, opt)

            if ai >= 3.5 or flow >= 4 or opt >= 4:
                alerts.append((stock, sector, ai, tech, flow, opt, sent))

    if not alerts:
        return

    alerts.sort(key=lambda x: x[2], reverse=True)

    msg = "🚨 HIGH-CONVICTION SIGNALS\n\n"

    for a in alerts:
        stock, sector, ai, tech, flow, opt, sent = a

        msg += (
            f"{stock} ({sector})\n"
            f"AI Score: {ai}\n"
            f"T:{tech} F:{flow} O:{opt} S:{sent}\n\n"
        )

    await context.bot.send_message(chat_id=CHAT_ID, text=msg)

# -------- START --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner AI V2 + Options Online 🚀")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.job_queue.run_daily(auto_scan, time=time(hour=14, minute=0))

app.run_polling()
