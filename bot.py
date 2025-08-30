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
async def send_message():
    global chat_id, answered
    if chat_id and not answered:
        await app.bot.send_message(chat_id=chat_id, text=MESSAGE_TEXT)

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
            f"Бот запущен. chat_id={chat_id}"
        )
    else:
        await update.message.reply_text("Бот уже запущен.")

# --- Создаем приложение ---
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Настраиваем APScheduler ---
scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Moscow"))

def scheduled_message_job():
    asyncio.create_task(send_message())

def reset_answered_flag():
    global answered
    answered = False

# Отправка сообщения каждый день в 20:00
scheduler.add_job(scheduled_message_job, 'cron', hour=20, minute=0)

# Повтор каждые 30 минут
scheduler.add_job(scheduled_message_job, 'interval', minutes=30)

# Сброс флага answered каждый день в 18:30
scheduler.add_job(reset_answered_flag, 'cron', hour=18, minute=30)

scheduler.start()

# --- Запуск ---
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.bot.delete_webhook())
    app.run_polling()
