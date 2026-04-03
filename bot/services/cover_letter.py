from openai import AsyncOpenAI

from bot.services.hh_parser import VacancyData


DEFAULT_TEMPLATE = """
Здравствуйте!

Меня заинтересовала вакансия {vacancy_title} в компании {company}.

Кратко обо мне:
{profile}

Почему подхожу:
- ...
- ...
- ...

Готов обсудить, как могу быть полезен вашей команде.
Спасибо за внимание!
"""


def _fill_template(template: str, vacancy: VacancyData, profile: str) -> str:
    return (
        template.replace("{vacancy_title}", vacancy.title.strip())
        .replace("{company}", vacancy.company.strip())
        .replace("{profile}", profile.strip())
    )


class CoverLetterService:
    def __init__(
        self,
        api_key: str,
        model: str,
        request_timeout: int = 20,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        kwargs: dict = {"api_key": api_key, "timeout": request_timeout}
        if base_url:
            kwargs["base_url"] = base_url
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
        filled_template = _fill_template(raw_template, vacancy, safe_profile)

        prompt = f"""Напиши одно готовое сопроводительное письмо от первого лица (только «я»), целиком на русском языке.

Факты о вакансии:
— Должность: {vacancy.title}
— Компания: {vacancy.company}
— Ссылку в текст письма не вставляй.

Фрагмент описания вакансии (выбери 1–2 релевантных тезиса, без полного пересказа):
{vacancy.description}

Профиль кандидата (опирайся только на это; не выдумывай стаж, студии и проекты):
{safe_profile}

Структура (перепиши связными абзацами, не копируй список с «...»):
{filled_template}

СТРОГО ЗАПРЕЩЕНО (любой такой фрагмент = провал задания):
— Любой текст не на русском: английские/китайские/другие предложения, кроме имён технологий латиницей (Unity, C#, .NET, UI и т.п.).
— Слова и штампы: various, knew how, worked on, sincerely, best regards, regards, yours, candidate, vacancy, modern (как англицизм).
— Плейсхолдеры в квадратных скобках: [ваше имя], [имя], тире вместо имени.
— Фразы вроде «Вам это просят», «кандидат с опытом — это я».
— Третье лицо про себя («кандидат обладает») — только «я».

Заверши письмо по-русски: «С уважением» и новая строка, без имени, или одна строка «Спасибо за внимание.» — без английской подписи.

Объём примерно 900–1400 символов, 3–5 абзацев.
"""

        system = (
            "Ты профессиональный редактор деловых писем на русском языке. "
            "Вывод: только тело письма. Без заголовка «Сопроводительное письмо», без приветствия «Тема:», без пояснений к заданию. "
            "Каждое предложение — грамотный русский; технологии можно латиницей (Unity, C#). "
            "Не смешивай языки. Не имитируй переводчик и не добавляй постскриптумы."
        )

        # Chat Completions: совместимо с OpenAI API и с Ollama (OpenAI-совместимый слой на /v1)
        response = await self._client.chat.completions.create(
            model=self.model,
            temperature=0.25,
            top_p=0.85,
            max_tokens=1200,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        return (content or "").strip()
