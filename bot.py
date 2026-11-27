import telebot
import os
from flask import Flask
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
    # Эта строчка выведет данные в логи Render, чтобы мы точно знали, что они дошли
    print("!!! ПОЛУЧЕНЫ ДАННЫЕ ИЗ ПРИЛОЖЕНИЯ:", message.web_app_data.data)
    
    order_data = message.web_app_data.data
    try:
        bot.send_message(
            ADMIN_ID,
            f"🔥 Новая заявка!\nКлиент: {message.from_user.first_name}\nДанные: {order_data}"
        )
    except Exception as e:
        print("ОШИБКА ОТПРАВКИ:", e)

    bot.send_message(message.chat.id, "✅ Заявка принята! Менеджер свяжется с вами.")

# --- Фейковый сайт для Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
# --------------------------------

if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.start()
    print("Бот запущен и ждет заявок...")
    bot.infinity_polling()
