import os
from dotenv import load_dotenv
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
pending_reply = {}  # {chat_id: user_id}


load_dotenv()
TOKEN = os.getenv('TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')

bot = Bot(token=TOKEN)
dp = Dispatcher()



def get_channel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Подписаться на канал",
        url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
    )
    return builder.as_markup()

# Определяем состояния FSM для пользователя
class Form(StatesGroup):
    name = State()
    question = State()
    messenger = State()  # Новый шаг: мессенджер
    format = State()     # Следом — формат консультации


# FSM для врача (админа)
class AdminReply(StatesGroup):
    waiting_reply = State()

@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    user = message.from_user
    if not user.username:
        await message.answer(
            "⚠️ У вас не указан username в Telegram.\n\n"
            "Врач сможет ответить только через этого бота, и не сможет найти вас в Telegram по username.\n"
            "Вы можете продолжить заполнение анкеты, или добавить username в настройках Telegram и снова начать (/start).\n\n"
            "Если желаете продолжить, как к Вам можно обращаться?"
        )
    else:
        await message.answer("Напишите, пожалуйста, Ваше имя")
    await state.set_state(Form.name)


@dp.message(Form.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Telegram")],
            [types.KeyboardButton(text="WhatsApp")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Укажите, какой мессенджер для проведения консультации для Вас предпочтителен:",
        reply_markup=keyboard
    )
    await state.set_state(Form.messenger)


@dp.message(Form.messenger)
async def get_messenger(message: types.Message, state: FSMContext):
    await state.update_data(messenger=message.text)
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Видеозвонок")],
            [types.KeyboardButton(text="Аудиозвонок")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Укажите, какой формат консультации для Вас предпочтителен:\n"
        "- видеозвонок\n"
        "- аудиозвонок\n"
        "* длительность консультации до 60 минут",
        reply_markup=keyboard
    )
    await state.set_state(Form.format)



@dp.message(Form.format)
async def get_format(message: types.Message, state: FSMContext):
    await state.update_data(format=message.text)
    data = await state.get_data()
    user = message.from_user

    if not user.username:
        note = "❗️ У пользователя НЕТ username! Связь возможна только через бот (user_id)."
    else:
        note = ""

    text = (
        f"Новая заявка от @{user.username or 'ID:' + str(user.id)}:\n"
        f"ID: {user.id}\n"
        f"{note}\n"
        f"Имя: {data['name']}\n"
        f"Предпочтительный мессенджер: {data['messenger']}\n"
        f"Формат консультации: {data['format']}\n"

    )
    # ======= Блок с кнопкой для врача =======
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user.id}")]
        ]
    )
    await bot.send_message(ADMIN_ID, text, reply_markup=markup)
    # ========================================

    await message.answer(
        "Ваши ответы приняты, большое спасибо! Свяжусь с Вами в ближайшее время для обсуждения даты консультации ❤️",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await message.answer(
        "Больше о репродуктивной медицине можно прочитать тут:",
        reply_markup=get_channel_keyboard()
    )
    await state.clear()

# ======= Логика ответа врача (админа) =======

@dp.callback_query(F.data.startswith("reply_"))
async def admin_reply_callback(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])
    group_id = call.message.chat.id
    pending_reply[group_id] = user_id
    await call.message.reply(
        "Теперь напишите ОДНО сообщение-ответ для клиента (оно будет доставлено лично клиенту, остальные — проигнорируются)."
    )
    print("Врач отвечает клиенту user_id:", user_id)

    await call.answer()





# ======= END =======



@dp.message()
async def group_answer_handler(message: types.Message, state: FSMContext):
    group_id = message.chat.id
    if group_id in pending_reply:
        user_id = pending_reply.pop(group_id)
        reply_text = message.text
        try:
            await bot.send_message(user_id, f"Вам ответил врач:\n\n{reply_text}")
            await message.reply("Ответ отправлен клиенту!")
        except Exception as e:
            await message.reply(f"Ошибка отправки: {e}")
    elif message.chat.type == "private":
        current_state = await state.get_state()
        if current_state:
            return
        await message.answer("Для начала консультации напишите /start")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
