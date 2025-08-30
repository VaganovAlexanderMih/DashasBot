import os
import telebot
import threading
import time
from datetime import datetime, timedelta
from flask import Flask

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

MESSAGE_TEXT = "Выпила таблетки?"
chat_file = "chat_id.txt"
chat_id = None
answered = False

# --- Сохраняем/загружаем chat_id ---
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

threading.Thread(target=run_flask, daemon=True).start()

# --- Сброс флага answered каждый день в 18:30 ---
def reset_answered_flag():
    global answered
    while True:
        now = datetime.now()
        target = now.replace(hour=18, minute=30, second=0, microsecond=0)
        if now > target:
            target += timedelta(days=1)
        time_to_sleep = (target - now).total_seconds()
        time.sleep(time_to_sleep)
        answered = False
        print("Флаг answered сброшен в 18:30")

threading.Thread(target=reset_answered_flag, daemon=True).start()

# --- Отправка сообщений ---
def send_message_job():
    global answered
    while True:
        now = datetime.now()
        # сообщение каждый день в 20:00
        target_time = now.replace(hour=21, minute=30, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)
        time_to_sleep = (target_time - now).total_seconds()
        time.sleep(time_to_sleep)

        # повтор каждые 30 минут до ответа
        while not answered and chat_id:
            bot.send_message(chat_id, MESSAGE_TEXT)
            time.sleep(1800)  # 30 минут

threading.Thread(target=send_message_job, daemon=True).start()

# --- Обработка команд ---
@bot.message_handler(commands=['start'])
def start(message):
    global chat_id
    chat_id = message.chat.id
    save_chat_id(chat_id)
    bot.reply_to(message, f"Бот запущен. chat_id={chat_id}")

@bot.message_handler(commands=['schedule'])
def schedule(message):
    bot.reply_to(message, "Сообщения будут отправляться с 20:00 каждые 30 минут до ответа.")

@bot.message_handler(func=lambda m: True)
def handle_reply(message):
    global answered
    answered = True
    bot.reply_to(message, "Спасибо за ответ! Бот больше не будет слать сообщения сегодня.")

# --- Запуск бота ---
bot.infinity_polling()
