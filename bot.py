import telebot
import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
from threading import Thread

# ===== ТВОИ ДАННЫЕ =====
TOKEN = '9283859144:AAGe6xwrC5VhXkIssW7I5U7SUoIsv7iUVGM'
ADMIN_ID = 5260033843
# =======================

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# База данных для одобренных клиентов
conn = sqlite3.connect('clients.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS approved (chat_id INTEGER PRIMARY KEY)''')
conn.commit()

def is_approved(chat_id):
    c.execute('SELECT 1 FROM approved WHERE chat_id = ?', (chat_id,))
    return c.fetchone() is not None

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "Добро пожаловать в Flowers Truck! Нажми 'Каталог', чтобы открыть прайс.")

@bot.message_handler(commands=['approve'])
def approve_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        client_id = int(message.text.split()[1])
        c.execute('INSERT OR IGNORE INTO approved (chat_id) VALUES (?)', (client_id,))
        conn.commit()
        bot.send_message(ADMIN_ID, f"✅ Клиент {client_id} одобрен.")
        bot.send_message(client_id, "🎉 Ваш доступ одобрен! Перезайдите в каталог.")
    except:
        bot.send_message(ADMIN_ID, "Ошибка. Используй: /approve 123456789")

@app.route('/')
def home():
    return "Bot is alive!"

# Отдаем товары с пересчитанными ценами!
@app.route('/api/products', methods=['GET'])
def get_products():
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        rate = data.get('rate', 3.07)
        items = data.get('items', [])
        
        # Пересчитываем цену для каждого товара
        for item in items:
            item['price'] = round(item['base_price'] * rate, 2)
            del item['base_price'] # Удаляем базовую, чтобы не путать
            
        return jsonify(items), 200
    except Exception as e:
        return str(e), 500

@app.route('/api/check', methods=['POST'])
def check_user():
    data = request.json
    chat_id = data.get('chat_id')
    if not chat_id: return jsonify({"status": "error"})
    return jsonify({"approved": is_approved(chat_id)})

@app.route('/api/request_access', methods=['POST'])
def request_access():
    data = request.json
    chat_id = data.get('chat_id')
    name = data.get('name', 'Клиент')
    username = data.get('username', '')
    
    # Проверка времени
    now = datetime.now()
    is_work_time = now.weekday() < 5 and 9 <= now.hour < 18
    
    if is_work_time:
        bot.send_message(chat_id, "Ваша заявка отправлена менеджеру. Ожидайте ответа.")
    else:
        bot.send_message(chat_id, "Мы работаем Пн-Пт с 09:00 до 18:00. Ваша заявка будет рассмотрена в рабочее время.")
    
    text = f"🔔 Запрос на доступ!\nКлиент: {name}\nID: {chat_id}\nЮзернейм: @{username}\n\nЧтобы одобрить, напиши команду:\n/approve {chat_id}"
    bot.send_message(ADMIN_ID, text)
    return jsonify({"status": "ok"})

@app.route('/api/order', methods=['POST'])
def receive_order():
    data = request.json
    items = data.get("items", [])
    total = data.get("total", "0")
    chat_id = data.get("chat_id")
    
    order_text = f"🔥 Новая заявка!\nКлиент ID: {chat_id}\n\n"
    for i in items:
        order_text += f"▪️ {i['name']} — {i['qty']} шт.\n"
    order_text += f"\n💰 Итого: {total} BYN"
    
    bot.send_message(ADMIN_ID, order_text)
    return jsonify({"status": "ok"})

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.start()
    bot.infinity_polling()
