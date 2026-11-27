import telebot
import os
from flask import Flask, request
from flask_cors import CORS
from threading import Thread

# ===== ТВОИ ДАННЫЕ =====
TOKEN = '9283859144:AAGe6xwrC5VhXkIssW7I5U7SUoIsv7iUVGM'
ADMIN_ID = 5260033843
# =======================

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "Привет! Бот работает. Нажми 'Каталог' и отправь заявку.")

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    print("!!! ПОЛУЧЕНЫ ДАННЫЕ ОТ ТЕЛЕГРАМ:", message.web_app_data.data)
    try:
        bot.send_message(ADMIN_ID, f"🔥 Новая заявка (Телеграм):\nКлиент: {message.from_user.first_name}\nДанные: {message.web_app_data.data}")
    except Exception as e:
        print("ОШИБКА ОТПРАВКИ:", e)
    bot.send_message(message.chat.id, "✅ Заявка принята! Менеджер свяжется с вами.")

app = Flask(__name__)
CORS(app) # <--- ВОТ ЭТО РАЗРЕШАЕТ САЙТУ ОТПРАВЛЯТЬ ДАННЫЕ

@app.route('/')
def home():
    return "Bot is alive!"

@app.route('/debug', methods=['POST', 'OPTIONS']) # Добавили OPTIONS для браузера
def debug():
    if request.method == 'OPTIONS':
        return "OK", 200
    data = request.json
    print("!!! ДАННЫЕ ПРИШЛИ НАПРЯМУЮ С САЙТА:", data)
    try:
        bot.send_message(ADMIN_ID, f"🛠 ТЕСТ (напрямую с сайта):\n{data}")
    except:
        pass
    return "OK", 200

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.start()
    print("Бот запущен и ждет заявок...")
    bot.infinity_polling()
