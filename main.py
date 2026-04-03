import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.database import Database
from bot.handlers import build_router
from bot.services.cover_letter import CoverLetterService
from bot.services.vacancy_parser import VacancyParser


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    db = Database(settings.database_path)
    await db.init()

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    parser = VacancyParser(timeout=settings.vacancy_http_timeout_seconds)
    cover_letter_service = CoverLetterService(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        request_timeout=settings.llm_http_timeout_seconds,
        base_url=settings.openai_base_url,
    )

    router = build_router(
        db=db,
        parser=parser,
        cover_letter_service=cover_letter_service,
        daily_limit=settings.daily_limit,
        admin_ids=settings.admin_ids,
    )
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await parser.close()
        await cover_letter_service.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
