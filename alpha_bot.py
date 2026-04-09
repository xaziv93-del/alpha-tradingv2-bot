from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import random

TOKEN = os.getenv("BOT_TOKEN")

# --- MOCK DATA (we replace later with real data) ---
stocks = ["NVDA", "PLTR", "RKLB", "TSLA", "AMD"]

def alpha_score():
    return {
        "technical": random.randint(1,5),
        "sentiment": random.randint(1,5),
        "options": random.randint(1,5),
        "catalyst": random.randint(1,5),
        "asymmetry": random.randint(1,5)
    }

def total_score(scores):
    return sum(scores.values())

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Alpha Scanner Bot Online 🚀")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    results = []

    for stock in stocks:
        scores = alpha_score()
        total = total_score(scores)

        results.append((stock, total, scores))

    results.sort(key=lambda x: x[1], reverse=True)

    message = "🚨 TOP ALPHA PLAYS TODAY\n\n"

    for stock, total, scores in results[:3]:
        message += f"{stock} | Score: {total}/25\n"

    await update.message.reply_text(message)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("scan", scan))

app.run_polling()
