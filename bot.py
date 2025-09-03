import os
import telebot
from flask import Flask, request
from datetime import datetime, time as dt_time
import logging
from telebot.types import Update

# --- Логгер ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# --- Конфиг ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # например: https://mybot.onrender.com
bot = telebot.TeleBot(TOKEN)

MESSAGE_TEXT = "Выпила таблетки?"
chat_file = "chat_id.txt"
time_file = "send_time.txt"
interval_file = "interval.txt"

chat_id = None
answered = False
send_hour = 19
send_minute = 0
reminder_interval = 30

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

# --- Сохранение/загрузки интервала ---
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
    return "Bot is running with webhook!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update_dict = request.get_json(force=True)
        logger.info(f"Update from Telegram: {update_dict}")
        message = update_dict['message']
        text = message['text']
        if text == '/start':
            start(message)
        else:
            handle_reply(message)
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка webhook: {e}")
        return "Error", 500


@app.route("/send_reminder", methods=["GET"])
def send_reminder():
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

@app.route("/reset_answered", methods=["GET"])
def reset_answered():
    global answered
    answered = False
    logger.info("Флаг answered сброшен")
    return "answered reset", 200

# --- Telegram команды ---
def start(message):
    global chat_id, answered
    chat_id = message.chat.id
    answered = False
    save_chat_id(chat_id)
    try:
        bot.send_message(chat_id, f"Бот запущен. chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Ошибка reply_to: {e}")
    logger.info(f"Пользователь {chat_id} запустил бота")

def handle_reply(message):
    global answered
    answered = True
    if (chat_id is None):
        return
    try:
        bot.send_message(chat_id, "Спасибо за ответ! До завтра 🚀")
        logger.info(f"Пользователь {chat_id} ответил, рассылка приостановлена")
    except Exception as e:
        logger.error(f"Ошибка при ответе: {e}")

# --- Установка webhook ---
def set_webhook():
    webhook_url = f"{APP_URL}/{TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook установлен: {webhook_url}")

# --- Только для продакшена через gunicorn ---
set_webhook()
logger.info("Приложение готово к запуску через gunicorn")
