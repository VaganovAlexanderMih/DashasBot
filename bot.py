import time
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Токен твоего бота
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Сообщение, которое бот будет отправлять
message_text = "Выпила таблетки?"

# ID чата для отправки сообщений
chat_id = None

# Переменная для отслеживания, был ли ответ
answered = False

# Функция, которая отправляет сообщение
def send_message(context: CallbackContext):
    global chat_id, answered
    if chat_id and not answered:
        context.bot.send_message(chat_id=chat_id, text=message_text)

# Функция для отслеживания сообщений
def handle_message(update, context: CallbackContext):
    global answered
    answered = True
    update.message.reply_text('Спасибо за ответ! Бот больше не будет отправлять сообщения.')

# Функция для старта бота
def start(update, context: CallbackContext):
    global chat_id
    if (chat_id == None):
        chat_id = update.message.chat_id
    update.message.reply_text("Бот запущен и будет отправлять сообщения каждый день в 19:00, пока не получит ответ.")

# Функция для настройки расписания
def set_schedule(update, context: CallbackContext):
    job_queue = context.job_queue

    # Вычисляем, когда нужно отправить первое сообщение (19:00 сегодня или завтра)
    now = datetime.now()
    target_time = now.replace(hour=19, minute=0, second=0, microsecond=0)

    if now > target_time:  # Если текущее время уже прошло 19:00, отправим сообщение завтра
        target_time += timedelta(days=1)

    # Планируем первое сообщение
    job_queue.run_once(send_message, target_time)

    # Планируем повторяющиеся сообщения каждую половину часа
    job_queue.run_repeating(send_message, interval=1800, first=target_time)

    update.message.reply_text(f"Сообщение будет отправлено в {target_time.strftime('%H:%M:%S')} и далее каждые 30 минут.")

def main():
    # Создаем апдейтера и диспетчера
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # Команды для бота
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('schedule', set_schedule))

    # Обработчик сообщений (если пользователь отвечает на сообщение)
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Запуск бота
    updater.start_polling()

    # Ожидаем остановки бота
    updater.idle()

if __name__ == '__main__':
    main()
