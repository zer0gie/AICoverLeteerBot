import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _parse_admin_ids(raw: str) -> set[int]:
    if not raw:
        return set()
    parts = [part.strip() for part in raw.split(",")]
    return {int(part) for part in parts if part.isdigit()}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    openai_base_url: str | None
    openai_model: str
    daily_limit: int
    database_path: str
    vacancy_http_timeout_seconds: int
    llm_http_timeout_seconds: int
    admin_ids: set[int]


def _load_settings() -> Settings:
    base = os.getenv("OPENAI_BASE_URL", "").strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    # Ollama и многие локальные прокси ждут любой непустой ключ; в доке Ollama часто используют "ollama"
    if base and not api_key:
        api_key = "ollama"

    llm_timeout_raw = os.getenv("LLM_HTTP_TIMEOUT", "").strip()
    legacy_http = os.getenv("HTTP_TIMEOUT_SECONDS", "").strip()
    llm_http_timeout_seconds = int(
        llm_timeout_raw or legacy_http or "600",
    )
    vacancy_http_timeout_seconds = int(os.getenv("VACANCY_HTTP_TIMEOUT", "45"))

    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        openai_api_key=api_key,
        openai_base_url=base if base else None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        daily_limit=int(os.getenv("DAILY_LIMIT", "10")),
        database_path=os.getenv("DATABASE_PATH", "bot.db").strip(),
        vacancy_http_timeout_seconds=vacancy_http_timeout_seconds,
        llm_http_timeout_seconds=llm_http_timeout_seconds,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
    )


settings = _load_settings()

if not settings.telegram_bot_token:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required in .env")

if not settings.openai_api_key:
    raise RuntimeError(
        "OPENAI_API_KEY is required in .env (или задайте OPENAI_BASE_URL для локальной LLM — тогда ключ по умолчанию ollama)"
    )
