import telebot
import os
import json
import sqlite3
import time
import csv
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from threading import Thread

# ===== ТВОИ ДАННЫЕ =====
TOKEN = '9283859144:AAGe6xwrC5VhXkIssW7I5U7SUoIsv7iUVGM'
ADMIN_ID = 5260033843
# =======================

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# База данных
conn = sqlite3.connect('flowers.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS approved (chat_id INTEGER PRIMARY KEY)''')
c.execute('''CREATE TABLE IF NOT EXISTS products 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, base_price REAL, rate REAL, image TEXT)''')
conn.commit()

def is_approved(chat_id):
    c.execute('SELECT 1 FROM approved WHERE chat_id = ?', (chat_id,))
    return c.fetchone() is not None

def get_image_url(name):
    n = name.lower()
    if 'роза' in n or 'rose' in n: return "https://source.unsplash.com/400x300/?rose,flower"
    if 'гвоздика' in n: return "https://source.unsplash.com/400x300/?carnation,flower"
    if 'хризантема' in n: return "https://source.unsplash.com/400x300/?chrysanthemum,flower"
    if 'альстромерия' in n: return "https://source.unsplash.com/400x300/?alstroemeria,flower"
    if 'гортензия' in n: return "https://source.unsplash.com/400x300/?hydrangea,flower"
    return "https://source.unsplash.com/400x300/?flower,bouquet"

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "Добро пожаловать! Отправьте мне CSV-файл с прайсом, чтобы обновить каталог.")

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

# --- ЧТЕНИЕ CSV ФАЙЛА ---
def process_csv(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open('temp.csv', 'wb') as new_file:
            new_file.write(downloaded_file)
        
        products = []
        rate = 3.07 # Значение по умолчанию

        with open('temp.csv', 'r', encoding='utf-8-sig') as f:
            reader = list(csv.reader(f))
            
            # Ищем курс в первой строке (5-я колонка, индекс 4)
            if len(reader) > 0 and len(reader[0]) > 4:
                try:
                    rate_val = reader[0][4].replace(',', '.').strip()
                    if rate_val: rate = float(rate_val)
                except: pass
            
            # Проходим по всем строкам, начиная со 2-й (индекс 1)
            for row in reader[1:]:
                if len(row) < 9: continue
                
                # Левая колонка
                name_l = row[0].strip()
                price_l = row[2].replace(',', '.').strip()
                if name_l and price_l:
                    try:
                        products.append((name_l, float(price_l), rate, get_image_url(name_l)))
                    except: pass
                
                # Правая колонка
                name_r = row[5].strip()
                price_r = row[7].replace(',', '.').strip()
                if name_r and price_r:
                    try:
                        products.append((name_r, float(price_r), rate, get_image_url(name_r)))
                    except: pass

        # Очищаем старую базу и вставляем новую
        c.execute('DELETE FROM products')
        c.executemany('INSERT INTO products (name, base_price, rate, image) VALUES (?, ?, ?, ?)', products)
        conn.commit()
        
        bot.reply_to(message, f"✅ Успех! Загружено {len(products)} позиций. Курс: {rate}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ ОШИБКА: {e}")
        print(traceback.format_exc())

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    
    if message.document.file_name.endswith('.csv'):
        bot.reply_to(message, "⏳ Читаю CSV-файл...")
        Thread(target=process_csv, args=(message,)).start()
    else:
        bot.reply_to(message, "Пожалуйста, сохраните файл Excel в формате CSV и отправьте его сюда.")

# --- API ---
@app.route('/')
def home(): return "Bot is alive!"

@app.route('/api/products', methods=['GET'])
def get_products():
    c.execute('SELECT id, name, base_price, rate, image FROM products')
    rows = c.fetchall()
    return jsonify([{"id": r[0], "name": r[1], "price": round(r[2] * r[3], 2), "image": r[4]} for r in rows])

@app.route('/api/check', methods=['POST'])
def check_user():
    data = request.json
    return jsonify({"approved": is_approved(data.get('chat_id'))})

@app.route('/api/request_access', methods=['POST'])
def request_access():
    data = request.json
    chat_id = data.get('chat_id')
    name = data.get('name', 'Клиент')
    
    now = datetime.now()
    is_work_time = now.weekday() < 5 and 9 <= now.hour < 18
    
    if is_work_time: bot.send_message(chat_id, "Заявка отправлена. Ожидайте.")
    else: bot.send_message(chat_id, "Мы работаем Пн-Пт с 09:00 до 18:00. Заявка будет рассмотрена в рабочее время.")
    
    bot.send_message(ADMIN_ID, f"🔔 Запрос!\nИмя: {name}\nID: {chat_id}\n\n/approve {chat_id}")
    return jsonify({"status": "ok"})

@app.route('/api/order', methods=['POST'])
def receive_order():
    data = request.json
    items = data.get("items", [])
    total = data.get("total", "0")
    
    text = f"🔥 Заявка!\nКлиент ID: {data.get('chat_id')}\n\n"
    for i in items: text += f"▪️ {i['name']} — {i['qty']} шт.\n"
    text += f"\n💰 Итого: {total} BYN"
    
    bot.send_message(ADMIN_ID, text)
    return jsonify({"status": "ok"})

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.start()
    time.sleep(10)
    bot.infinity_polling()
