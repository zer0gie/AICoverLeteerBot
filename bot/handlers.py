import html
import logging
import re
from dataclasses import dataclass
from enum import Enum

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.database import Database
from bot.services.cover_letter import CoverLetterService
from bot.services.hh_parser import VacancyParser

logger = logging.getLogger(__name__)
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


class PendingAction(str, Enum):
    PROFILE = "profile"
    TEMPLATE = "template"


@dataclass
class HandlerDeps:
    db: Database
    parser: VacancyParser
    cover_letter_service: CoverLetterService
    daily_limit: int
    admin_ids: set[int]
    pending_actions: dict[int, PendingAction]


def build_router(
    db: Database,
    parser: VacancyParser,
    cover_letter_service: CoverLetterService,
    daily_limit: int,
    admin_ids: set[int],
) -> Router:
    router = Router()
    deps = HandlerDeps(
        db=db,
        parser=parser,
        cover_letter_service=cover_letter_service,
        daily_limit=daily_limit,
        admin_ids=admin_ids,
        pending_actions={},
    )

    @router.message(Command("start"))
    async def start_handler(message: Message) -> None:
        user_id = message.from_user.id
        await deps.db.ensure_user(user_id, message.from_user.username)
        await message.answer(
            "Привет! Отправь ссылку на вакансию, и я подготовлю сопроводительное письмо.\n\n"
            "Команды:\n"
            "/profile - обновить профиль кандидата\n"
            "/template - обновить шаблон письма\n"
            "/history - последние 10 запросов\n"
            "/pause и /resume - пауза/возобновление\n"
            "/help - подсказка"
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await message.answer(
            "Как пользоваться:\n"
            "1) Выполни /profile и пришли свой профиль.\n"
            "2) При желании задай /template.\n"
            "3) Отправь ссылку на вакансию (например с hh.ru).\n\n"
            "Бот извлечет текст и сгенерирует сопроводительное письмо."
        )

    @router.message(Command("profile"))
    async def profile_handler(message: Message) -> None:
        deps.pending_actions[message.from_user.id] = PendingAction.PROFILE
        await message.answer(
            "Пришли текст профиля (опыт, стек, достижения), 5-15 предложений."
        )

    @router.message(Command("template"))
    async def template_handler(message: Message) -> None:
        deps.pending_actions[message.from_user.id] = PendingAction.TEMPLATE
        await message.answer(
            "Пришли шаблон письма. Можно использовать плейсхолдеры: "
            "{vacancy_title}, {company}, {profile}."
        )

    @router.message(Command("pause"))
    async def pause_handler(message: Message) -> None:
        await deps.db.ensure_user(message.from_user.id, message.from_user.username)
        await deps.db.set_paused(message.from_user.id, True)
        await message.answer("Бот на паузе. Используй /resume для возобновления.")

    @router.message(Command("resume"))
    async def resume_handler(message: Message) -> None:
        await deps.db.ensure_user(message.from_user.id, message.from_user.username)
        await deps.db.set_paused(message.from_user.id, False)
        await message.answer("Готово, снова обрабатываю ссылки на вакансии.")

    @router.message(Command("history"))
    async def history_handler(message: Message) -> None:
        await deps.db.ensure_user(message.from_user.id, message.from_user.username)
        logs = await deps.db.get_last_logs(message.from_user.id, limit=10)
        if not logs:
            await message.answer("История пока пустая.")
            return

        lines = ["Последние запросы:"]
        for item in logs:
            lines.append(
                f"- {item['vacancy_title']} | {item['company']}\n  {item['vacancy_url']}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("stats"))
    async def stats_handler(message: Message) -> None:
        if message.from_user.id not in deps.admin_ids:
            await message.answer("Команда доступна только администратору.")
            return
        stats = await deps.db.get_stats()
        await message.answer(
            "Статистика:\n"
            f"Пользователей: {stats['users_count']}\n"
            f"Запросов: {stats['requests_count']}\n"
            f"Пауза: {stats['paused_count']}"
        )

    @router.message(F.text)
    async def text_handler(message: Message) -> None:
        user_id = message.from_user.id
        text = message.text.strip()
        await deps.db.ensure_user(user_id, message.from_user.username)

        pending = deps.pending_actions.get(user_id)
        if pending == PendingAction.PROFILE:
            await deps.db.set_profile(user_id, text)
            deps.pending_actions.pop(user_id, None)
            await message.answer("Профиль сохранен.")
            return
        if pending == PendingAction.TEMPLATE:
            await deps.db.set_template(user_id, text)
            deps.pending_actions.pop(user_id, None)
            await message.answer("Шаблон сохранен.")
            return

        user = await deps.db.get_user(user_id)
        if user and user["is_paused"] == 1:
            await message.answer("Бот на паузе. Используй /resume.")
            return

        url = _extract_url(text)
        if not url:
            await message.answer("Отправь ссылку на вакансию или используй /help.")
            return

        count_today = await deps.db.get_today_count(user_id)
        if count_today >= deps.daily_limit:
            await message.answer(
                f"Достигнут дневной лимит ({deps.daily_limit}). Попробуй завтра."
            )
            return

        wait_message = await message.answer("Читаю вакансию и готовлю письмо...")
        try:
            vacancy = await deps.parser.parse(url)
            letter = await deps.cover_letter_service.generate(
                vacancy=vacancy,
                profile_text=user["profile_text"] if user else "",
                template_text=user["template_text"] if user else "",
            )
            await deps.db.save_log(
                telegram_id=user_id,
                vacancy_url=url,
                vacancy_title=vacancy.title,
                company=vacancy.company,
                letter_text=letter,
            )

            header = (
                f"<b>{html.escape(vacancy.title)}</b>\n"
                f"{html.escape(vacancy.company)}\n"
                f"{html.escape(vacancy.url)}\n\n"
                "<b>Сопроводительное письмо:</b>\n"
            )
            await wait_message.edit_text(header + html.escape(letter))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to process vacancy URL: %s", exc)
            await wait_message.edit_text(
                "Не удалось обработать ссылку. Проверь URL и попробуй еще раз."
            )

    return router


def _extract_url(text: str) -> str | None:
    match = URL_RE.search(text)
    return match.group(0) if match else None
