import os
import telebot
from flask import Flask
from datetime import datetime, time as dt_time
import logging
import threading

# --- Логгер ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# --- Конфиг ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

MESSAGE_TEXT = "Выпила таблетки?"
chat_file = "chat_id.txt"
time_file = "send_time.txt"
interval_file = "interval.txt"

chat_id = None
answered = False
send_hour = 19  # по умолчанию 19:00
send_minute = 0
reminder_interval = 30  # минуты по умолчанию

# --- Сохранение/загрузка chat_id ---
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

# --- Сохранение/загрузка времени ---
def save_send_time(h, m):
    with open(time_file, "w") as f:
        f.write(f"{h:02d}:{m:02d}")

def load_send_time():
    try:
        with open(time_file) as f:
            h, m = map(int, f.read().split(":"))
            return h, m
    except:
        return 19, 0

send_hour, send_minute = load_send_time()

# --- Сохранение/загрузка интервала ---
def save_interval(minutes):
    with open(interval_file, "w") as f:
        f.write(str(minutes))

def load_interval():
    try:
        with open(interval_file) as f:
            return int(f.read())
    except:
        return 30

reminder_interval = load_interval()

# --- Flask ---
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "Bot is running with polling!"

@app.route("/send_reminder", methods=["GET"])
def send_reminder():
    """Эндпоинт для вызова из UptimeRobot каждые N минут"""
    global answered
    if chat_id is None:
        logger.info("chat_id не задан, сообщение не отправлено")
        return "No chat_id", 200

    now = datetime.now()
    if now.time() < dt_time(send_hour, send_minute):
        logger.info(f"Ещё не {send_hour:02d}:{send_minute:02d}, сообщение не отправлено")
        return "Too early", 200

    if not answered:
        try:
            bot.send_message(chat_id, MESSAGE_TEXT)
            logger.info(f"Сообщение отправлено пользователю {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
    else:
        logger.info("Пользователь уже ответил, сообщение не отправлено")

    return "OK", 200

# --- Telegram команды ---
@bot.message_handler(commands=['start'])
def start(message):
    global chat_id, answered
    chat_id = message.chat.id
    answered = False
    save_chat_id(chat_id)
    bot.reply_to(message, f"Бот запущен. chat_id={chat_id}")
    logger.info(f"Пользователь {chat_id} запустил бота")

@bot.message_handler(commands=['schedule'])
def schedule(message):
    global send_hour, send_minute
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Использование: /schedule HH:MM")
        return
    try:
        h, m = map(int, parts[1].split(":"))
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError
        send_hour, send_minute = h, m
        save_send_time(h, m)
        bot.reply_to(message, f"Время отправки изменено на {h:02d}:{m:02d}")
        logger.info(f"Новое время рассылки: {h:02d}:{m:02d}")
    except ValueError:
        bot.reply_to(message, "Неверный формат. Используй HH:MM")

@bot.message_handler(commands=['interval'])
def interval(message):
    global reminder_interval
    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Использование: /interval N (в минутах)")
        return
    try:
        minutes = int(parts[1])
        if minutes < 1:
            raise ValueError
        reminder_interval = minutes
        save_interval(minutes)
        bot.reply_to(message, f"Интервал изменен на {minutes} минут")
        logger.info(f"Интервал напоминаний: {minutes} минут")
    except ValueError:
        bot.reply_to(message, "Неверный формат. Используй целое число больше 0")

@bot.message_handler(func=lambda m: True)
def handle_reply(message):
    global answered
    answered = True
    try:
        bot.reply_to(message, "Спасибо за ответ! До завтра 🚀")
        logger.info(f"Пользователь {chat_id} ответил, рассылка приостановлена")
    except Exception as e:
        logger.error(f"Ошибка при ответе: {e}")

# --- Запуск ---
if __name__ == "__main__":
    # Запускаем polling в отдельном потоке
    threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True), daemon=True).start()

    # Flask для UptimeRobot
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Запуск Flask на порту {port}")
    app.run(host="0.0.0.0", port=port)
