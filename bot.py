import asyncio
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Токен из переменных окружения Render
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Сообщение для рассылки
MESSAGE_TEXT = "Выпила таблетки?"

# Переменные для работы
chat_id = None
answered = False
task = None  # Для хранения задачи asyncio

# Функция отправки сообщения
async def send_message(application):
    global chat_id, answered
    if chat_id and not answered:
        await application.bot.send_message(chat_id=chat_id, text=MESSAGE_TEXT)

# Обработчик любых текстовых сообщений (от пользователя)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global answered, task
    answered = True
    if task:
        task.cancel()  # отменяем повторяющиеся сообщения
    await update.message.reply_text("Спасибо за ответ! Бот больше не будет слать сообщения.")

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global chat_id
    if chat_id == None:
        chat_id = update.effective_chat.id
    await update.message.reply_text(
        "Бот запущен. Для установки расписания используй команду /schedule"
    )

# Команда /schedule
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global task

    if not chat_id:
        await update.message.reply_text("Сначала отправь /start")
        return

    # Вычисляем время следующего 19:00
    now = datetime.now()
    target_time = now.replace(hour=19, minute=0, second=0, microsecond=0)
    if now > target_time:
        target_time += timedelta(days=1)
    delay_seconds = (target_time - now).total_seconds()

    await update.message.reply_text(
        f"Сообщение будет отправлено в {target_time.strftime('%H:%M:%S')} и далее каждые 30 минут до ответа."
    )

    # Создаем асинхронную задачу для повторяющихся сообщений
    async def repeated_messages():
        await asyncio.sleep(delay_seconds)  # ждём до 19:00
        while not answered:
            await send_message(context.application)
            await asyncio.sleep(1800)  # повтор каждые 30 минут

    task = asyncio.create_task(repeated_messages())

# Основная функция
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
