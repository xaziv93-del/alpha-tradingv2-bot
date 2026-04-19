from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import requests
from datetime import time
import json
from upstash_redis import Redis

TOKEN = os.getenv("BOT_TOKEN")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

REDIS = Redis(
    url=os.getenv("REDIS_URL"),
    token=os.getenv("REDIS_TOKEN"),
)

CHAT_ID = 8655837636

# -------- EXPANDED STOCK UNIVERSE (~60) --------
stocks = {
    "AI": ["NVDA","AMD","MSFT","GOOGL","AMZN","SMCI","META","ORCL","ADBE","CRM"],
    "Semiconductors": ["TSM","ASML","AVGO","MU","INTC","QCOM","TXN","LRCX","KLAC","AMAT"],
    "Defense": ["LMT","RTX","NOC","GD","BA","PLTR","HII","LHX"],
    "Space": ["RKLB","SPCE","ASTS","IRDM","MAXR"],
    "Energy": ["XOM","CVX","SLB","NEE","COP","EOG","OXY","BP"],
    "Biotech": ["MRNA","BNTX","VRTX","CRSP","REGN","GILD","AMGN","ILMN","BIIB"],
    "Quantum": ["IONQ","QBTS","RGTI","IBM","GOOGL","MSFT","AMZN"]
}

# -------- FLOW MEMORY --------
def load_flow_data():
    data = REDIS.get("flow_data")
    if not data:
        return {}
    return data if isinstance(data, dict) else json.loads(data)

def save_flow_data(data):
    REDIS.set("flow_data", json.dumps(data))

# -------- PERSISTENCE MEMORY --------
def load_persistence():
    data = REDIS.get("persistence_data")
    if not data:
        return {}
    return data if isinstance(data, dict) else json.loads(data)

def save_persistence(data):
    REDIS.set("persistence_data", json.dumps(data))

# -------- PERSISTENCE ENGINE --------
def persistence_signal(symbol, early_vol, prev_data):
    prev_count = prev_data.get(symbol, 0)

    if "⚡" in early_vol:
        new_count = prev_count + 1
    else:
        new_count = 0

    if new_count >= 3:
        signal = "🔥⚡ Persistent Early Momentum"
    elif new_count == 2:
        signal = "👀 Building Pressure"
    else:
        signal = ""

    return new_count, signal

# -------- DATA --------
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

# -------- FLOW CHANGE --------
def flow_change_signal(symbol, current_flow, prev_data):
    prev_flow = prev_data.get(symbol, 0)
    change = current_flow - prev_flow

    if change >= 2:
        return "🚀 Flow Surge"
    elif change == 1:
        return "📈 Increasing Flow"
    elif change == 0:
        return "😐 Stable Flow"
    else:
        return "⚠️ Decreasing Flow"

# -------- OPTIONS FLOW --------
def options_flow(symbol):
    data = get_price(symbol)
    c = data.get("c")
    pc = data.get("pc")

    if not c or not pc:
        return 0, "No Data"

    move = (c - pc) / pc

    score = 0
    if move > 0.02: score += 2
    if move > 0.04: score += 2
    if move > 0.06: score += 1

    if score >= 4:
        signal = "💰 Heavy Options Activity"
    elif score >= 2:
        signal = "📊 Unusual Options Interest"
    else:
        signal = "😐 Normal Options"

    return min(score, 5), signal

# -------- COMBO SIGNAL (NEW) --------
def combo_signal(flow, flow_change, opt):
    if ("🚀" in flow_change or "📈" in flow_change) and opt >= 3:
        return "🚀💰 Institutional Activity Detected"
    elif opt >= 4 and flow >= 3:
        return "💰 Strong Options + Flow"
    else:
        return ""

# -------- EARLY VOLATILITY --------
def early_volatility_signal(flow, flow_change, opt, sent):
    if (
        ("🚀" in flow_change or "📈" in flow_change)
        and opt >= 2
        and sent <= 2
    ):
        return "⚡ Early Volatility Detected"
    return ""
    
