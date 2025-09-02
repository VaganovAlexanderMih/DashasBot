import os
import telebot
import threading
import time
import logging
from datetime import datetime, timedelta
from flask import Flask

# --- Настройка логов ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Бот ---
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
    logger.info(f"chat_id сохранён: {cid}")


def load_chat_id():
    try:
        with open(chat_file) as f:
            cid = int(f.read())
            logger.info(f"Загружен chat_id: {cid}")
            return cid
    except Exception:
        return None


def save_send_time(h, m):
    with open(time_file, "w") as f:
        f.write(f"{h:02d}:{m:02d}")
    logger.info(f"Время отправки сохранено: {h:02d}:{m:02d}")


def load_send_time():
    try:
        with open(time_file) as f:
            h, m = map(int, f.read().split(":"))
            logger.info(f"Загружено время отправки: {h:02d}:{m:02d}")
            return h, m
    except Exception:
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
    logger.info(f"Запуск Flask на порту {port}")
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
        logger.info("Флаг answered сброшен в 18:30")


# --- Основной планировщик ---
def send_message_job():
    global answered
    while True:
        if chat_id is None:
            time.sleep(5)
            continue

        next_run = compute_next_target(datetime.now())
        logger.info(f"Следующая отправка в {next_run.strftime('%H:%M')}")

        # ждем до времени запуска
        while True:
            now = datetime.now()
            remain = (next_run - now).total_seconds()
            if remain <= 0:
                break
            woke = schedule_changed.wait(timeout=min(3, remain))
            if woke:
                schedule_changed.clear()
                next_run = compute_next_target(datetime.now())
                logger.info(f"Расписание изменено, новое время {next_run.strftime('%H:%M')}")

        # цикл повторов каждые 30 мин
        while not answered and chat_id:
            try:
                bot.send_message(chat_id, MESSAGE_TEXT)
                logger.info(f"Сообщение отправлено {datetime.now().strftime('%H:%M')}")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")

            # ждем 30 мин по секундам
            for _ in range(3 * 60):
                if answered:
                    logger.info("Получен ответ от пользователя, цикл остановлен")
                    break
                if schedule_changed.is_set():
                    logger.info("Расписание изменено во время ожидания, выходим из цикла")
                    schedule_changed.clear()
                    break
                time.sleep(1)

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
    logger.info(f"/start вызван. chat_id={chat_id}")

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
        logger.info(f"/schedule: время изменено на {h:02d}:{m:02d}")
    except ValueError:
        bot.reply_to(message, "Неверный формат. Используйте HH:MM.")
        logger.warning("Ошибка формата в /schedule")


@bot.message_handler(commands=["status"])
def status(message):
    msg = (
        f"Текущее время отправки: {send_hour:02d}:{send_minute:02d}\n"
        f"answered = {answered}\n"
        f"chat_id = {chat_id}"
    )
    bot.reply_to(message, msg)
    logger.info("/status вызван")


@bot.message_handler(func=lambda m: True)
def handle_reply(message):
    global answered
    answered = True
    bot.reply_to(message, "Спасибо за ответ! До завтра 🚀")
    logger.info(f"Ответ получен: '{message.text}'")


# --- Запуск ---
if chat_id:
    logger.info(f"Найден chat_id={chat_id}, запускаем фоновые задачи")
    threading.Thread(target=reset_answered_flag, daemon=True).start()
    threading.Thread(target=send_message_job, daemon=True).start()

logger.info("Бот запущен, начинаем polling...")
bot.infinity_polling()
