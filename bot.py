import telebot
import os
from flask import Flask, request
from threading import Thread

TOKEN = '9283859144:AAGe6xwrC5VhXkIssW7I5U7SUoIsv7iUVGM'
ADMIN_ID = 5260033843

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "Бот работает. Нажми 'Каталог'.")

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

# Этот маршрут принимает данные от сайта
@app.route('/debug', methods=['POST'])
def debug():
    try:
        data = request.get_data(as_text=True)
        print("!!! ПРИШЛИ ДАННЫЕ:", data)
        bot.send_message(ADMIN_ID, f"🔥 Новая заявка (прямая):\n{data}")
        return "OK", 200
    except Exception as e:
        print("ОШИБКА:", e)
        return "Error", 500

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.start()
    print("Бот запущен...")
    bot.infinity_polling()
