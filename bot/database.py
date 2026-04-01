import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path.as_posix())
        self._conn.row_factory = sqlite3.Row

        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                profile_text TEXT DEFAULT '',
                template_text TEXT DEFAULT '',
                is_paused INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                vacancy_url TEXT NOT NULL,
                vacancy_title TEXT NOT NULL,
                company TEXT NOT NULL,
                letter_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    async def ensure_user(self, telegram_id: int, username: str | None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """
            INSERT INTO users(telegram_id, username, created_at, updated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                updated_at = excluded.updated_at
            """,
            (telegram_id, username or "", now, now),
        )
        await self._conn.commit()

    async def get_user(self, telegram_id: int) -> sqlite3.Row | None:
        cursor = await self._conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        return await cursor.fetchone()

    async def set_profile(self, telegram_id: int, profile_text: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """
            UPDATE users
            SET profile_text = ?, updated_at = ?
            WHERE telegram_id = ?
            """,
            (profile_text, now, telegram_id),
        )
        await self._conn.commit()

    async def set_template(self, telegram_id: int, template_text: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """
            UPDATE users
            SET template_text = ?, updated_at = ?
            WHERE telegram_id = ?
            """,
            (template_text, now, telegram_id),
        )
        await self._conn.commit()

    async def set_paused(self, telegram_id: int, is_paused: bool) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """
            UPDATE users
            SET is_paused = ?, updated_at = ?
            WHERE telegram_id = ?
            """,
            (1 if is_paused else 0, now, telegram_id),
        )
        await self._conn.commit()

    async def get_today_count(self, telegram_id: int) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        cursor = await self._conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM request_logs
            WHERE telegram_id = ? AND substr(created_at, 1, 10) = ?
            """,
            (telegram_id, today),
        )
        row = await cursor.fetchone()
        return int(row["count"]) if row else 0

    async def save_log(
        self,
        telegram_id: int,
        vacancy_url: str,
        vacancy_title: str,
        company: str,
        letter_text: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            """
            INSERT INTO request_logs(
                telegram_id, vacancy_url, vacancy_title, company, letter_text, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (telegram_id, vacancy_url, vacancy_title, company, letter_text, now),
        )
        await self._conn.commit()

    async def get_last_logs(self, telegram_id: int, limit: int = 10) -> list[sqlite3.Row]:
        cursor = await self._conn.execute(
            """
            SELECT vacancy_title, company, vacancy_url, created_at
            FROM request_logs
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (telegram_id, limit),
        )
        return await cursor.fetchall()

    async def get_stats(self) -> sqlite3.Row:
        cursor = await self._conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM users) AS users_count,
                (SELECT COUNT(*) FROM request_logs) AS requests_count,
                (SELECT COUNT(*) FROM users WHERE is_paused = 1) AS paused_count
            """
        )
        return await cursor.fetchone()
