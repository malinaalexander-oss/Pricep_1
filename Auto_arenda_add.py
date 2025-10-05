# bot_rent_vacant_vertical.py
import json
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================== НАСТРОЙКИ ==================
TOKEN = "8151509290:AAHSTotV96q22XF9RuRL_zSWvNMJlkTbBHA"  # <-- Вставьте ваш токен
OWNER_ID = 3437915
DATA_FILE = "data.json"

# ================== ХРАНЕНИЕ ДАННЫХ ==================
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"categories": {}, "bookings": []}

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

data = load_data()

# ================== ПРИЦЕПЫ ==================
if not data["categories"]:
    data["categories"] = {
        "для дачи": [
            {"id": 101, "name": "X123XX178", "location": "Пр. Науки 25"},
            {"id": 102, "name": "A456AA178", "location": "Пр. Науки 25"},
            {"id": 103, "name": "B789BB178", "location": "Пр. Науки 25"}
        ],
        "открытый": [
            {"id": 201, "name": "C234CC178", "location": "Пр. Науки 25"},
            {"id": 202, "name": "D567DD178", "location": "Пр. Науки 25"},
            {"id": 203, "name": "E890EE178", "location": "Пр. Науки 25"}
        ],
        "закрытый": [
            {"id": 301, "name": "F321FF178", "location": "Пр. Науки 25"},
            {"id": 302, "name": "G654GG178", "location": "Пр. Науки 25"},
            {"id": 303, "name": "H987HH178", "location": "Пр. Науки 25"}
        ],
        "эндуро": [
            {"id": 401, "name": "I135II178", "location": "Уманский пер. 77"},
            {"id": 402, "name": "J246JJ178", "location": "Уманский пер. 77"},
            {"id": 403, "name": "K357KK178", "location": "Уманский пер. 77"}
        ]
    }
    save_data(data)

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
def iso_to_dt(s): return datetime.fromisoformat(s)
def overlaps(a_start, a_end, b_start, b_end): return a_start < b_end and b_start < a_end

def is_available(trailer_id: int, desired_start: datetime, desired_end: datetime) -> bool:
    for b in data["bookings"]:
        if b["trailer_id"] != trailer_id or b.get("status") in ["finished", "cancelled"]:
            continue
        if overlaps(iso_to_dt(b["start_time"]), iso_to_dt(b["end_time"]), desired_start, desired_end):
            return False
    return True

def get_main_button(user_id: int):
    active = next((b for b in data["bookings"]
                   if b["user_id"] == user_id and b["status"] == "active" and b.get("taken")), None)
    kb = InlineKeyboardBuilder()
    if active:
        kb.row(types.InlineKeyboardButton(text="🚛 Сдать прицеп", callback_data="return_trailer"))
    else:
        kb.row(types.InlineKeyboardButton(text="📝 Оформить аренду", callback_data="start_rent"))
    if user_id == OWNER_ID:
        kb.row(types.InlineKeyboardButton(text="⚙ Настройки", callback_data="owner_settings"))
    return kb.as_markup()

user_state = {}

# ================== ИНИЦИАЛИЗАЦИЯ БОТА ==================
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================== КОМАНДЫ ==================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=get_main_button(message.from_user.id))

# ================== ОБРАБОТКА КНОПОК ==================
@dp.callback_query(lambda c: c.data == "start_rent")
async def start_rent(callback: types.CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    for cat in data["categories"]:
        kb.row(types.InlineKeyboardButton(text=cat.capitalize(), callback_data=f"cat_{cat}"))
    await callback.message.edit_text("Выберите категорию прицепа:", reply_markup=kb.as_markup())

# ========== Выбор категории и даты ========== 
@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def choose_category(callback: types.CallbackQuery):
    await callback.answer()
    cat = callback.data.split("_",1)[1]
    uid = callback.from_user.id
    user_state[uid] = {"step":"choose_start","category":cat}

    kb = InlineKeyboardBuilder()
    months = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]
    for i in range(7):  # только 7 дней вперед
        date = datetime.now() + timedelta(days=i)
        kb.row(types.InlineKeyboardButton(
            text=f"{date.day} {months[date.month-1]}", callback_data=f"start_{i}"))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="start_rent"))

    await callback.message.edit_text("Выберите день начала аренды:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("start_"))
async def choose_start(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    start_delay = int(callback.data.split("_",1)[1])
    user_state[uid]["start_delay"] = start_delay

    kb = InlineKeyboardBuilder()
    for d in range(1,8):
        kb.row(types.InlineKeyboardButton(text=f"{d} дн", callback_data=f"dur_{d}"))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"cat_{user_state[uid]['category']}"))

    await callback.message.edit_text("Выберите длительность аренды (дни):", reply_markup=kb.as_markup())
    user_state[uid]["step"]="choose_duration"

