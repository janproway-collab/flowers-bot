import telebot

# ===== ЗАМЕНИ ЭТИ ДВЕ СТРОКИ =====
TOKEN = '283859144:AAGe6xwrC5VhXkIssW7I5U7SUoIsv7iUVGM'
ADMIN_ID = 5260033843
# =================================

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    order_data = message.web_app_data.data
    
    bot.send_message(
        ADMIN_ID, 
        f"🔥 Новая заявка!\nКлиент: {message.from_user.first_name}\nДанные: {order_data}"
    )
    
    bot.send_message(message.chat.id, "✅ Заявка принята! Менеджер свяжется с вами.")

print("Бот запущен и ждет заявок...")
bot.infinity_polling()