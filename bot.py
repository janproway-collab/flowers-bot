import telebot
import os
import json
import sqlite3
import time
import openpyxl
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

# --- ПАРСЕР В ОТДЕЛЬНОМ ПОТОКЕ ---
def process_excel(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open('temp.xlsx', 'wb') as new_file:
            new_file.write(downloaded_file)
        
        wb = openpyxl.load_workbook('temp.xlsx', read_only=True, data_only=True)
        sheet = wb.active
        
        rate = sheet.cell(row=1, column=5).value
        if not isinstance(rate, (int, float)): rate = 3.07
        rate = float(rate)

        products = []
        for row in sheet.iter_rows(min_row=2, max_col=9):
            name_left = row[0].value
            price_left = row[2].value
            if name_left and isinstance(price_left, (int, float)):
                products.append((str(name_left).strip(), float(price_left), rate, get_image_url(str(name_left))))

            name_right = row[5].value
            price_right = row[7].value
            if name_right and isinstance(price_right, (int, float)):
                products.append((str(name_right).strip(), float(price_right), rate, get_image_url(str(name_right))))

        c.execute('DELETE FROM products')
        c.executemany('INSERT INTO products (name, base_price, rate, image) VALUES (?, ?, ?, ?)', products)
        conn.commit()
        
        bot.reply_to(message, f"✅ Успех! Загружено {len(products)} позиций. Курс: {rate}")
        
    except Exception as e:
        # Если произойдет ошибка, бот напишет её тебе
        bot.reply_to(message, f"❌ ОШИБКА ПРИ ЧТЕНИИ: {e}")
        print(traceback.format_exc())

@bot.message_handler(content_types=['document'])
def handle_excel(message):
    if message.from_user.id != ADMIN_ID: return
    if not message.document.file_name.endswith(('.xls', '.xlsx')):
        return bot.reply_to(message, "Пожалуйста, отправьте файл Excel (.xlsx)")
    
    bot.reply_to(message, "⏳ Начинаю чтение файла в фоне. Подождите...")
    # Запускаем парсинг в отдельном потоке, чтобы бот не завис
    Thread(target=process_excel, args=(message,)).start()

@app.route('/')
def home():
    return "Bot is alive!"

@app.route('/api/products', methods=['GET'])
def get_products():
    c.execute('SELECT id, name, base_price, rate, image FROM products')
    rows = c.fetchall()
    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "name": r[1],
            "price": round(r[2] * r[3], 2),
            "image": r[4]
        })
    return jsonify(result)

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
    
    if is_work_time:
        bot.send_message(chat_id, "Заявка отправлена. Ожидайте.")
    else:
        bot.send_message(chat_id, "Мы работаем Пн-Пт с 09:00 до 18:00. Заявка будет рассмотрена в рабочее время.")
    
    bot.send_message(ADMIN_ID, f"🔔 Запрос!\nИмя: {name}\nID: {chat_id}\n\n/approve {chat_id}")
    return jsonify({"status": "ok"})

@app.route('/api/order', methods=['POST'])
def receive_order():
    data = request.json
    items = data.get("items", [])
    total = data.get("total", "0")
    
    text = f"🔥 Заявка!\nКлиент ID: {data.get('chat_id')}\n\n"
    for i in items:
        text += f"▪️ {i['name']} — {i['qty']} шт.\n"
    text += f"\n💰 Итого: {total} BYN"
    
    bot.send_message(ADMIN_ID, text)
    return jsonify({"status": "ok"})

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.start()
    
    print("Ждем 10 секунд...")
    time.sleep(10)
    
    print("Бот запущен...")
    bot.infinity_polling()
