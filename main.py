import telebot
from telebot import types
import json
import os
from flask import Flask, render_template, request, redirect, url_for
from flask_httpauth import HTTPBasicAuth
import threading

# Настройки
TOKEN = '8055683684:AAEnEi2TVivWyOiIln7lHkQpu3NQubhK_eM'
DATA_FILE = 'users.json'

# Инициализация бота
bot = telebot.TeleBot(TOKEN)


# Загрузка данных пользователей
def load_users():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


# Сохранение данных
def save_users(users):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# Структура пользователя в базе
user_template = {
    "name": "",
    "age": 0,
    "gender": "",
    "bio": "",
    "photo_id": "",
    "likes": [],
    "dislikes": [],
    "state": "MENU"
}

users = load_users()

# Обработчики бота остаются без изменений
# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)

    if user_id not in users:
        users[user_id] = user_template.copy()
        users[user_id]['state'] = 'REG_NAME'
        save_users(users)
        bot.send_message(message.chat.id, "👋 Привет! Давай создадим твой профиль.\nВведи свое имя:")
    else:
        show_main_menu(message.chat.id)


# Обработка текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = str(message.from_user.id)
    user = users.get(user_id)

    if not user:
        return start(message)

    state = user['state']

    if state == 'REG_NAME':
        users[user_id]['name'] = message.text
        users[user_id]['state'] = 'REG_AGE'
        save_users(users)
        bot.send_message(message.chat.id, "📅 Сколько тебе лет?")

    elif state == 'REG_AGE':
        if message.text.isdigit():
            users[user_id]['age'] = int(message.text)
            users[user_id]['state'] = 'REG_GENDER'
            save_users(users)
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("👨 Мужской", "👩 Женский")
            bot.send_message(message.chat.id, "🚻 Выбери пол:", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, "❌ Введи число!")

    elif state == 'REG_GENDER':
        if message.text in ["👨 Мужской", "👩 Женский"]:
            users[user_id]['gender'] = "М" if "👨" in message.text else "Ж"
            users[user_id]['state'] = 'REG_BIO'
            save_users(users)
            bot.send_message(message.chat.id, "📝 Расскажи о себе:", reply_markup=types.ReplyKeyboardRemove())
        else:
            bot.send_message(message.chat.id, "❌ Используй кнопки!")

    elif state == 'REG_BIO':
        users[user_id]['bio'] = message.text
        users[user_id]['state'] = 'REG_PHOTO'
        save_users(users)
        bot.send_message(message.chat.id, "📸 Пришли свое фото:")


# Обработка фото
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = str(message.from_user.id)
    user = users.get(user_id)

    if user and user['state'] == 'REG_PHOTO':
        users[user_id]['photo_id'] = message.photo[-1].file_id
        users[user_id]['state'] = 'MENU'
        save_users(users)
        bot.send_message(message.chat.id, "✅ Регистрация завершена!")
        show_main_menu(message.chat.id)


# Главное меню
def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Искать анкеты")
    bot.send_message(chat_id, "Главное меню:", reply_markup=markup)


# Поиск анкет
def find_profiles(user_id):
    current_user = users[user_id]
    return [
        uid for uid, profile in users.items()
        if (uid != user_id and
            profile['photo_id'] and
            uid not in current_user['likes'] and
            uid not in current_user['dislikes'])
    ]


# Показ анкеты
def show_profile(chat_id, profile_id):
    profile = users[profile_id]
    caption = f"{profile['name']}, {profile['age']}\n\n{profile['bio']}"
    bot.send_photo(
        chat_id,
        profile['photo_id'],
        caption=caption,
        reply_markup=generate_action_buttons()
    )


# Кнопки действий
def generate_action_buttons():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("❤️", callback_data="like"),
        types.InlineKeyboardButton("👎", callback_data="dislike")
    )
    return markup


# Обработка кнопок главного меню
@bot.message_handler(func=lambda m: m.text in ["🔍 Искать анкеты"])
def handle_menu(message):
    user_id = str(message.from_user.id)

    if message.text == "🔍 Искать анкеты":
        candidates = find_profiles(user_id)
        if candidates:
            users[user_id]['current_candidate'] = candidates[0]
            save_users(users)
            show_profile(message.chat.id, candidates[0])
        else:
            bot.send_message(message.chat.id, "😔 Анкет пока нет. Попробуй позже!")


# Обработка inline-кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = str(call.from_user.id)
    current_user = users[user_id]

    if call.data in ["like", "dislike"] and 'current_candidate' in current_user:
        candidate_id = current_user['current_candidate']

        if call.data == "like":
            current_user['likes'].append(candidate_id)
            bot.answer_callback_query(call.id, "❤️ Твой лайк отправлен!")

            # Проверка взаимности
            if user_id in users.get(candidate_id, {}).get('likes', []):
                bot.send_message(
                    call.message.chat.id,
                    f"✨ У вас взаимная симпатия с {users[candidate_id]['name']}! @{users[candidate_id].get('username', '')}"
                )

        else:  # dislike
            current_user['dislikes'].append(candidate_id)
            bot.answer_callback_query(call.id, "👎")

        # Ищем следующего кандидата
        candidates = find_profiles(user_id)
        if candidates:
            users[user_id]['current_candidate'] = candidates[0]
            save_users(users)
            show_profile(call.message.chat.id, candidates[0])
        else:
            bot.send_message(call.message.chat.id, "🔍 Анкеты закончились!")
            save_users(users)


# ... (все обработчики бота из вашего исходного кода)

# Создаем Flask-приложение для админки
app = Flask(__name__)
auth = HTTPBasicAuth()

# Конфигурация админки
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "secure_password_123"


# Проверка авторизации
@auth.verify_password
def verify_password(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


# Роут для главной страницы админки
@app.route('/')
@auth.login_required
def admin_dashboard():
    users_data = load_users()  # Всегда загружаем свежие данные

    stats = {
        'total_users': len(users_data),
        'profiles_with_photo': sum(1 for u in users_data.values() if u['photo_id']),
        'active_profiles': sum(1 for u in users_data.values() if u['state'] == 'MENU'),
    }

    return render_template(
        'admin.html',
        users=users_data,
        stats=stats,
        token=TOKEN,  # Передаем токен в шаблон
        current_user=auth.current_user()  # Передаем текущего пользователя
    )


# Роут для удаления пользователя
@app.route('/delete_user', methods=['POST'])
@auth.login_required
def delete_user():
    user_id = request.form['user_id']
    users_data = load_users()  # Загружаем актуальные данные

    if user_id in users_data:
        del users_data[user_id]
        save_users(users_data)

    return redirect(url_for('admin_dashboard'))


# Запуск Flask в отдельном потоке
def run_admin_panel():
    app.run(port=3000, host='127.0.0.1', debug=False, use_reloader=False)


# Запуск бота и админки
if __name__ == '__main__':
    # Запускаем админ-панель в отдельном потоке
    threading.Thread(target=run_admin_panel, daemon=True).start()

    print("Админ-панель запущена на http://localhost:3000")
    print("Логин: admin, Пароль: secure_password_123")
    print("Бот запущен...")
    bot.infinity_polling()