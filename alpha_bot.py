from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import requests
from datetime import datetime, time
import pytz
import json
from upstash_redis import Redis

TOKEN = os.getenv("BOT_TOKEN")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

REDIS = Redis(
    url=os.getenv("REDIS_URL"),
    token=os.getenv("REDIS_TOKEN"),
)

MIN_SECTOR_STRENGTH = 0.5

CHAT_ID = 8655837636

price_cache = {}
news_cache = None

# -------- EXPANDED STOCK UNIVERSE (~150) --------
stocks = {

    "AI": ["NVDA","AMD","MSFT","GOOGL","AMZN","META","ORCL","ADBE","CRM","SMCI","SNOW","PLTR"], 
    "Semiconductors": ["TSM","ASML","AVGO","MU","INTC","QCOM","TXN","LRCX","KLAC","AMAT","ON","MCHP"],
    "Defense": ["LMT","RTX","NOC","GD","BA","PLTR","HII","LHX","KTOS","AVAV"],
    "Space": ["RKLB","SPCE","ASTS","IRDM","SATL","VSAT"],
    "Energy": ["XOM","CVX","SLB","COP","EOG","OXY","BP","HAL","DVN","FANG"],
    "Biotech": ["MRNA","BNTX","VRTX","CRSP","REGN","GILD","AMGN","ILMN","BIIB","SGEN"],
    "Quantum": ["IONQ","QBTS","RGTI","IBM","GOOGL","MSFT","AMZN"],
    "Momentum": ["TSLA","COIN","MSTR","RBLX","SHOP","SQ","ROKU","AFRM","UPST","DKNG"],
    "Finance": ["JPM","GS","MS","BAC","C","SCHW","PYPL","V","MA"],
    "ETF": ["SPY","QQQ","IWM","SMH","XLE","XLK","ARKK"]
}

# -------- FLOW MEMORY --------
def load_flow_data():
    data = REDIS.get("flow_data")
    if not data:
        return {}
    return data if isinstance(data, dict) else json.loads(data)

def save_flow_data(data):
    REDIS.set("flow_data", json.dumps(data))

def load_alerts():
    data = REDIS.get("alerted_stocks")
    if not data:
        return {}
    return data if isinstance(data, dict) else json.loads(data)

def save_alerts(data):
    REDIS.set("alerted_stocks", json.dumps(data))

# -------- MOMENTUM MEMORY --------
def load_momentum():
    data = REDIS.get("momentum_data")
    if not data:
        return {}

    return data if isinstance(data, dict) else json.loads(data)


def save_momentum(data):
    REDIS.set("momentum_data", json.dumps(data))

# -------- WATCHLIST MEMORY --------
def load_watchlist():
    data = REDIS.get("watchlist_data")
    if not data:
        return {}

    return data if isinstance(data, dict) else json.loads(data)


def save_watchlist(data):
    REDIS.set("watchlist_data", json.dumps(data))

# -------- WATCHLIST MEMORY --------
def watchlist_signal(symbol, ai, prev_data):
    today = datetime.utcnow().strftime("%Y-%m-%d")

    stock_data = prev_data.get(
        symbol,
        {
            "count": 0,
            "day": ""
        }
    )

    count = stock_data["count"]
    last_day = stock_data["day"]

    signal = ""

    if ai >= 3.5:

        # only count once per day
        if last_day != today:
            count += 1
            last_day = today

    else:
        count = 0

    if count >= 3:
        signal = "🔥 Sector Leader"

    elif count == 2:
        signal = "👀 Emerging Leader"

    return {
        "count": count,
        "day": last_day
    }, signal

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
    if symbol in price_cache:
        return price_cache[symbol]

    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    data = requests.get(url).json()

    price_cache[symbol] = data
    return data

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
    
# -------- MOMENTUM ENGINE --------
def momentum_signal(symbol, ai, prev_data):
    today = datetime.utcnow().strftime("%Y-%m-%d")

    stock_data = prev_data.get(symbol)

    # backward compatibility
    if isinstance(stock_data, list):
        stock_data = {
            "history": stock_data,
            "day": ""
        }

    if not stock_data:
        stock_data = {
            "history": [],
            "day": ""
        }

    history = stock_data["history"]
    last_day = stock_data["day"]

    # only once per day
    if last_day != today:
        history.append(ai)
        history = history[-3:]
        last_day = today

    signal = ""

    if len(history) == 3:

        if history[0] < history[1] < history[2]:
            signal = "🚀 Accelerating Alpha"

        elif history[0] > history[1] > history[2]:
            signal = "⚠️ Momentum Cooling"

        elif history[0] < 1 and history[2] >= 4:
            signal = "💥 Breakout Candidate"

    return {
        "history": history,
        "day": last_day
    }, signal

# -------- EXPLOSIVE SETUP --------
def explosive_setup_signal(flow, opt, sent, persist_count):

    if (
        flow >= 3
        and opt >= 2
        and sent <= 2
        and persist_count >= 2
    ):
        return "⚡💰 Hidden Momentum"

    return ""