@dp.callback_query(lambda c: c.data.startswith("dur_"))
async def choose_duration(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    duration = int(callback.data.split("_",1)[1])
    start = datetime.now() + timedelta(days=user_state[uid]["start_delay"])
    end = start + timedelta(days=duration)
    user_state[uid].update({"duration":duration, "start":start.isoformat(), "end":end.isoformat()})

    category = user_state[uid]["category"]
    available_trailers = [t for t in data["categories"][category] if is_available(t["id"], start, end)]

    if not available_trailers:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text="🔄 Начать заново", callback_data="start_rent"))
        await callback.message.edit_text(
            "❌ Все прицепы заняты на выбранные даты. Попробуйте другой период.",
            reply_markup=kb.as_markup()
        )
        user_state.pop(uid)
        return

    # Формируем текст с адресами и номерами
    text = "Выберите прицеп:\n\n"
    kb = InlineKeyboardBuilder()
    for t in available_trailers:
        text += f"Прицеп: {t['name']}\nАдрес: {t['location']}\n\n"  # номер и адрес текстом
        kb.row(types.InlineKeyboardButton(text=f"Выбрать {t['name']}", callback_data=f"trailer_{t['id']}"))

    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"start_{user_state[uid]['start_delay']}"))

    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    user_state[uid]["step"]="choose_trailer"


@dp.callback_query(lambda c: c.data.startswith("trailer_"))
async def confirm_booking(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    trailer_id = int(callback.data.split("_",1)[1])
    start = iso_to_dt(user_state[uid]["start"])
    end = iso_to_dt(user_state[uid]["end"])

    trailer = next(t for t in sum(data["categories"].values(), []) if t["id"]==trailer_id)

    booking = {
        "user_id": uid,
        "username": callback.from_user.username,
        "trailer_id": trailer_id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "status": "active",
        "taken": False,
        "created_at": datetime.now().isoformat()
    }
    data["bookings"].append(booking)
    save_data(data)
    user_state.pop(uid)

    await bot.send_message(OWNER_ID,
        f"🔔 Новая бронь!\n@{callback.from_user.username or uid}\nПрицеп {trailer['name']}, {trailer['location']}\n"
        f"{start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}")

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🚛 Забрать прицеп", callback_data="take_trailer"))
    await callback.message.edit_text(
        f"✅ Бронь успешна!\nПрицеп: {trailer['name']}\nАдрес: {trailer['location']}\n"
        f"Период аренды: {start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}",
        reply_markup=kb.as_markup()
    )

# ================== ЗАБРАТЬ ПРИЦЕП ==================
@dp.callback_query(lambda c: c.data=="take_trailer")
async def take_trailer(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    booking = next((b for b in data["bookings"] if b["user_id"]==uid and b["status"]=="active" and not b.get("taken")), None)
    if not booking:
        await callback.message.answer("❌ Нет броней на сегодня для забора.")
        return
    user_state[uid] = {"step":"await_photo_take","booking":booking}
    await callback.message.answer("📸 Пришлите фото прицепа при получении.")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]["step"]=="await_photo_take")
async def photo_take(message: types.Message):
    if not message.photo:
        await message.answer("❌ Это не фото, отправьте изображение прицепа.")
        return
    uid = message.from_user.id
    file_id = message.photo[-1].file_id
    booking = user_state[uid]["booking"]
    booking["taken"] = True
    save_data(data)
    await bot.send_photo(OWNER_ID, photo=file_id, caption=f"📸 Прицеп забран @{message.from_user.username or uid}")
    user_state.pop(uid)
    await message.answer("✅ Фото отправлено владельцу. Кнопка 'Сдать прицеп' появится в вашем меню.", reply_markup=get_main_button(uid))

# ================== СДАТЬ ПРИЦЕП ==================
@dp.callback_query(lambda c: c.data=="return_trailer")
async def return_trailer(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    booking = next((b for b in data["bookings"] if b["user_id"]==uid and b["status"]=="active" and b.get("taken")), None)
    if not booking:
        await callback.message.answer("❌ Нет активной аренды.")
        return
    user_state[uid] = {"step":"await_photo_return","booking":booking}
    await callback.message.answer("📸 Пришлите фото прицепа при возврате.")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]["step"]=="await_photo_return")
