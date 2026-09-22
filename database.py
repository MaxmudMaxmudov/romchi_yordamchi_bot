"""
Ma'lumotlar bazasi qatlami. aiosqlite orqali async ishlaydi.

Jadvallar:
- groups: bot qo'shilgan guruhlar (bot admin buyruqlar orqali tanlaydigan ro'yxat)
- known_users: har bir guruhda "tanilgan" odamlar (xabar yozganlar yoki qo'lda qo'shilganlar)
- reminders: qaysi guruhda, qaysi kun/vaqtlarda, qanday matn bilan eslatma yuboriladi
- reminder_users: har bir eslatmaga tegishli odamlar
- sent_log: qaysi eslatma qaysi kuni/vaqtda yuborilgani (ikki marta yubormaslik uchun)
"""
from __future__ import annotations

import datetime

import aiosqlite
from config import DB_PATH, DEFAULT_LEAD_DAYS, DEFAULT_TIME

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS groups (
    chat_id INTEGER PRIMARY KEY,
    title TEXT
);

CREATE TABLE IF NOT EXISTS known_users (
    chat_id INTEGER,
    user_id INTEGER,      -- NULL bo'lishi mumkin (faqat username orqali qo'lda qo'shilgan bo'lsa)
    username TEXT,        -- @ belgisisiz
    full_name TEXT,
    PRIMARY KEY (chat_id, user_id, username)
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    day_of_month INTEGER NOT NULL,   -- 1..31
    note TEXT,
    mode TEXT NOT NULL DEFAULT 'times',  -- 'times' yoki 'interval'
    times TEXT,                      -- mode='times': "09:00,14:00,19:00"
    start_time TEXT,                 -- mode='interval': boshlanish, "09:00"
    end_time TEXT,                   -- mode='interval': tugash, "21:00"
    interval_hours INTEGER,          -- mode='interval': har necha soatda
    lead_days INTEGER NOT NULL DEFAULT 7,  -- muddatdan necha kun oldin boshlanadi
    text_before TEXT,                -- muddat oldi matni
    text_after TEXT,                 -- muddat o'tgandagi matn
    paused INTEGER NOT NULL DEFAULT 0,     -- butunlay pauza
    stopped_cycle TEXT,              -- qaysi sikl to'xtatilgan, masalan "2026-09-22"
    created_at TEXT                  -- yaratilgan sana, "2026-09-22"
);

CREATE TABLE IF NOT EXISTS reminder_users (
    reminder_id INTEGER NOT NULL,
    user_id INTEGER,
    username TEXT,
    full_name TEXT,
    FOREIGN KEY (reminder_id) REFERENCES reminders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sent_log (
    reminder_id INTEGER NOT NULL,
    run_date TEXT NOT NULL,          -- "2026-09-22"
    run_time TEXT NOT NULL,          -- "09:00"
    PRIMARY KEY (reminder_id, run_date, run_time)
);
"""

# Eslatmalarni o'qiyotganda hamma joyda kerak bo'ladigan ustunlar
REMINDER_COLUMNS = (
    "id, chat_id, day_of_month, mode, times, start_time, end_time, interval_hours, "
    "lead_days, text_before, text_after, paused, stopped_cycle, created_at"
)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await _migrate(db)
        await db.commit()


async def _migrate(db: aiosqlite.Connection):
    """
    Eski bazalarni yangi sxemaga moslaydi: vaqt ustunlari qo'shiladi va
    vaqtsiz yaratilgan eski eslatmalarga standart vaqt (DEFAULT_TIME) qo'yiladi.
    """
    cursor = await db.execute("PRAGMA table_info(reminders)")
    existing = {row[1] for row in await cursor.fetchall()}
    new_columns = {
        "mode": "TEXT NOT NULL DEFAULT 'times'",
        "times": "TEXT",
        "start_time": "TEXT",
        "end_time": "TEXT",
        "interval_hours": "INTEGER",
        "lead_days": f"INTEGER NOT NULL DEFAULT {DEFAULT_LEAD_DAYS}",
        "text_before": "TEXT",
        "text_after": "TEXT",
        "paused": "INTEGER NOT NULL DEFAULT 0",
        "stopped_cycle": "TEXT",
        "created_at": "TEXT",
    }
    for name, definition in new_columns.items():
        if name not in existing:
            await db.execute(f"ALTER TABLE reminders ADD COLUMN {name} {definition}")
    await db.execute(
        "UPDATE reminders SET mode='times', times=? "
        "WHERE (times IS NULL OR times='') AND (mode IS NULL OR mode='times')",
        (DEFAULT_TIME,),
    )
    # Matnsiz yaratilgan eski eslatmalar standart matnlar bilan ishlayveradi
    # (NULL matn scheduler'da standartga almashtiriladi), lekin yaratilgan
    # sanasi bo'lmasa — bugundan boshlab hisoblaymiz, aks holda o'tgan oyning
    # muddati ham "kechikkan" deb hisoblanib ketadi.
    today = datetime.date.today().isoformat()
    await db.execute("UPDATE reminders SET created_at=? WHERE created_at IS NULL", (today,))


async def upsert_group(chat_id: int, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO groups (chat_id, title) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title",
            (chat_id, title),
        )
        await db.commit()


async def get_groups() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT chat_id, title FROM groups ORDER BY title")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def upsert_known_user(chat_id: int, user_id: int | None, username: str | None, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Bir xil odam ikki marta yozilmasligi uchun avval tekshiramiz
        cursor = await db.execute(
            "SELECT 1 FROM known_users WHERE chat_id=? AND "
            "((user_id IS NOT NULL AND user_id=?) OR (username IS NOT NULL AND username=?))",
            (chat_id, user_id, username),
        )
        exists = await cursor.fetchone()
        if exists:
            return
        await db.execute(
            "INSERT INTO known_users (chat_id, user_id, username, full_name) VALUES (?, ?, ?, ?)",
            (chat_id, user_id, username, full_name),
        )
        await db.commit()


async def get_known_users(chat_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, username, full_name FROM known_users WHERE chat_id=? ORDER BY full_name",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def create_reminder(
    chat_id: int,
    day_of_month: int,
    users: list[dict],
    schedule: dict,
    lead_days: int,
    text_before: str,
    text_after: str,
) -> int:
    """
    schedule — yoki {"mode": "times", "times": ["09:00", "14:00"]},
    yoki {"mode": "interval", "start_time": "09:00", "end_time": "21:00", "interval_hours": 3}.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO reminders (chat_id, day_of_month, mode, times, start_time, end_time, "
            "interval_hours, lead_days, text_before, text_after, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                chat_id,
                day_of_month,
                schedule.get("mode", "times"),
                ",".join(schedule.get("times", [])) or None,
                schedule.get("start_time"),
                schedule.get("end_time"),
                schedule.get("interval_hours"),
                lead_days,
                text_before,
                text_after,
                datetime.date.today().isoformat(),
            ),
        )
        reminder_id = cursor.lastrowid
        for u in users:
            await db.execute(
                "INSERT INTO reminder_users (reminder_id, user_id, username, full_name) VALUES (?, ?, ?, ?)",
                (reminder_id, u.get("user_id"), u.get("username"), u.get("full_name")),
            )
        await db.commit()
        return reminder_id


