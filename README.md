# AI Telegram Bot: Cover Letter from Vacancy URL

Telegram-бот на Python, который:
- принимает ссылку на страницу вакансии (job-борд или сайт работодателя);
- извлекает текст вакансии;
- генерирует сопроводительное письмо через **OpenAI API** или **локальную LLM** (например Ollama) по вашему шаблону;
- хранит профиль пользователя, историю запросов, лимиты и базовую статистику.

## Функциональность

- Прием ссылки и генерация письма
- Команды:
  - `/start`
  - `/help`
  - `/profile` (сохранить профиль кандидата)
  - `/template` (сохранить шаблон письма)
  - `/history` (последние 10 запросов)
  - `/pause`, `/resume`
  - `/stats`
- Дневной лимит запросов на пользователя
- SQLite для хранения данных
- Обработка ошибок

## Стек

- `aiogram` (Telegram Bot API)
- `openai` (генерация текста)
- `httpx` + `beautifulsoup4` (парсинг вакансии)
- `aiosqlite` (база данных)
- `python-dotenv` (переменные окружения)

## Быстрый старт

1. Установите зависимости:

```bash
pip install -r requirements.txt
```

2. Создайте `.env` из `.env.example` и заполните значения.

**Облако (OpenAI):** укажите `OPENAI_API_KEY`, `OPENAI_MODEL` (например `gpt-4o-mini`), `OPENAI_BASE_URL` не задавайте.

**Локально (Ollama в Docker):** поднимите Ollama (см. ниже), затем в `.env`:

```env
TELEGRAM_BOT_TOKEN=...
OPENAI_BASE_URL=http://127.0.0.1:11434/v1
OPENAI_MODEL=llama3.2:3b
OPENAI_API_KEY=
LLM_HTTP_TIMEOUT=600
VACANCY_HTTP_TIMEOUT=45
```

Ключ для Ollama можно оставить пустым — в коде подставится значение `ollama` (так устроен OpenAI-совместимый слой Ollama).

3. Запустите:

```bash
python main.py
```

## Как пользоваться

1. В Telegram отправьте `/start`.
2. Отправьте `/profile` и вставьте ваш опыт/стек/достижения.
3. (Опционально) отправьте `/template` и задайте структуру письма.
4. Отправьте ссылку на вакансию.
5. Бот вернет персонализированное сопроводительное письмо.

## Локальная LLM (Ollama) и PyCharm

1. **Docker в PyCharm:** включите плагин Docker, в проекте есть `docker-compose.ollama.yml`. Через вкладку **Services** можно запустить compose и смотреть логи контейнера.
2. В терминале (или **Run** конфигурация с `docker compose`):

```bash
docker compose -f docker-compose.ollama.yml up -d
docker compose -f docker-compose.ollama.yml exec ollama ollama pull llama3.2:3b
```

3. Бот запускайте **на хосте** (`python main.py`): в `.env` укажите `OPENAI_BASE_URL=http://127.0.0.1:11434/v1` и имя модели из `ollama list`.

Если когда-нибудь завернёте **и бота, и Ollama** в один compose, вместо `127.0.0.1` используйте имя сервиса: `http://ollama:11434/v1` (только между контейнерами в одной сети).

## Примечания

- Для `/stats` ваш `telegram_id` должен быть в `ADMIN_IDS`.
- Парсинг использует общие HTML-селекторы; полнота полей зависит от вёрстки конкретного сайта.
- Генерация через **Chat Completions** — совместима с OpenAI и с Ollama `/v1`.