async def photo_return(message: types.Message):
    if not message.photo:
        await message.answer("❌ Отправьте фото прицепа.")
        return
    uid = message.from_user.id
    user_state[uid]["photo_trailer"] = message.photo[-1].file_id
    user_state[uid]["step"]="await_photo_check"
    await message.answer("📄 Отправьте фото чека об оплате.")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]["step"]=="await_photo_check")
async def photo_check(message: types.Message):
    if not message.photo:
        await message.answer("❌ Отправьте фото чека.")
        return
    uid = message.from_user.id
    booking = user_state[uid]["booking"]
    booking["status"]="finished"
    booking["photo_return"] = user_state[uid]["photo_trailer"]
    booking["photo_check"] = message.photo[-1].file_id
    save_data(data)
    await bot.send_photo(OWNER_ID, photo=user_state[uid]["photo_trailer"], caption=f"📸 Прицеп возвращен @{message.from_user.username or uid}")
    await bot.send_photo(OWNER_ID, photo=message.photo[-1].file_id, caption=f"📄 Чек @{message.from_user.username or uid}")
    user_state.pop(uid)
    await message.answer("✅ Возврат завершён.", reply_markup=get_main_button(uid))

# ================== НАСТРОЙКИ ВЛАДЕЛЬЦА ==================
@dp.callback_query(lambda c: c.data=="owner_settings")
async def owner_settings(callback: types.CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="📊 Получить статистику", callback_data="show_stats"))
    kb.row(types.InlineKeyboardButton(text="🗑 Сбросить аренду", callback_data="reset_booking"))
    kb.row(types.InlineKeyboardButton(text="🛠 Управление прицепами", callback_data="manage_trailers"))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"))
    await callback.message.edit_text("Настройки владельца:", reply_markup=kb.as_markup())

# ================== УПРАВЛЕНИЕ ПРИЦЕПАМИ (главное меню) ==================
@dp.callback_query(lambda c: c.data=="manage_trailers")
async def manage_trailers(callback: types.CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="➕ Добавить прицеп", callback_data="add_trailer"))
    kb.row(types.InlineKeyboardButton(text="❌ Удалить прицеп", callback_data="delete_trailer"))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="owner_settings"))
    await callback.message.edit_text("Управление прицепами:", reply_markup=kb.as_markup())

# ================== СТАТИСТИКА ==================
@dp.callback_query(lambda c: c.data=="show_stats")
async def show_stats(callback: types.CallbackQuery):
    await callback.answer()
    now = datetime.now()
    active_bookings = [b for b in data["bookings"] if b["status"]=="active" and iso_to_dt(b["start_time"]) <= now <= iso_to_dt(b["end_time"])]
    future_bookings = [b for b in data["bookings"] if b["status"]=="active" and iso_to_dt(b["start_time"]) > now]

    text = "📊 Статистика:\n\nАктивные аренды:\n"
    if active_bookings:
        for b in active_bookings:
            text += f"Прицеп {b['trailer_id']}: {iso_to_dt(b['start_time']).strftime('%d.%m')} – {iso_to_dt(b['end_time']).strftime('%d.%m')} @{b['username'] or b['user_id']}\n"
    else:
        text += "Нет активных аренд\n"
    text += "\nБудущие брони:\n"
    if future_bookings:
        for b in future_bookings:
            text += f"Прицеп {b['trailer_id']}: {iso_to_dt(b['start_time']).strftime('%d.%m')} – {iso_to_dt(b['end_time']).strftime('%d.%m')} @{b['username'] or b['user_id']}\n"
    else:
        text += "Нет будущих броней\n"

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="owner_settings"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())

