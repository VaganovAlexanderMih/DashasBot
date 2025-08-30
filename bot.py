import asyncio
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask
import threading

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MESSAGE_TEXT = "Выпила таблетки?"

chat_file = "chat_id.txt"
chat_id = None
answered = False
task = None

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
    global answered, task
    answered = True
    if task:
        task.cancel()
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
    global task
    if not chat_id:
        await update.message.reply_text("Сначала отправь /start")
        return

    now = datetime.now()
    target_time = now.replace(hour=20, minute=0, second=0, microsecond=0)
    if now > target_time:
        target_time += timedelta(days=1)
    delay_seconds = (target_time - now).total_seconds()

    await update.message.reply_text(
        f"Сообщение будет отправлено в {target_time.strftime('%H:%M:%S')} и далее каждые 30 минут до ответа."
    )

    async def repeated_messages():
        await asyncio.sleep(delay_seconds)
        while not answered:
            await send_message(context.application)
            await asyncio.sleep(1800)  # 30 минут

    task = asyncio.create_task(repeated_messages())

# --- Создаем приложение ---
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("schedule", schedule))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Запуск без asyncio.run, чтобы избежать конфликта event loop ---
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.bot.delete_webhook())
    app.run_polling()
