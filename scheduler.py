"""
Har daqiqada bir marta ishga tushadi va shu daqiqaga to'g'ri keladigan
eslatmalarni topib, tegishli guruhlarga odamlarni tag qilib xabar yuboradi.

Har bir eslatma ikki bosqichda ishlaydi:
- muddatdan `lead_days` kun oldin boshlab, muddat kunigacha — 1-matn
- muddat o'tgandan keyin — 2-matn, /stop bilan to'xtatilgunicha yoki
  keyingi siklning oldindan eslatish oynasi boshlangunicha

Bir kunda bir necha marta yuborilishi mumkin (aniq vaqtlar ro'yxati yoki
"har N soatda" rejimi). Har bir yuborish `sent_log` jadvaliga yozib boriladi —
shu sababli bot qayta ishga tushsa ham xabar ikki marta ketmaydi.
"""
from __future__ import annotations

import datetime
import logging
from html import escape

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
import timeslots as ts
from config import CATCHUP_MINUTES, TZ

logger = logging.getLogger(__name__)


def build_mention(user: dict) -> str:
    """
    user_id bo'lsa — tg://user?id= orqali ism bilan tag (username bo'lmasa ham ishlaydi).
    Bo'lmasa — @username matn ko'rinishida (Telegram avtomatik link qiladi).
    """
    if user.get("user_id"):
        name = escape(user.get("full_name") or "foydalanuvchi", quote=False)
        return f'<a href="tg://user?id={user["user_id"]}">{name}</a>'
    return f"@{user['username']}"


def due_slots(reminder: dict, now: datetime.datetime) -> list[str]:
    """
    Shu daqiqada yuborilishi kerak bo'lgan vaqtlar. Odatda bittadan ko'p bo'lmaydi,
    lekin bot bir necha daqiqa o'chib turgan bo'lsa, CATCHUP_MINUTES ichidagi
    o'tkazib yuborilganlari ham qaytariladi.
    """
    window_start = now - datetime.timedelta(minutes=CATCHUP_MINUTES)
    due = []
    for slot in ts.reminder_times(reminder):
        hour, minute = (int(x) for x in slot.split(":"))
        moment = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if window_start <= moment <= now:
            due.append(slot)
    return due


async def send_due_reminders(bot: Bot):
    now = datetime.datetime.now(TZ)
    today = now.date()
    run_date = today.isoformat()

    for rem in await db.get_active_reminders():
        phase, due = ts.phase_on(rem, today)
        if not phase or ts.is_silenced(rem, due):
            continue

        for slot in due_slots(rem, now):
            # sent_log orqali band qilamiz — allaqachon yuborilgan bo'lsa, o'tkazib yuboramiz
            if not await db.claim_send(rem["id"], run_date, slot):
                continue
            mentions = " ".join(build_mention(u) for u in rem["users"])
            template = rem["text_before"] if phase == "before" else rem["text_after"]
            if not template:
                template = ts.DEFAULT_TEXT_BEFORE if phase == "before" else ts.DEFAULT_TEXT_AFTER
            text = ts.render_text(template, phase, due, today, mentions)
            try:
                await bot.send_message(rem["chat_id"], text, parse_mode="HTML")
                logger.info(
                    "Eslatma #%s yuborildi (chat_id=%s, %s, bosqich=%s)",
                    rem["id"], rem["chat_id"], slot, phase,
                )
            except Exception as e:
                # Masalan, bot guruhdan chiqarib yuborilgan bo'lishi mumkin — dasturni to'xtatmaymiz
                await db.forget_send(rem["id"], run_date, slot)
                logger.error(
                    "Eslatma #%s yuborishda xatolik (chat_id=%s, %s): %s",
                    rem["id"], rem["chat_id"], slot, e,
                )


async def cleanup_sent_log():
    """Eski yozuvlar jadvalni shishirmasligi uchun 7 kundan oldingilarini o'chiramiz."""
    cutoff = (datetime.datetime.now(TZ) - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    await db.prune_sent_log(cutoff)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(
        send_due_reminders,
        trigger="cron",
        minute="*",
        args=[bot],
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60,
        id="send_due_reminders",
    )
    scheduler.add_job(
        cleanup_sent_log,
        trigger="cron",
        hour=4,
        minute=0,
        coalesce=True,
        id="cleanup_sent_log",
    )
    scheduler.start()
    logger.info("Scheduler ishga tushdi (vaqt zonasi: %s)", TZ)
    return scheduler
