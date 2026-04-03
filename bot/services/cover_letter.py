import re

import httpx
from openai import AsyncOpenAI

from bot.services.vacancy_parser import VacancyData


DEFAULT_TEMPLATE = """
Здравствуйте!

{opening}

Кратко обо мне:
{profile}

Соответствие задачам вакансии (кратко, по пунктам из описания ниже):
- ...

Готов обсудить задачи и формат работы.
С уважением.
"""


def _opening_line(vacancy: VacancyData) -> str:
    title = vacancy.title.strip()
    company = vacancy.company.strip()
    if title and company:
        return f"Меня заинтересовала вакансия «{title}» в компании {company}."
    if title:
        return f"Меня заинтересовала вакансия «{title}»."
    if company:
        return f"Обращаюсь в {company} по открытой позиции."
    return "Обращаюсь по размещённой вакансии."


def _fill_template(template: str, vacancy: VacancyData, profile: str) -> str:
    title = vacancy.title.strip()
    company = vacancy.company.strip()
    out = (
        template.replace("{vacancy_title}", title)
        .replace("{company}", company)
        .replace("{profile}", profile.strip())
    )
    if not company:
        out = re.sub(r"\s*в компании\s+", " ", out, flags=re.IGNORECASE)
        out = re.sub(r"\s*в компании\.", ".", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


class CoverLetterService:
    def __init__(
        self,
        api_key: str,
        model: str,
        request_timeout: int = 20,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        kwargs: dict = {"api_key": api_key}
        if base_url:
            # Локальный Ollama: долгая генерация на CPU; без повторов при 500/timeout (иначе 2× ожидание).
            kwargs["base_url"] = base_url
            kwargs["max_retries"] = 0
            kwargs["timeout"] = httpx.Timeout(
                connect=60.0,
                read=float(request_timeout),
                write=120.0,
                pool=60.0,
            )
        else:
            kwargs["timeout"] = request_timeout
        self._client = AsyncOpenAI(**kwargs)

    async def close(self) -> None:
        await self._client.close()

    async def generate(
        self,
        vacancy: VacancyData,
        profile_text: str,
        template_text: str,
    ) -> str:
        safe_profile = profile_text.strip() or (
            "Профиль в боте пока не заполнен: не придумывай конкретный опыт и проекты; "
            "опиши мотивацию и готовность обсудить задачи общими фразами, только от первого лица (я)."
        )
        raw_template = template_text.strip() or DEFAULT_TEMPLATE.strip()
        if template_text.strip():
            filled_template = _fill_template(raw_template, vacancy, safe_profile)
        else:
            filled_template = (
                raw_template.replace("{opening}", _opening_line(vacancy))
                .replace("{profile}", safe_profile)
            )

        facts_lines: list[str] = []
        if vacancy.title.strip():
            facts_lines.append(f"— Должность: {vacancy.title.strip()}")
        if vacancy.company.strip():
            facts_lines.append(f"— Компания: {vacancy.company.strip()}")
        facts_section = (
            "Известные сведения о позиции:\n" + "\n".join(facts_lines) + "\n\n"
            if facts_lines
            else ""
        )

        desc = vacancy.description.strip()
        desc_block = (
            desc
            if desc
            else "(текст вакансии с сайта не извлечён — опирайся только на профиль и общий характер роли, без выдуманных обязанностей)"
        )

        prompt = f"""Напиши одно сопроводительное письмо от первого лица («я»), на русском языке.

Стиль: деловой, сдержанный, без «воды» и общих лозунгов о росте/команде, если это не следует из вакансии. Короткие абзацы.

Содержание:
— Опирайся на формулировки задач и требований из описания вакансии: перечисли 2–4 конкретных пункта, с которыми сопоставляешь свой опыт (если описания нет — не выдумывай детали).
— Не повторяй дословно весь текст вакансии.

{facts_section}Если должность или компания не указаны выше — не называй их в письме и не объясняй почему.

Описание вакансии (источник требований и задач):
{desc_block}

Профиль кандидата (только факты отсюда; не придумывай места работы и проекты):
{safe_profile}

Ориентир структуры (перепиши цельно; пункты со «...» замени содержанием):
{filled_template}

ЗАПРЕЩЕНО:
— Упоминать отсутствие названия компании/должности, ошибки парсинга, «не удалось определить».
— Лишний пафос и общие фразы без привязки к задачам из описания.
— Английский текст, кроме имён продуктов/систем (1С, SAP и т.п.).

Объём примерно 650–1100 символов, 2–4 абзаца. Завершение: «С уважением,» и строка без имени, либо только «С уважением.» без фамилии.
"""

        system = (
            "Ты редактор деловой переписки на русском. Пиши формально и по существу. "
            "Вывод: только текст письма, без заголовка «Сопроводительное письмо» и без служебных комментариев."
        )

        # Chat Completions: совместимо с OpenAI API и с Ollama (OpenAI-совместимый слой на /v1)
        response = await self._client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            top_p=0.8,
            max_tokens=900,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        return (content or "").strip()
