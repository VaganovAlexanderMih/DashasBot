import os
import telebot
from flask import Flask, request
import threading
import time
import logging
from datetime import datetime, timedelta

# --- Логгер ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
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
send_hour = 20
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
        return 20, 0

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
    return "Bot is running with webhook!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_data().decode("utf-8")
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "OK", 200

# --- Логика бота ---
def reset_answered_flag():
    global answered
    while True:
        now = datetime.now()
        target = now.replace(hour=18, minute=30, second=0, microsecond=0)
        if now > target:
            target += timedelta(days=1)
        time.sleep((target - now).total_seconds())
        answered = False
        logger.info("Флаг answered сброшен в 18:30")

def send_message_job():
    global answered
    while True:
        if chat_id is None:
            time.sleep(10)
            continue

        now = datetime.now()
        target_time = now.replace(hour=send_hour, minute=send_minute, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)

        sleep_seconds = (target_time - now).total_seconds()
        logger.info(f"Ожидание до следующего сообщения: {sleep_seconds/60:.1f} минут")
        time.sleep(sleep_seconds)

        # повтор с заданным интервалом
        while not answered and chat_id:
            try:
                bot.send_message(chat_id, MESSAGE_TEXT)
                logger.info(f"Сообщение отправлено {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
            for _ in range(reminder_interval * 60):
                if answered:
                    break
                time.sleep(1)

@bot.message_handler(commands=['start'])
def start(message):
    global chat_id, answered
    chat_id = message.chat.id
    answered = False
    save_chat_id(chat_id)
    bot.reply_to(message, f"Бот запущен. chat_id={chat_id}")

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
        bot.reply_to(message, f"Время изменено на {h:02d}:{m:02d}")
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
    except Exception as e:
        logger.error(f"Ошибка при ответе: {e}")

# --- Установка webhook ---
def set_webhook():
    webhook_url = f"{APP_URL}/{TOKEN}"
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook установлен: {webhook_url}")

if __name__ == "__main__":
    set_webhook()

    logger.info(f"Запуск бота. Загружен chat_id={chat_id}, время {send_hour:02d}:{send_minute:02d}, интервал {reminder_interval} мин")

    # --- Запускаем фоновые потоки ---
    threading.Thread(target=reset_answered_flag, daemon=True).start()
    threading.Thread(target=send_message_job, daemon=True).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