# -------- SENTIMENT --------
def sentiment(symbol):
    try:
        global news_cache

        if news_cache is None:
            url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
            news_cache = requests.get(url).json()

        news = news_cache

        score = 0
        mentions = 0

        positive_words = [
            "surge","rally","soars","breakout","beats",
            "bullish","upgrade","strong","record","momentum",
            "growth","expansion","outperform"
        ]

        negative_words = [
            "drop","falls","miss","downgrade","weak",
            "lawsuit","risk","decline","cut","bearish",
            "loss","warning"
        ]

        for article in news[:30]:
            headline = article.get("headline", "").lower()
            summary = article.get("summary", "").lower()

            text = headline + " " + summary

            # 🎯 RELEVANCE FILTER (strong upgrade)
            if symbol.lower() not in text:
                continue

            mentions += 1

            for word in positive_words:
                if word in text:
                    score += 1

            for word in negative_words:
                if word in text:
                    score -= 1

        # 🧠 Normalize score
        if mentions == 0:
            return 0, "😐 No Coverage"

        norm_score = score / mentions

        # 🎯 FINAL SIGNAL
        if norm_score >= 1:
            signal = "🔥 Strong Bullish Sentiment"
            final_score = 5
        elif norm_score >= 0.3:
            signal = "📈 Bullish Bias"
            final_score = 3
        elif norm_score <= -1:
            signal = "💀 Strong Bearish Sentiment"
            final_score = 0
        elif norm_score <= -0.3:
            signal = "📉 Bearish Bias"
            final_score = 1
        else:
            signal = "😐 Neutral Sentiment"
            final_score = 2

        return final_score, signal

    except:
        return 0, "Error"

# -------- AI SCORE --------
def ai_score_v3(tech, flow, sent, opt, early_vol, persist_count):
    score = (
        tech * 0.2 +
        flow * 0.3 +
        opt * 0.2 +
        sent * 0.1
    )

    # ⚡ Early volatility boost
    if "⚡" in early_vol:
        score += 0.5

    # 🔁 Persistence boost
    if persist_count >= 3:
        score += 1.5
    elif persist_count == 2:
        score += 1
    elif persist_count == 1:
        score += 0.3

    # 🚀 Flow expansion bonus
    if flow >= 4:
        score += 0.5

    # ⚠️ Weak flow penalty
    if flow <= 1:
        score -= 0.5

    return round(score, 2)

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

def pre_filter(stock):
    data = get_price(stock)
    c = data.get("c")
    pc = data.get("pc")

    if not c or not pc:
        return False

    change = abs((c - pc) / pc)

    tech = technical_score(stock)
    flow, _ = smart_money(stock)

    # 🔥 HARD FILTER
    if c < 5:
        return False

    # 💤 DEAD MARKET
    if change < 0.005:
        return tech >= 2 or flow >= 2

    # 🚀 ACTIVE MARKET
    if change >= 0.005:
        return tech >= 1 or flow >= 1

    return True