async def get_active_reminders() -> list[dict]:
    """Barcha eslatmalar (odamlari bilan) — scheduler har daqiqada shulardan foydalanadi."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(f"SELECT {REMINDER_COLUMNS} FROM reminders WHERE paused=0")
        reminders = [dict(r) for r in await cursor.fetchall()]
        for rem in reminders:
            cursor = await db.execute(
                "SELECT user_id, username, full_name FROM reminder_users WHERE reminder_id=?",
                (rem["id"],),
            )
            rem["users"] = [dict(r) for r in await cursor.fetchall()]
        return reminders


async def get_all_reminders(chat_id: int | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = (
            f"SELECT {', '.join('r.' + c for c in REMINDER_COLUMNS.split(', '))}, g.title AS chat_title "
            "FROM reminders r LEFT JOIN groups g ON g.chat_id = r.chat_id "
        )
        if chat_id is not None:
            cursor = await db.execute(
                query + "WHERE r.chat_id=? ORDER BY r.day_of_month", (chat_id,)
            )
        else:
            cursor = await db.execute(query + "ORDER BY r.chat_id, r.day_of_month")
        reminders = [dict(r) for r in await cursor.fetchall()]
        for rem in reminders:
            cursor = await db.execute(
                "SELECT full_name, username FROM reminder_users WHERE reminder_id=?", (rem["id"],)
            )
            rem["users"] = [
                dict(r)["full_name"] or f"@{dict(r)['username']}" for r in await cursor.fetchall()
            ]
        return reminders


async def delete_reminder(reminder_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reminder_users WHERE reminder_id=?", (reminder_id,))
        await db.execute("DELETE FROM sent_log WHERE reminder_id=?", (reminder_id,))
        cursor = await db.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_reminder(reminder_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"SELECT {REMINDER_COLUMNS} FROM reminders WHERE id=?", (reminder_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def set_stopped_cycle(reminder_id: int, cycle: str | None):
    """Shu siklni to'xtatadi (cycle=muddat sanasi) yoki to'xtatishni bekor qiladi (None)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET stopped_cycle=? WHERE id=?", (cycle, reminder_id))
        await db.commit()


async def set_paused(reminder_id: int, paused: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reminders SET paused=? WHERE id=?", (1 if paused else 0, reminder_id)
        )
        await db.commit()


async def resume_reminder(reminder_id: int):
    """Pauzani ham, shu sikl to'xtatishini ham bekor qiladi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reminders SET paused=0, stopped_cycle=NULL WHERE id=?", (reminder_id,)
        )
        await db.commit()


async def claim_send(reminder_id: int, run_date: str, run_time: str) -> bool:
    """
    Shu eslatmani shu kun va shu vaqt uchun "yuborish huquqini" band qiladi.
    True qaytsa — hali yuborilmagan, yuborish kerak. False — allaqachon yuborilgan.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO sent_log (reminder_id, run_date, run_time) VALUES (?, ?, ?)",
            (reminder_id, run_date, run_time),
        )
        await db.commit()
        return cursor.rowcount > 0


async def forget_send(reminder_id: int, run_date: str, run_time: str):
    """Yuborish muvaffaqiyatsiz bo'lsa, belgini olib tashlaymiz (keyingi urinishda qayta uriniladi)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM sent_log WHERE reminder_id=? AND run_date=? AND run_time=?",
            (reminder_id, run_date, run_time),
        )
        await db.commit()


async def prune_sent_log(before_date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sent_log WHERE run_date < ?", (before_date,))
        await db.commit()
