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
send_hour = 20
send_minute = 0

# событие для изменения расписания
schedule_changed = threading.Event()


# --- Работа с файлами ---
def save_chat_id(cid):
    with open(chat_file, "w") as f:
        f.write(str(cid))


def load_chat_id():
    try:
        with open(chat_file) as f:
            return int(f.read())
    except:
        return None


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


chat_id = load_chat_id()
send_hour, send_minute = load_send_time()


# --- Flask для Render ---
app_http = Flask("web")


@app_http.route("/")
def index():
    return "Bot is running!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_http.run(host="0.0.0.0", port=port)


threading.Thread(target=run_flask, daemon=True).start()


# --- Вспомогательная функция ---
def compute_next_target(now: datetime):
    target = now.replace(hour=send_hour, minute=send_minute, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


# --- Сброс answered каждый день в 18:30 ---
def reset_answered_flag():
    global answered
    while True:
        now = datetime.now()
        target = now.replace(hour=18, minute=30, second=0, microsecond=0)
        if now > target:
            target += timedelta(days=1)
        time.sleep((target - now).total_seconds())
        answered = False
        print("[reset] Флаг answered сброшен в 18:30")


# --- Основной планировщик ---
def send_message_job():
    global answered
    while True:
        if chat_id is None:
            time.sleep(5)
            continue

        next_run = compute_next_target(datetime.now())
        print(f"[job] Следующая отправка в {next_run.strftime('%H:%M')}")

        # ждем до времени запуска
        while True:
            now = datetime.now()
            remain = (next_run - now).total_seconds()
            if remain <= 0:
                break
            woke = schedule_changed.wait(timeout=min(30, remain))
            if woke:
                schedule_changed.clear()
                next_run = compute_next_target(datetime.now())
                print(f"[job] Расписание изменено, новое время {next_run.strftime('%H:%M')}")

        # цикл повторов каждые 30 мин
        while not answered and chat_id:
            try:
                bot.send_message(chat_id, MESSAGE_TEXT)
                print(f"[job] Сообщение отправлено {datetime.now().strftime('%H:%M')}")
            except Exception as e:
                print(f"[job] Ошибка отправки: {e}")

            # ждем 30 мин по секундам, чтобы можно было прервать ответом
            for _ in range(30 * 60):
                if answered:
                    break
                if schedule_changed.is_set():
                    schedule_changed.clear()
                    break
                time.sleep(1)

            # если изменилось расписание — выходим к внешнему циклу
            if schedule_changed.is_set():
                break


# --- Обработчики команд ---
@bot.message_handler(commands=["start"])
def start(message):
    global chat_id, answered
    answered = False
    chat_id = message.chat.id
    save_chat_id(chat_id)
    bot.reply_to(message, f"Бот запущен. chat_id={chat_id}")

    threading.Thread(target=reset_answered_flag, daemon=True).start()
    threading.Thread(target=send_message_job, daemon=True).start()


@bot.message_handler(commands=["schedule"])
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
        schedule_changed.set()
        bot.reply_to(message, f"Время изменено на {h:02d}:{m:02d}")
    except ValueError:
        bot.reply_to(message, "Неверный формат. Используйте HH:MM.")


@bot.message_handler(commands=["status"])
def status(message):
    bot.reply_to(
        message,
        f"Текущее время отправки: {send_hour:02d}:{send_minute:02d}\n"
        f"answered = {answered}\n"
        f"chat_id = {chat_id}",
    )


@bot.message_handler(func=lambda m: True)
def handle_reply(message):
    global answered
    answered = True
    bot.reply_to(message, "Спасибо за ответ! До завтра 🚀")


# --- Запуск ---
if chat_id:
    print(f"Найден chat_id={chat_id}, запускаем фоновые задачи")
    threading.Thread(target=reset_answered_flag, daemon=True).start()
    threading.Thread(target=send_message_job, daemon=True).start()

bot.infinity_polling()
