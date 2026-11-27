import telebot
import os
import sqlite3
import time
import openpyxl
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread

# ===== ТВОИ ДАННЫЕ =====
TOKEN = '9283859144:AAGe6xwrC5VhXkIssW7I5U7SUoIsv7iUVGM'
ADMIN_ID = 5260033843
# =======================

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
CORS(app)

conn = sqlite3.connect('flowers.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS approved (chat_id INTEGER PRIMARY KEY)''')
c.execute('''CREATE TABLE IF NOT EXISTS products 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT, base_price REAL, rate REAL, image TEXT)''')
conn.commit()

def is_approved(chat_id):
    c.execute('SELECT 1 FROM approved WHERE chat_id = ?', (chat_id,))
    return c.fetchone() is not None

# Надежные ссылки на фото
def get_image_url(name):
    n = name.lower()
    if 'роза' in n or 'rose' in n: return "https://images.unsplash.com/photo-1548586196-aa5803b77379?w=400&q=80"
    if 'гвоздика' in n: return "https://images.unsplash.com/photo-1563241527-3004b7be0ffd?w=400&q=80"
    if 'хризантема' in n: return "https://images.unsplash.com/photo-1603044344921-975333f79b9c?w=400&q=80"
    if 'альстромерия' in n: return "https://images.unsplash.com/photo-1596701645647-82563349329c?w=400&q=80"
    if 'гортензия' in n: return "https://images.unsplash.com/photo-1508610048659-a06b669e3321?w=400&q=80"
    if 'зелень' in n or 'лист' in n or 'ветви' in n: return "https://images.unsplash.com/photo-1592150621744-aca64f48394a?w=400&q=80"
    return "https://images.unsplash.com/photo-1490750967868-88cb3e98425d?w=400&q=80"

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "Добро пожаловать в Flowers Truck! Отправьте Excel-файл (.xlsx) для обновления прайса.")

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

def process_excel(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open('temp.xlsx', 'wb') as new_file:
            new_file.write(downloaded_file)
        
        wb = openpyxl.load_workbook('temp.xlsx', read_only=True, data_only=True)
        sheet = wb.active
        products = []
        rate = 3.07 
        
        try:
            rate_cell = sheet.cell(row=1, column=5).value
            if isinstance(rate_cell, (int, float)): rate = float(rate_cell)
        except: pass

        current_cat_left = "Разное"
        current_cat_right = "Розы (Разное)"

        for row in sheet.iter_rows(min_row=2, max_row=250, max_col=9):
            # Левая сторона
            name_left = row[0].value
            price_left = row[2].value
            if name_left:
                if isinstance(price_left, (int, float)):
                    products.append((str(name_left).strip(), current_cat_left, float(price_left), rate, get_image_url(str(name_left))))
                else:
                    current_cat_left = str(name_left).strip()

            # Правая сторона
            name_right = row[5].value
            price_right = row[7].value
            if name_right:
                if isinstance(price_right, (int, float)):
                    products.append((str(name_right).strip(), current_cat_right, float(price_right), rate, get_image_url(str(name_right))))
                else:
                    current_cat_right = str(name_right).strip()

        if len(products) == 0:
            bot.reply_to(message, "⚠️ Не нашел цены в файле.")
            return

        c.execute('DELETE FROM products')
        c.executemany('INSERT INTO products (name, category, base_price, rate, image) VALUES (?, ?, ?, ?, ?)', products)
        conn.commit()
        bot.reply_to(message, f"✅ Успех! Загружено {len(products)} позиций. Курс: {rate}")
    except Exception as e:
        bot.reply_to(message, f"❌ ОШИБКА: {e}")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    if message.document.file_name.endswith('.xlsx'):
        bot.reply_to(message, "⏳ Читаю Excel-файл...")
        Thread(target=process_excel, args=(message,)).start()
    else:
        bot.reply_to(message, "Отправьте файл .xlsx")

# --- API ---
@app.route('/')
def home(): return "Bot is alive!"

@app.route('/api/products', methods=['GET'])
def get_products():
    c.execute('SELECT id, name, category, base_price, rate, image FROM products')
    rows = c.fetchall()
    return jsonify([{
        "id": r[0], "name": r[1], "category": r[2], 
        "price": round(r[3] * r[4], 2), "image": r[5]
    } for r in rows])

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
    subtotal = float(data.get("subtotal", 0))
    discount = float(data.get("discount", 0))
    final_total = float(data.get("total", 0))
    chat_id = data.get("chat_id")
    
    text = f"🔥 **НОВЫЙ ЗАКАЗ**\nКлиент ID: {chat_id}\n\n"
    for i in items: 
        text += f"▪️ {i['name']} — {i['qty']} шт. ({i['price']} BYN)\n"
    
    text += f"\nСумма: {subtotal} BYN"
    if discount > 0:
        text += f"\n🎁 Скидка (от 3000): -{discount} BYN"
    text += f"\n💰 **Итого к оплате: {final_total} BYN**"
        
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')
    return jsonify({"status": "ok"})

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.start()
    time.sleep(10)
    bot.infinity_polling()
