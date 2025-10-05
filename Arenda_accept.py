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
        return {"categories": {}, "bookings": [], "pending": []}

def save_data(d):
    if "pending" not in d:
        d["pending"] = []
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

data = load_data()
data.setdefault("pending", [])

# ================== ПРИЦЕПЫ ==================
if not data["categories"]:
    data["categories"] = {
        "для дачи": [{"id": 101+i, "name": f"D-{101+i}", "location": f"ул. Дача, {i+1}"} for i in range(3)],
        "открытый": [{"id": 201+i, "name": f"O-{201+i}", "location": f"ул. Открытый, {i+1}"} for i in range(3)],
        "закрытый": [{"id": 301+i, "name": f"Z-{301+i}", "location": f"ул. Закрытый, {i+1}"} for i in range(3)],
        "эндуро": [{"id": 401+i, "name": f"E-{401+i}", "location": f"ул. Эндуро, {i+1}"} for i in range(3)]
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
    for p in data.get("pending", []):
        if p["trailer_id"] != trailer_id:
            continue
        if overlaps(iso_to_dt(p["start_time"]), iso_to_dt(p["end_time"]), desired_start, desired_end):
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

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def choose_category(callback: types.CallbackQuery):
    await callback.answer()
    cat = callback.data.split("_",1)[1]
    uid = callback.from_user.id
    user_state[uid] = {"step":"choose_start","category":cat}

    kb = InlineKeyboardBuilder()
    for i in range(14):
        date = datetime.now() + timedelta(days=i)
        kb.row(types.InlineKeyboardButton(
            text=date.strftime("%d.%m"), callback_data=f"start_{i}"))
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

    kb = InlineKeyboardBuilder()
    for t in available_trailers:
        kb.row(types.InlineKeyboardButton(text=t["name"], callback_data=f"trailer_{t['id']}"))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"start_{user_state[uid]['start_delay']}"))

    await callback.message.edit_text("Выберите прицеп:", reply_markup=kb.as_markup())
    user_state[uid]["step"]="choose_trailer"

# === pending-заявки ===
@dp.callback_query(lambda c: c.data.startswith("trailer_"))
async def create_pending_booking(callback: types.CallbackQuery):
    await callback.answer()
    uid = callback.from_user.id
    trailer_id = int(callback.data.split("_",1)[1])
    start = iso_to_dt(user_state[uid]["start"])
    end = iso_to_dt(user_state[uid]["end"])

    pending_id = str(int(datetime.now().timestamp() * 1000))
    pending = {
        "id": pending_id,
        "user_id": uid,
        "username": callback.from_user.username,
        "trailer_id": trailer_id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "created_at": datetime.now().isoformat()
    }

    data.setdefault("pending", [])
    data["pending"].append(pending)
    save_data(data)
    user_state.pop(uid, None)

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="✅ Подтвердить бронь", callback_data=f"pending_approve_{pending_id}"))
    kb.row(types.InlineKeyboardButton(text="❌ Отклонить бронь", callback_data=f"pending_reject_{pending_id}"))

    start_str = start.strftime('%d.%m.%Y')
    end_str = end.strftime('%d.%m.%Y')
    await bot.send_message(OWNER_ID,
        f"🔔 Запрос на бронь (ID {pending_id}):\n"
        f"Пользователь: @{callback.from_user.username or uid} (id {uid})\n"
        f"Прицеп ID: {trailer_id}\n"
        f"Период: {start_str} – {end_str}",
        reply_markup=kb.as_markup()
    )

    await callback.message.edit_text("⏳ Запрос на бронь отправлен владельцу на подтверждение. Ожидайте ответа.")

