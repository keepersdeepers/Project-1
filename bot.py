import telebot
import sqlite3
from config import TOKEN, ADMIN_ID
from database import init_db, create_deal, get_deals_by_status, update_deal_status
from keyboards import main_menu, buyer_confirm_keyboard, after_payment_keyboard, confirm_receive_keyboard
from database import (
    init_db,
    create_deal,
    get_deals_by_status,
    update_deal_status,
    get_deal_by_id
)

bot = telebot.TeleBot(TOKEN)

init_db()  # создаём базу при запуске

# -----------------------
# Команда /start
# -----------------------
@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, "👋 Привет! Я — Гарант Бот для Telegram Gifts. MakarGarant.\n\n"
                                  "Здесь можно безопасно продавать и покупать подарки 🎁", 
                                  reply_markup=main_menu())
# --
# Обработка кнопки мои сделки
# --                                  
@bot.message_handler(func=lambda message: message.text == "ℹ️ Мои сделки")
def my_deals(message):
    user_id = message.from_user.id

    conn = sqlite3.connect("deals.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, gift_name, price, status
        FROM deals
        WHERE seller_id=? OR buyer_id=?
    """, (user_id, user_id))
    deals = cur.fetchall()
    conn.close()

    if not deals:
        bot.send_message(message.chat.id, "❌ У тебя пока нет активных сделок.", reply_markup=main_menu())
        return

    text = "📦 Твои сделки:\n\n"
    for d in deals:
        deal_id, gift_name, price, status = d
        status_text = {
            "waiting_buyer": "Ожидает покупателя",
            "in_progress": "В процессе",
            "paid": "Оплачено, ждёт подтверждения",
            "completed": "✅ Завершена",
            "dispute": "⚠️ Открыт спор",
            "cancelled": "❌ Отменена"
        }.get(status, status)
        text += f"#{deal_id} — {gift_name} ({price}₽)\nСтатус: {status_text}\n\n"

    bot.send_message(message.chat.id, text, reply_markup=main_menu())                                

# -----------------------
# Создание сделки
# -----------------------
@bot.message_handler(func=lambda m: m.text == "📦 Создать сделку")
def ask_gift_name(msg):
    bot.send_message(msg.chat.id, "🎁 Введи название подарка:")
    bot.register_next_step_handler(msg, ask_price)

def ask_price(msg):
    gift_name = msg.text
    bot.send_message(msg.chat.id, "💰 Укажи цену (например, 500₽):")
    bot.register_next_step_handler(msg, lambda m: save_deal(m, gift_name))

def save_deal(msg, gift_name):
    price = msg.text
    create_deal(msg.chat.id, gift_name, price)
    bot.send_message(msg.chat.id, f"✅ Сделка создана!\nПодарок: {gift_name}\nЦена: {price}\n\n"
                                  "Теперь покупатель может её найти и купить.")

# -----------------------
# Просмотр сделок для покупки
# -----------------------
@bot.message_handler(func=lambda m: m.text == "🛒 Купить подарок")
def show_deals(msg):
    deals = get_deals_by_status("waiting_buyer")
    if not deals:
        bot.send_message(msg.chat.id, "Пока нет активных предложений 😕")
        return
    for deal in deals:
        deal_id, seller_id, gift_name, price = deal
        bot.send_message(msg.chat.id,
                         f"🎁 {gift_name}\n💰 Цена: {price}\n👤 Продавец: [{seller_id}](tg://user?id={seller_id})",
                         parse_mode="Markdown",
                         reply_markup=buyer_confirm_keyboard(deal_id))

# -----------------------
# Inline-кнопки (callback)
# -----------------------
@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def confirm_buy(call):
    deal_id = int(call.data.split("_")[1])
    deal = get_deal_by_id(deal_id)  # нужно добавить такую функцию в database.py
    
    # Проверка: продавец не может быть покупателем
    if call.from_user.id == deal.seller_id:
        bot.answer_callback_query(call.id, "❌ Ты не можешь купить свой же подарок.")
        return
    
    update_deal_status(deal_id, "waiting_payment", call.from_user.id)
    bot.send_message(call.message.chat.id, "💳 Отправь оплату на реквизиты гаранта:\n"
                                           "`@admin_username` или TON-кошелёк.\n\n"
                                           "После оплаты — нажми 'Я оплатил'.", 
                                           parse_mode="Markdown",
                                           reply_markup=after_payment_keyboard(deal_id))
                                           
@bot.callback_query_handler(func=lambda c: c.data.startswith("paid_"))
def mark_paid(call):
    deal_id = int(call.data.split("_")[1])
    update_deal_status(deal_id, "waiting_gift")
    bot.send_message(call.message.chat.id, "✅ Оплата зафиксирована. Ожидаем подарок от продавца.",
                     reply_markup=confirm_receive_keyboard(deal_id))
    bot.send_message(ADMIN_ID, f"⚠️ Сделка #{deal_id} оплачена. Проверь поступление средств.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("received_"))
def mark_received(call):
    deal_id = int(call.data.split("_")[1])
    update_deal_status(deal_id, "completed")
    bot.send_message(call.message.chat.id, "🎉 Сделка завершена! Спасибо за использование гаранта 💎")
    bot.send_message(ADMIN_ID, f"✅ Сделка #{deal_id} успешно завершена.")
    
bot.infinity_polling()
if __name__ == "__main__":
    from database import init_db
    init_db()
    print("База данных готова ✅")
    print("Бот запущен 🚀")
    bot.polling(none_stop=True)
