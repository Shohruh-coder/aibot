import asyncio
import logging
import os
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from groq import AsyncGroq

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "bot.env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PORT = int(os.getenv("PORT", "10000"))

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN topilmadi. Render Environment yoki .env ichiga kiriting.")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY topilmadi. Render Environment yoki .env ichiga kiriting.")

groq_client = AsyncGroq(api_key=GROQ_API_KEY)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

chat_histories: dict[int, list[dict[str, str]]] = {}
SYSTEM_PROMPT = "Siz foydali AI yordamchisiz. O'zbek tilida javob bering."


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    chat_histories[message.from_user.id] = []
    await message.answer("Salom! Men AI yordamchiman. Istalgan savol bering.")


@dp.message(Command("clear"))
async def clear_handler(message: Message) -> None:
    chat_histories[message.from_user.id] = []
    await message.answer("Suhbat tarixi tozalandi.")


@dp.message(F.text)
async def handle(message: Message) -> None:
    user_id = message.from_user.id
    history = chat_histories.setdefault(user_id, [])

    try:
        await bot.send_chat_action(message.chat.id, "typing")

        history.append({"role": "user", "content": message.text})

        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *history],
            max_tokens=1024,
        )

        answer = response.choices[0].message.content or "Javob bo'sh qaytdi."
        history.append({"role": "assistant", "content": answer})
        await message.answer(answer)
    except Exception as exc:
        logging.exception("Groq yoki Telegram xatoligi")
        await message.answer(f"Xatolik: {exc}")


async def health_check(_: web.Request) -> web.Response:
    return web.Response(text="Bot ishlayapti!")


async def main() -> None:
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info("Web server %s portda ishga tushdi", PORT)

    try:
        logging.info("Bot polling boshlandi")
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