# ================== PENDING approve/reject ==================
@dp.callback_query(lambda c: c.data.startswith("pending_approve_"))
async def pending_approve(callback: types.CallbackQuery):
    await callback.answer()
    pending_id = callback.data.split("pending_approve_")[1]
    pending = next((p for p in data.get("pending", []) if p["id"] == pending_id), None)
    if not pending:
        await callback.message.edit_text("⚠️ Заявка не найдена или уже обработана.")
        return

    booking = {
        "user_id": pending["user_id"],
        "username": pending.get("username"),
        "trailer_id": pending["trailer_id"],
        "start_time": pending["start_time"],
        "end_time": pending["end_time"],
        "status": "active",
        "taken": False,
        "created_at": datetime.now().isoformat(),
        "confirmed_at": datetime.now().isoformat()
    }
    data["bookings"].append(booking)
    data["pending"] = [p for p in data.get("pending", []) if p["id"] != pending_id]
    save_data(data)

    try:
        await bot.send_message(pending["user_id"],
            f"✅ Ваша бронь подтверждена!\nПрицеп {pending['trailer_id']}\n"
            f"{iso_to_dt(pending['start_time']).strftime('%d.%m.%Y')} – {iso_to_dt(pending['end_time']).strftime('%d.%m.%Y')}",
            reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(
                text="🚛 Забрать прицеп", callback_data="take_trailer")).as_markup()
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"✅ Заявка {pending_id} подтверждена владельцем.\n"
        f"Прицеп {pending['trailer_id']}\n"
        f"{iso_to_dt(pending['start_time']).strftime('%d.%m.%Y')} – {iso_to_dt(pending['end_time']).strftime('%d.%m.%Y')}"
    )

@dp.callback_query(lambda c: c.data.startswith("pending_reject_"))
async def pending_reject(callback: types.CallbackQuery):
    await callback.answer()
    pending_id = callback.data.split("pending_reject_")[1]
    pending = next((p for p in data.get("pending", []) if p["id"] == pending_id), None)
    if not pending:
        await callback.message.edit_text("⚠️ Заявка не найдена или уже обработана.")
        return

    data["pending"] = [p for p in data.get("pending", []) if p["id"] != pending_id]
    save_data(data)

    try:
        await bot.send_message(pending["user_id"],
            f"❌ Ваша бронь отклонена владельцем.\nПрицеп {pending['trailer_id']}\n"
            f"{iso_to_dt(pending['start_time']).strftime('%d.%m.%Y')} – {iso_to_dt(pending['end_time']).strftime('%d.%m.%Y')}")
    except Exception:
        pass

    await callback.message.edit_text(
        f"❌ Заявка {pending_id} отклонена владельцем.\n"
        f"Прицеп {pending['trailer_id']}\n"
        f"{iso_to_dt(pending['start_time']).strftime('%d.%m.%Y')} – {iso_to_dt(pending['end_time']).strftime('%d.%m.%Y')}"
    )

# ================== Забрать / Сдать прицеп (не изменялось) ==================
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

# ================== Настройки владельца ==================
@dp.callback_query(lambda c: c.data=="owner_settings")
async def owner_settings(callback: types.CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="📊 Получить статистику", callback_data="show_stats"))
    kb.row(types.InlineKeyboardButton(text="🗑 Сбросить аренду", callback_data="reset_booking"))
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"))
    await callback.message.edit_text("Настройки владельца:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data=="back_main")
async def back_main(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("Выберите действие:", reply_markup=get_main_button(OWNER_ID))

# ================== Статистика ==================
@dp.callback_query(lambda c: c.data=="show_stats")
async def show_stats(callback: types.CallbackQuery):
    await callback.answer()
    now = datetime.now()
    active_bookings = [b for b in data["bookings"] 
                       if b["status"]=="active" and iso_to_dt(b["start_time"]) <= now <= iso_to_dt(b["end_time"])]
    future_bookings = [b for b in data["bookings"] 
                       if b["status"]=="active" and iso_to_dt(b["start_time"]) > now]

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

# ================== Сброс аренд ==================
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

# ================== ЗАПУСК ==================
async def main():
    print("Бот запущен. Нажмите CTRL+C для выхода.")
    await dp.start_polling(bot)

if __name__=="__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