# ================== СБРОС АРЕНД ==================
@dp.callback_query(lambda c: c.data=="reset_booking")
async def reset_booking(callback: types.CallbackQuery):
    await callback.answer()
    now = datetime.now()
    bookings_list = [b for b in data["bookings"] if b["status"]=="active" and iso_to_dt(b["end_time"]) >= now]
    if not bookings_list:
        await callback.message.edit_text("Нет активных или будущих аренд для сброса.", reply_markup=get_main_button(OWNER_ID))
        return
    kb = InlineKeyboardBuilder()
    for b in bookings_list:
        kb.row(types.InlineKeyboardButton(
            text=f"{b['trailer_id']} | {iso_to_dt(b['start_time']).strftime('%d.%m')} – {iso_to_dt(b['end_time']).strftime('%d.%m')} @{b['username'] or b['user_id']}",
            callback_data=f"reset_{b['trailer_id']}_{b['user_id']}_{b['start_time']}"
        ))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="owner_settings"))
    await callback.message.edit_text("Выберите аренду для сброса:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("reset_"))
async def do_reset(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_",3)
    trailer_id, user_id, start_time = int(parts[1]), int(parts[2]), parts[3]
    booking = next((b for b in data["bookings"] if b["trailer_id"]==trailer_id and b["user_id"]==user_id and b["start_time"]==start_time), None)
    if booking:
        booking["status"]="cancelled"
        save_data(data)
        await callback.message.answer(f"✅ Бронь прицепа {trailer_id} отменена.")
    await reset_booking(callback)

# ================== УПРАВЛЕНИЕ ПРИЦЕПАМИ ==================
@dp.callback_query(lambda c: c.data=="add_trailer")
async def add_trailer_start(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    user_state[uid] = {"step":"add_trailer_category"}
    
    kb = InlineKeyboardBuilder()
    for cat in data["categories"]:
        kb.row(types.InlineKeyboardButton(text=cat.capitalize(), callback_data=f"newcat_{cat}"))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="manage_trailers"))
    
    await callback.message.edit_text("Выберите категорию нового прицепа:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("newcat_"))
async def add_trailer_category(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    cat = callback.data.split("_",1)[1]
    user_state[uid].update({"category":cat, "step":"add_trailer_number"})
    await callback.message.edit_text("Введите номер нового прицепа (например: Х123ХХ178):")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]["step"]=="add_trailer_number")
async def add_trailer_number(message: types.Message):
    uid = message.from_user.id
    user_state[uid]["number"] = message.text.strip()
    user_state[uid]["step"] = "add_trailer_location"
    await message.answer("Введите адрес хранения прицепа:")

@dp.message(lambda m: m.from_user.id in user_state and user_state[m.from_user.id]["step"]=="add_trailer_location")
async def add_trailer_location(message: types.Message):
    uid = message.from_user.id
    category = user_state[uid]["category"]
    number = user_state[uid]["number"]
    location = message.text.strip()
    


    # Создаём новый прицеп с уникальным id
    existing_ids = [t["id"] for t in data["categories"][category]]
    new_id = max(existing_ids, default=100) + 1
    
    data["categories"][category].append({"id":new_id, "name":number, "location":location})
    save_data(data)
    user_state.pop(uid)
    
    await message.answer(f"✅ Прицеп {number} ({location}) добавлен в категорию '{category}'", reply_markup=get_main_button(OWNER_ID))

@dp.callback_query(lambda c: c.data=="delete_trailer")
async def delete_trailer_start(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    user_state[uid] = {"step":"delete_select_category"}
    
    kb = InlineKeyboardBuilder()
    for cat in data["categories"]:
        kb.row(types.InlineKeyboardButton(text=cat.capitalize(), callback_data=f"delcat_{cat}"))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="manage_trailers"))
    
    await callback.message.edit_text("Выберите категорию прицепа для удаления:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("delcat_"))
async def delete_trailer_category(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    cat = callback.data.split("_",1)[1]
    user_state[uid].update({"category":cat, "step":"delete_select_trailer"})
    
    kb = InlineKeyboardBuilder()
    for t in data["categories"][cat]:
        kb.row(types.InlineKeyboardButton(text=f"{t['name']} – {t['location']}", callback_data=f"deltrailer_{t['id']}"))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="delete_trailer"))
    
    await callback.message.edit_text("Выберите прицеп для удаления:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("deltrailer_"))
async def delete_trailer_confirm(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    trailer_id = int(callback.data.split("_",1)[1])
    cat = user_state[uid]["category"]
    
    data["categories"][cat] = [t for t in data["categories"][cat] if t["id"] != trailer_id]
    save_data(data)
    user_state.pop(uid)
    
    await callback.message.edit_text(f"✅ Прицеп удален из категории '{cat}'", reply_markup=get_main_button(OWNER_ID))


# ================== ЗАПУСК ==================
async def main():
    print("Бот запущен. Нажмите CTRL+C для выхода.")
    await dp.start_polling(bot)

if __name__=="__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
