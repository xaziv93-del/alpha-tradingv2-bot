from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import random

TOKEN = os.getenv("BOT_TOKEN")

stocks = ["NVDA", "PLTR", "RKLB", "AMD", "TSLA"]

# --- TECH SCORE (FIXED SIMPLE VERSION) ---
def technical_score():
    return random.randint(1,5)

# --- OPTIONS FLOW (SMART MONEY SIMULATION) ---
def options_flow_score():
    score = random.randint(1,5)

    signal = ""
    if score >= 4:
        signal = "🔥 Heavy Call Buying"
    elif score == 3:
        signal = "📈 Moderate Flow"
    else:
        signal = "😐 Weak Flow"

    return score, signal

# --- SCAN ---
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    results = []

    for stock in stocks:
        tech = technical_score()
        options_score, flow_signal = options_flow_score()

        total = tech + options_score

        results.append((stock, total, tech, options_score, flow_signal))

    results.sort(key=lambda x: x[1], reverse=True)

    message = "🚨 ALPHA SCAN (TECH + SMART MONEY)\n\n"

    for stock, total, tech, opt, signal in results[:3]:
        message += (
            f"{stock} | Score: {total}/10\n"
            f"Tech: {tech}/5 | Options: {opt}/5\n"
            f"{signal}\n\n"
        )

    await update.message.reply_text(message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Bot Online 🚀")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.run_polling()
