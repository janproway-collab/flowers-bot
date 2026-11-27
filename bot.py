import telebot
import os
import sqlite3
import time
import openpyxl
import traceback
import io
import csv
from datetime import datetime
from flask import Flask, request, jsonify, Response
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
c.execute('''CREATE TABLE IF NOT EXISTS approved 
             (chat_id INTEGER PRIMARY KEY, client_type TEXT, client_name TEXT, approval_date TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS products 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT, base_price REAL, rate REAL, pack_size INTEGER, image TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS orders_log 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, order_json TEXT, created_at TEXT)''')
conn.commit()

def is_approved(chat_id):
    c.execute('SELECT 1 FROM approved WHERE chat_id = ?', (chat_id,))
    return c.fetchone() is not None

def get_image_url(name):
    n = name.lower()
    if 'роза' in n or 'rose' in n: return "https://images.unsplash.com/photo-1548586196-aa5803b77379?w=600&auto=format&fit=crop&q=80"
    if 'гвоздика' in n: return "https://images.unsplash.com/photo-1563241527-3004b7be0ffd?w=600&auto=format&fit=crop&q=80"
    if 'хризантема' in n: return "https://images.unsplash.com/photo-1603044344921-975333f79b9c?w=600&auto=format&fit=crop&q=80"
    if 'альстромерия' in n: return "https://images.unsplash.com/photo-1596701645647-82563349329c?w=600&auto=format&fit=crop&q=80"
    if 'гортензия' in n: return "https://images.unsplash.com/photo-1508610048659-a06b669e3321?w=600&auto=format&fit=crop&q=80"
    if 'зелень' in n or 'лист' in n or 'ветви' in n or 'эвкалипт' in n or 'пальма' in n: 
        return "https://images.unsplash.com/photo-1592150621744-aca64f48394a?w=600&auto=format&fit=crop&q=80"
    return "https://images.unsplash.com/photo-1490750967868-88cb3e98425d?w=600&auto=format&fit=crop&q=80"

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(
        message.chat.id, 
        "Добро пожаловать в Flowers Truck! 🌸\n\nНажмите кнопку ниже, чтобы открыть каталог:",
        reply_markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True).add("🌸 Открыть каталог")
    )

@bot.message_handler(commands=['approve'])
def approve_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split(maxsplit=3)
        client_id = int(parts[1])
        client_name = parts[2] if len(parts) > 2 else "Оптовый клиент"
        client_type = parts[3] if len(parts) > 3 else "Юрлицо"
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute('REPLACE INTO approved (chat_id, client_type, client_name, approval_date) VALUES (?, ?, ?, ?)', 
                  (client_id, client_type, client_name, now_str))
        conn.commit()
        
        bot.send_message(ADMIN_ID, f"✅ Клиент {client_name} (ID: {client_id}) успешно добавлен в белый список ({client_type}).")
        bot.send_message(client_id, "🎉 Ваша заявка одобрена! Доступ к оптовым ценам и спецпредложениям открыт. Нажмите /start и откройте каталог.")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}\nФормат: /approve <ID> <Имя> <Тип>")

# --- УМНОЕ ЧТЕНИЕ EXCEL С ГРУППАМИ И РАЗМЕРОМ ПАЧЕК ---
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
            if isinstance(rate_cell, (int, float)) and rate_cell > 0: 
                rate = float(rate_cell)
        except: 
            pass

        current_cat_left = "Разное"
        current_cat_right = "Розы"

        for row in sheet.iter_rows(min_row=2, max_row=300, max_col=9):
            # Левая сторона
            name_left = row[0].value
            price_left = row[2].value
            if name_left:
                name_str = str(name_left).strip()
                if isinstance(price_left, (int, float)):
                    pack = 10 if ('роза' in name_str.lower() or 'гвоздика' in name_str.lower()) else 20
                    products.append((name_str, current_cat_left, float(price_left), rate, pack, get_image_url(name_str)))
                else:
                    current_cat_left = name_str

            # Правая сторона
            name_right = row[5].value
            price_right = row[7].value
            if name_right:
                name_str = str(name_right).strip()
                if isinstance(price_right, (int, float)):
                    pack = 25 if ('роза' in name_str.lower() or 'роза ec' in current_cat_right.lower()) else 10
                    products.append((name_str, current_cat_right, float(price_right), rate, pack, get_image_url(name_str)))
                else:
                    current_cat_right = name_str

        if not products:
            bot.reply_to(message, "⚠️ В файле не обнаружены товары с числовыми ценами. Проверьте колонки C и H.")
            return

        c.execute('DELETE FROM products')
        c.executemany('INSERT INTO products (name, category, base_price, rate, pack_size, image) VALUES (?, ?, ?, ?, ?, ?)', products)
        conn.commit()
        
        bot.reply_to(message, f"✅ Прайс успешно обновлен!\nЗагружено позиций: {len(products)}\nАктуальный курс: {rate}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка чтения Excel: {e}")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    if message.document.file_name.endswith('.xlsx'):
        bot.reply_to(message, "⏳ Обрабатываю прайс-лист, подождите пару секунд...")
        Thread(target=process_excel, args=(message,)).start()
    else:
        bot.reply_to(message, "Пожалуйста, отправьте файл в формате .xlsx")

