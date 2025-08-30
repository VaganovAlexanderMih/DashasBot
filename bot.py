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
time_file = "send_time.txt"
chat_id = None
answered = False
send_hour = 22
send_minute = 30

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

# --- Сохраняем/загружаем время отправки ---
def save_send_time(h, m):
    with open(time_file, "w") as f:
        f.write(f"{h:02d}:{m:02d}")

def load_send_time():
    try:
        with open(time_file) as f:
            h, m = map(int, f.read().split(":"))
            return h, m
    except:
        return 20, 0  # время по умолчанию

send_hour, send_minute = load_send_time()

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
        time.sleep((target - now).total_seconds())
        answered = False
        print("Флаг answered сброшен в 18:30")

# --- Отправка сообщений ---
def send_message_job():
    global answered
    while True:
        if chat_id is None:
            time.sleep(10)
            continue

        now = datetime.now()
        # динамически формируем цель с учетом текущих send_hour и send_minute
        target_time = now.replace(hour=send_hour, minute=send_minute, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)

        sleep_seconds = (target_time - now).total_seconds()
        while sleep_seconds > 0:
            time.sleep(min(60, sleep_seconds))  # спим максимум минуту, чтобы catch-up обновился
            sleep_seconds -= min(60, sleep_seconds)

        # повтор каждые 30 минут до ответа
        while not answered and chat_id:
            try:
                bot.send_message(chat_id, MESSAGE_TEXT)
            except Exception as e:
                print("Ошибка отправки:", e)
            for _ in range(30*60):  # 30 минут, проверяем каждую секунду
                if answered:
                    break
                time.sleep(1)

# --- Обработка команд ---
@bot.message_handler(commands=['start'])
def start(message):
    global chat_id
    global answered
    answered = False
    chat_id = message.chat.id
    save_chat_id(chat_id)
    bot.reply_to(message, f"Бот запущен. chat_id={chat_id}")

    # Стартуем фоновые потоки только после получения chat_id
    threading.Thread(target=reset_answered_flag, daemon=True).start()
    threading.Thread(target=send_message_job, daemon=True).start()

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
        send_hour = h
        send_minute = m
        save_send_time(send_hour, send_minute)
        bot.reply_to(message, f"Время отправки сообщения изменено на {send_hour:02d}:{send_minute:02d}")
    except ValueError:
        bot.reply_to(message, "Неверный формат времени. Используйте HH:MM в 24-часовом формате.")

@bot.message_handler(func=lambda m: True)
def handle_reply(message):
    global answered
    answered = True
    bot.reply_to(message, "Спасибо за ответ! Бот больше не будет слать сообщения сегодня.")

# --- Запуск бота ---
bot.infinity_polling()
