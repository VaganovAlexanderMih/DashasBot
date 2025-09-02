import os
import telebot
from flask import Flask, request
import logging

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
answered_file = "answered.txt"

# --- Flask ---
app = Flask(__name__)

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

# --- Сохранение/загрузка answered ---
def save_answered(flag):
    with open(answered_file, "w") as f:
        f.write("1" if flag else "0")

def load_answered():
    try:
        with open(answered_file) as f:
            return f.read() == "1"
    except:
        return False

answered = load_answered()

# --- Flask routes ---
@app.route("/", methods=["GET"])
def index():
    return "Bot is running!"

@app.route(f"/start", methods=["GET"])
def start_webhook():
    global chat_id, answered
    # Если EasyCron вызовет этот endpoint
    if chat_id is None:
        return "No chat_id set. Send /start to bot first.", 400

    answered = load_answered()
    if not answered:
        try:
            bot.send_message(chat_id, MESSAGE_TEXT)
            logger.info(f"Сообщение отправлено {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            return f"Ошибка: {e}", 500
    else:
        logger.info("Пользователь уже ответил, сообщение не отправлено")
    return "OK", 200

@app.route(f"/answered", methods=["POST"])
def answered_webhook():
    # Этот endpoint можно вызвать через бота после ответа пользователя
    global answered
    answered = True
    save_answered(True)
    return "Answered flag set", 200

# --- Telegram боты ---
@bot.message_handler(commands=['start'])
def start(message):
    global chat_id, answered
    chat_id = message.chat.id
    answered = False
    save_chat_id(chat_id)
    save_answered(False)
    bot.reply_to(message, f"Бот запущен. chat_id={chat_id}\nТеперь EasyCron будет вызывать /start для отправки сообщений")

@bot.message_handler(func=lambda m: True)
def handle_reply(message):
    global answered
    answered = True
    save_answered(True)
    bot.reply_to(message, "Спасибо за ответ! До завтра 🚀")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    bot.remove_webhook()
    bot.set_webhook(url=f"{os.getenv('APP_URL')}/{TOKEN}")  # чтобы получать обновления от Telegram
    app.run(host="0.0.0.0", port=port)