# --- API СЕРВЕР ---
@app.route('/')
def home(): return "Flowers Truck API is active and healthy."

@app.route('/api/products', methods=['GET'])
def get_products():
    c.execute('SELECT id, name, category, base_price, rate, pack_size, image FROM products')
    rows = c.fetchall()
    return jsonify([{
        "id": r[0], 
        "name": r[1], 
        "category": r[2], 
        "price": round(r[3] * r[4], 2), 
        "pack_price": round(r[3] * r[4] * r[5], 2),
        "pack_size": r[5],
        "image": r[6]
    } for r in rows])

@app.route('/api/check', methods=['POST'])
def check_user():
    data = request.json
    chat_id = data.get('chat_id')
    c.execute('SELECT client_type, client_name FROM approved WHERE chat_id = ?', (chat_id,))
    row = c.fetchone()
    if row:
        return jsonify({"approved": True, "client_type": row[0], "client_name": row[1]})
    return jsonify({"approved": False})

@app.route('/api/request_access', methods=['POST'])
def request_access():
    data = request.json
    chat_id = data.get('chat_id')
    name = data.get('name', 'Без имени')
    username = data.get('username', '')
    client_type = data.get('client_type', 'Оптовик')
    
    now = datetime.now()
    is_work_time = now.weekday() < 5 and 9 <= now.hour < 18
    
    if is_work_time: 
        bot.send_message(chat_id, "📝 Ваша заявка отправлена менеджеру. Ожидайте подтверждения.")
    else: 
        bot.send_message(chat_id, "⏰ Ваша заявка принята. Мы работаем Пн-Пт с 09:00 до 18:00, менеджер свяжется с вами в рабочее время.")
    
    username_link = f"https://t.me/{username}" if username else "нет username"
    msg = f"🔔 **Заявка на доступ к прайсу**\n\n👤 **Имя:** {name}\n🏢 **Тип:** {client_type}\n🔗 **Профиль:** {username_link}\n🆔 **Chat ID:** `{chat_id}`\n\n👉 *Для одобрения нажмите кнопку или отправьте команду:*"
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("✅ Одобрить (Опт)", callback_data=f"app_{chat_id}_Оптовик"))
    markup.add(telebot.types.InlineKeyboardButton("✅ Одобрить (Розница)", callback_data=f"app_{chat_id}_Физлицо"))
    
    bot.send_message(ADMIN_ID, msg, reply_markup=markup, parse_mode='Markdown', disable_web_page_preview=True)
    return jsonify({"status": "ok"})

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_'))
def callback_approve(call):
    parts = call.data.split('_')
    client_id = int(parts[1])
    client_type = parts[2]
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute('REPLACE INTO approved (chat_id, client_type, client_name, approval_date) VALUES (?, ?, ?, ?)', 
              (client_id, client_type, "Клиент из Telegram", now_str))
    conn.commit()
    
    bot.answer_callback_query(call.id, "Клиент одобрен!")
    bot.edit_message_text(f"✅ Доступ одобрен для {client_type} (ID: {client_id}).", call.message.chat.id, call.message.message_id)
    bot.send_message(client_id, "🎉 Ваш доступ к каталогу одобрен! Откройте каталог заново.")

@app.route('/api/order', methods=['POST'])
def receive_order():
    data = request.json
    items = data.get("items", [])
    subtotal = float(data.get("subtotal", 0))
    discount = float(data.get("discount", 0))
    final_total = float(data.get("total", 0))
    chat_id = data.get("chat_id")
    
    text = f"🔥 **НОВЫЙ ЗАКАЗ**\nКлиент: `{chat_id}`\n\n"
    for i in items: 
        text += f"▪️ {i['name']} — {i['qty']} шт. ({i['price']} BYN)\n"
    
    text += f"\nПодытог: {subtotal:.2f} BYN"
    if discount > 0: text += f"\n🎁 Скидка (спецпредложение): -{discount:.2f} BYN"
    text += f"\n💰 **К оплате: {final_total:.2f} BYN**"
        
    bot.send_message(ADMIN_ID, text, parse_mode='Markdown')
    
    order_json = json.dumps(data, ensure_ascii=False)
    c.execute('INSERT INTO orders_log (chat_id, order_json, created_at) VALUES (?, ?, ?)', 
              (chat_id, order_json, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    return jsonify({"status": "ok"})

# Экспорт заказа в CSV для бухгалтерии
@app.route('/api/export_orders', methods=['GET'])
def export_orders():
    c.execute('SELECT id, chat_id, order_json, created_at FROM orders_log ORDER BY id DESC')
    rows = c.fetchall()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Дата', 'Chat_ID', 'Сумма', 'Состав заказа'])
    for r in rows:
        order_data = json.loads(r[2])
        items_str = ", ".join([f"{i['name']} ({i['qty']} шт.)" for i in order_data.get('items', [])])
        writer.writerow([r[3], r[1], order_data.get('total', '0'), items_str])
    
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=orders.csv"})

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    t = Thread(target=run_web_server)
    t.start()
    time.sleep(5)
    bot.infinity_polling()