# -------- SENTIMENT --------
def sentiment(symbol):
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        news = requests.get(url).json()

        score = 0
        hype_words = [
            "surge","rally","soars","breakout",
            "beats","bullish","upgrade","strong",
            "explosive","record","momentum"
        ]

        for article in news[:20]:
            headline = article.get("headline", "").lower()

            if symbol.lower() in headline:
                score += 1
                for word in hype_words:
                    if word in headline:
                        score += 1

        score = min(score, 5)

        if score >= 4:
            signal = "🔥 Viral Hype Building"
        elif score >= 2:
            signal = "📢 Social Attention Rising"
        else:
            signal = "😐 No Hype"

        return score, signal

    except:
        return 0, "Error"

# -------- AI SCORE --------
def ai_score(tech, flow, sent, opt):
    return round(
        tech * 0.25 +
        flow * 0.35 +
        opt * 0.25 +
        sent * 0.15,
        2
    )

# -------- NO TRADE DAY --------
def no_trade_day(results):
    total = len(results)

    low_scores = sum(1 for r in results if r[2] < 6)
    weak_flow = sum(1 for r in results if r[4] <= 1)

    strong = [
        r for r in results
        if r[4] >= 3 and r[6] >= 3 and r[2] >= 10
    ]

    return (
        low_scores > total * 0.6 and
        weak_flow > total * 0.6 and
        len(strong) == 0
    )

# -------- SCAN --------
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):

    prev_data = load_flow_data()
    persist_prev = load_persistence()

    new_data = {}
    persist_new = {}

    results = []

    for sector, tickers in stocks.items():
        for stock in tickers:
            tech = technical_score(stock)
            flow, flow_sig = smart_money(stock)
            opt, opt_sig = options_flow(stock)
            sent, sent_sig = sentiment(stock)

            flow_change = flow_change_signal(stock, flow, prev_data)
            combo = combo_signal(flow, flow_change, opt)
            early_vol = early_volatility_signal(flow, flow_change, opt, sent)
            persist_count, persist_sig = persistence_signal(stock, early_vol, persist_prev)
            persist_new[stock] = persist_count
            
            total = tech + flow + sent + opt
            ai = ai_score(tech, flow, sent, opt)

            results.append(
            (stock, sector, total, tech, flow, sent, opt, ai, flow_sig, sent_sig, opt_sig, flow_change, combo, early_vol, persist_sig)
            
            )

            new_data[stock] = flow

    save_flow_data(new_data)
    save_persistence(persist_new)
    
    results.sort(key=lambda x: x[7], reverse=True)

    no_trade = no_trade_day(results)

    msg = "🚨 FULL ALPHA SCAN (FLOW INTELLIGENCE MODE)\n\n"

    if no_trade:
        msg += "🚫 NO TRADE DAY DETECTED\nMarket weak — stay patient 🎯\n\n"

    msg += "🔥 TOP PLAYS:\n\n"

    for r in results[:8]:
        stock, sector, total, tech, flow, sent, opt, ai, fs, ss, os, fc, combo, early_vol, persist_sig = r

        signals = [fs, fc, os, ss, combo, early_vol, persist_sig]
        signals = [s for s in signals if s]

    msg += (
        f"{stock} ({sector})\n"
        f"AI Score: {ai} | Total: {total}/20\n\n"
        f"Technical: {tech}/5\n"
        f"Flow: {flow}/5\n"
        f"Options: {opt}/5\n"
        f"Sentiment: {sent}/5\n\n"
        + "\n".join(signals) + "\n\n"
    )

    await update.message.reply_text(msg)

# -------- ALERTS --------
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
                alerts.append((stock, sector, ai))

    if not alerts:
        return

    alerts.sort(key=lambda x: x[2], reverse=True)

    msg = "🚨 HIGH-CONVICTION SIGNALS\n\n"

    for a in alerts:
        msg += f"{a[0]} ({a[1]}) | AI Score: {a[2]}\n"

    await context.bot.send_message(chat_id=CHAT_ID, text=msg)

# -------- START --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Ready 🚀")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.job_queue.run_daily(auto_scan, time=time(hour=12, minute=0))

app.run_polling()