# -------- SCAN --------
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
    price_cache.clear()
    prev_data = load_flow_data()
    persist_prev = load_persistence()
    momentum_prev = load_momentum()
    
    watch_prev = load_watchlist()
    watch_new = {}
    
    new_data = {}
    persist_new = {}
    results = []

    for sector, tickers in stocks.items():
        for stock in tickers:

            # 🔪 PRE-FILTER
            if not pre_filter(stock):
                continue

            tech = technical_score(stock)
            flow, flow_sig = smart_money(stock)
            opt, opt_sig = options_flow(stock)
            sent, sent_sig = sentiment(stock)

            flow_change = flow_change_signal(stock, flow, prev_data)
            combo = combo_signal(flow, flow_change, opt)
            early_vol = early_volatility_signal(flow, flow_change, opt, sent)

            persist_count, persist_sig = persistence_signal(stock, early_vol, persist_prev)
            persist_new[stock] = persist_count

            explosive_sig = explosive_setup_signal(flow, opt, sent, persist_count)
            
            total = tech + flow + sent + opt
            ai = ai_score_v3(tech, flow, sent, opt, early_vol, persist_count)

            momentum_history, momentum_sig = momentum_signal(stock, ai, momentum_prev)
            
            watch_data, watch_sig = watchlist_signal(
                stock,
                ai,
                watch_prev
            )

            watch_new[stock] = watch_data
            
            results.append(
                (stock, sector, total, tech, flow, sent, opt, ai,
                 flow_sig, sent_sig, opt_sig, flow_change,
                 combo, early_vol, persist_sig, watch_sig, explosive_sig, momentum_sig)
            )

            new_data[stock] = flow

    # -------- SECTOR STRENGTH --------
    sector_scores = {}

    for r in results:
        sector = r[1]
        ai = r[7]

        if sector not in sector_scores:
            sector_scores[sector] = []

        sector_scores[sector].append(ai)
    
    if not sector_scores:
        await update.message.reply_text(
            "🚫 No valid setups found today.\nMarket quiet or filters too strict."
        )
        return
    
    # normalize sectors
    max_score = max(sum(vals)/len(vals) for vals in sector_scores.values())

    sector_avg = {
        s: round((sum(vals)/len(vals)) / max_score, 2)
        for s, vals in sector_scores.items()
    }

    STRONG_SECTORS = {
    s for s, score in sector_avg.items()
    if score >= MIN_SECTOR_STRENGTH
    }
    
    # -------- SAVE MEMORY --------
    save_flow_data(new_data)
    save_persistence(persist_new)

    save_momentum({
        r[0]: momentum_signal(
            r[0],
            r[7],
            momentum_prev
        )[0]
        for r in results
    })

    save_watchlist(watch_new)

    # -------- SORT --------
    results.sort(key=lambda x: x[7], reverse=True)
    no_trade = no_trade_day(results)

    # -------- BUILD MESSAGE --------
    msg = "🚨 FULL ALPHA SCAN (FLOW INTELLIGENCE MODE)\n\n"

    # 📊 Sector strength
    msg += "📊 SECTOR STRENGTH:\n\n"
    top_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)

    for s, score in top_sectors[:5]:
        msg += f"{s}: {score}\n"

    msg += "\n"

    # 🚫 No trade filter
    if no_trade:
        msg += "🚫 NO TRADE DAY DETECTED\nMarket weak — stay patient 🎯\n\n"

    msg += "🔥 TOP PLAYS:\n\n"

    # -------- TOP STOCKS --------
    filtered_results = [
        r for r in results
        if r[1] in STRONG_SECTORS
    ]

    for r in filtered_results[:8]:
        stock, sector, total, tech, flow, sent, opt, ai, fs, ss, os, fc, combo, early_vol, persist_sig, watch_sig, explosive_sig, momentum_sig = r

        signals = [fs, fc, os, ss, combo, early_vol, persist_sig, watch_sig, explosive_sig, momentum_sig]
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
    except Exception as e:
            await update.message.reply_text(
                f"DEBUG ERROR:\n{str(e)}"
        )

# -------- ALERTS --------
async def auto_scan(context: ContextTypes.DEFAULT_TYPE):
    global news_cache
    news_cache = None  # 🔥 reset news each run

    prev_alerts = load_alerts()
    new_alerts = {}

    alerts = []

    # -------- BUILD TEMP RESULTS + SECTOR STRENGTH --------
    sector_scores = {}
    temp_results = []

    for sector, tickers in stocks.items():
        for stock in tickers:

            if not pre_filter(stock):
                continue

            tech = technical_score(stock)
            flow, _ = smart_money(stock)
            opt, _ = options_flow(stock)
            sent, _ = sentiment(stock)

            ai = ai_score_v3(tech, flow, sent, opt, "", 0)

            temp_results.append((stock, sector, ai, flow, opt, tech))

            if sector not in sector_scores:
                sector_scores[sector] = []

            sector_scores[sector].append(ai)

    # -------- NORMALIZE SECTORS --------
    if not sector_scores:
        return

    max_score = max(sum(vals)/len(vals) for vals in sector_scores.values())

    sector_avg = {
        s: round((sum(vals)/len(vals)) / max_score, 2)
        for s, vals in sector_scores.items()
    }

    STRONG_SECTORS = {
        s for s, score in sector_avg.items()
        if score >= MIN_SECTOR_STRENGTH
    }

    # -------- ALERT LOGIC --------
    for stock, sector, ai, flow, opt, tech in temp_results:

        # 🔥 SECTOR FILTER
        if sector not in STRONG_SECTORS:
            continue

        prev_ai = prev_alerts.get(stock, 0)

        is_new = False

        # 🚀 MAIN TRIGGER
        if ai >= 3.5 and flow >= 3 and opt >= 3 and tech >= 3 and prev_ai < 3.5:
            is_new = True

        # 💰 FLOW TRIGGER
        elif flow >= 4 and prev_ai < 2:
            is_new = True

        # 💰 OPTIONS TRIGGER
        elif opt >= 4 and prev_ai < 2:
            is_new = True

        if is_new:
            alerts.append((stock, sector, ai))

        new_alerts[stock] = ai

    # -------- SAVE --------
    save_alerts(new_alerts)

    if not alerts:
        return

    alerts.sort(key=lambda x: x[2], reverse=True)

    # -------- MESSAGE --------
    msg = "🚨 NEW OPPORTUNITIES DETECTED\n\n"

    for stock, sector, ai in alerts:
        msg += f"{stock} ({sector}) | AI Score: {ai}\n"

    await context.bot.send_message(chat_id=CHAT_ID, text=msg)
# -------- START --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Ready 🚀")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.job_queue.run_daily(
    auto_scan,
    time=time(hour=14, minute=0, tzinfo=pytz.timezone("Europe/Stockholm"))
)

app.run_polling()
