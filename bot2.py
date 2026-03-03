import re
from datetime import datetime, timedelta, timezone
import asyncio
from telethon import TelegramClient, events, Button

# -------------------- Настройки --------------------
API_ID = ... 
API_HASH = "..." 
BOT_TOKEN = "..." 
CHANNELS = { 
    "svao": "username1", 
    "vao": "username2", 
    "butovo": "username3"
}

DAYS_LIMIT = 365  # ищем посты старше 1 года
SEARCH_START_YEAR = 2023  # ищем только начиная с 2023 года
# ---------------------------------------------------

bot = TelegramClient("bot_session", API_ID, API_HASH)
client = TelegramClient("user_session", API_ID, API_HASH)

pattern_years = re.compile(r"\(всего \d+ (лет|год|года) назад\)", re.IGNORECASE)

def normalize(text: str) -> str:
    """Приведение текста к нижнему регистру, удаление знаков препинания, цифр, эмодзи и ссылок"""
    text = text.lower()
    text = re.sub(r"https?://\S+", "", text)  # удаляем ссылки
    text = re.sub(r"\d+", "", text)  # удаляем цифры
    text = re.sub(r"[^\wа-яё ]", "", text)  # оставляем только буквы и пробелы
    text = re.sub(r"\s+", " ", text)  # нормализуем пробелы
    return text.strip()

async def handle_missing(chat_id, channel_key, channel_name):
    progress_msg = await bot.send_message(chat_id, f"⏳ Идёт поиск пропущенных постов в {channel_name}...")

    last_seen = {}  # нормализованный текст -> список (дата, id, оригинальный текст)
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=DAYS_LIMIT)
    search_start_date = datetime(SEARCH_START_YEAR, 1, 1, tzinfo=timezone.utc)
    channel = CHANNELS[channel_key]

    count = 0
    async for msg in client.iter_messages(channel, reverse=True):
        if msg.date < search_start_date:
            continue  # игнорируем посты до 2023 года

        count += 1
        if count % 500 == 0:
            await progress_msg.edit(f"⏳ Просмотрено {count} сообщений...")

        if not msg.message:
            continue
        if not pattern_years.search(msg.message):
            continue

        txt = msg.message.split("---")[0] if "---" in msg.message else msg.message

        # удаляем фразу "(всего X лет/год/года назад)" перед нормализацией
        txt_for_norm = re.sub(pattern_years, "", txt)
        norm = normalize(txt_for_norm)

        if norm not in last_seen:
            last_seen[norm] = []
        last_seen[norm].append((msg.date, msg.id, txt))

    missing = []
    for norm, entries in last_seen.items():
        entries.sort(key=lambda x: x[0])
        latest_date = entries[-1][0]

        # если последний пост с таким текстом меньше года назад — пропускаем
        if latest_date >= one_year_ago:
            continue

        # берём самый старый пост для отправки
        oldest_entry = entries[0]
        missing.append(oldest_entry)

    missing.sort(key=lambda x: x[0])

    if not missing:
        await progress_msg.edit(f"👌 Нет пропущенных постов в {channel_name}!")
        return

    await progress_msg.edit(f"✅ Найдено {len(missing)} пропущенных постов в {channel_name}!")

    # Отправляем каждое сообщение отдельно с ссылкой на оригинал
    for dt, msg_id, original_text in missing:
        link = f"https://t.me/{CHANNELS[channel_key]}/{msg_id}"
        msg_text = f"• {dt.strftime('%d.%m.%Y')} — {original_text}\n\n[Ссылка на пост]({link})"
        await bot.send_message(chat_id, msg_text, parse_mode="Markdown")

@bot.on(events.NewMessage(pattern="/start"))
async def start_panel(event):
    buttons = [
        [Button.inline("СВАО", b"svao")],
        [Button.inline("ВАО", b"vao")],
        [Button.inline("Бутово", b"butovo")]
    ]
    await bot.send_message(event.sender_id, "Выберите канал для поиска пропущенных постов:", buttons=buttons)

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    await event.answer("Идёт поиск, это может занять время...")
    data = event.data.decode("utf-8")
    if data == "svao":
        await handle_missing(event.sender_id, "svao", "СВАО")
    elif data == "vao":
        await handle_missing(event.sender_id, "vao", "ВАО")
    elif data == "butovo":
        await handle_missing(event.sender_id, "butovo", "Бутово")

async def main():
    print("Введите номер телефона для авторизации вашего аккаунта (если сессия отсутствует):")
    await client.start()
    print("Пользовательский клиент готов!")

    print("Запускаем бота...")
    await bot.start(bot_token=BOT_TOKEN)
    print("Бот запущен!")

    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
