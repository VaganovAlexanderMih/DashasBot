import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask
import threading
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MESSAGE_TEXT = "Выпила таблетки?"

chat_file = "chat_id.txt"
chat_id = None
answered = False

# --- Функции для сохранения chat_id ---
def save_chat_id(cid):
    with open(chat_file, "w") as f:
        f.write(str(cid))

def load_chat_id():
    try:
        with open(chat_file) as f:
            return int(f.read())
    except:
        return None

chat_id = load_chat_id()

# --- Flask сервер для Render ---
app_http = Flask("web")

@app_http.route("/")
def index():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_http.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# --- Telegram бота ---
async def send_message(application):
    global chat_id, answered
    if chat_id and not answered:
        await application.bot.send_message(chat_id=chat_id, text=MESSAGE_TEXT)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global answered
    answered = True
    await update.message.reply_text("Спасибо за ответ! Бот больше не будет слать сообщения сегодня.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global chat_id
    if chat_id is None:
        chat_id = update.effective_chat.id
        save_chat_id(chat_id)
        await update.message.reply_text(
            f"Бот запущен. Для установки расписания используй команду /schedule. chat_id={chat_id}"
        )
    else:
        await update.message.reply_text("Бот уже запущен.")

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global answered
    if not chat_id:
        await update.message.reply_text("Сначала отправь /start")
        return

    answered = False  # сбрасываем флаг ответа на новый день
    await update.message.reply_text(
        "Расписание установлено: сообщение будет приходить в 20:40 и каждые 30 минут до ответа."
    )

# --- Создаем приложение ---
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("schedule", schedule))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Настраиваем APScheduler ---
scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Moscow"))

def send_scheduled_message():
    global answered
    if chat_id and not answered:
        asyncio.create_task(app.bot.send_message(chat_id=chat_id, text=MESSAGE_TEXT))

# Ежедневно в 20:00
scheduler.add_job(send_scheduled_message, 'cron', hour=20, minute=40)

# Каждые 30 минут
scheduler.add_job(send_scheduled_message, 'interval', minutes=30)

scheduler.start()

# --- Запуск без asyncio.run, чтобы избежать конфликта event loop ---
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.bot.delete_webhook())
    app.run_polling()
