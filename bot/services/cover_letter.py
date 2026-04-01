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

Буду рад(а) обсудить, как могу быть полезен(полезна) вашей команде.
Спасибо за внимание!
"""


class CoverLetterService:
    def __init__(self, api_key: str, model: str, request_timeout: int = 20) -> None:
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, timeout=request_timeout)

    async def close(self) -> None:
        await self._client.close()

    async def generate(
        self,
        vacancy: VacancyData,
        profile_text: str,
        template_text: str,
    ) -> str:
        safe_profile = profile_text.strip() or "Кандидат с релевантным опытом."
        safe_template = template_text.strip() or DEFAULT_TEMPLATE.strip()

        prompt = f"""
Ты карьерный ассистент. Напиши короткое, живое сопроводительное письмо на русском.
Требования:
1) Учитывай детали вакансии и профиль кандидата.
2) Не выдумывай опыт, которого нет в профиле.
3) Длина 900-1400 символов.
4) Тон: уверенный и вежливый.
5) Следуй структуре шаблона, но адаптируй текст естественно.

Шаблон письма:
{safe_template}

Профиль кандидата:
{safe_profile}

Данные вакансии:
Название: {vacancy.title}
Компания: {vacancy.company}
Ссылка: {vacancy.url}
Описание:
{vacancy.description}
"""

        response = await self._client.responses.create(
            model=self.model,
            input=prompt,
        )
        return response.output_text.strip()
