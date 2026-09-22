"""
Eslatma vaqtlari bilan ishlash uchun yordamchi funksiyalar.

Vaqtlar hamma joyda "HH:MM" (24 soatlik) matn ko'rinishida saqlanadi va
config.TZ vaqt zonasi bo'yicha tushuniladi.

Ikki rejim bor:
- "times"    — aniq vaqtlar ro'yxati, masalan 09:00, 14:00, 19:00
- "interval" — boshlanish vaqtidan tugash vaqtigacha har N soatda
"""
from __future__ import annotations

import calendar
import datetime
from html import escape

from config import DEFAULT_LEAD_DAYS

# Klaviaturada tayyor tugma sifatida chiqadigan vaqtlar
PRESET_TIMES = ["08:00", "09:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "21:00"]

# "Har N soatda" rejimi uchun tanlanadigan intervallar
INTERVAL_CHOICES = [1, 2, 3, 4, 6, 8, 12]

# Muddatdan necha kun oldin eslatish mumkinligi
LEAD_CHOICES = [3, 5, 7, 10, 14]


def parse_time(raw: str) -> str | None:
    """
    Odam yozgan matnni "HH:MM" ga keltiradi. Qabul qilinadi: "9", "9:5",
    "09.30", "9 30". Noto'g'ri bo'lsa None qaytaradi.
    """
    text = (raw or "").strip().replace(".", ":").replace(" ", ":").replace("-", ":")
    if not text:
        return None
    parts = [p for p in text.split(":") if p != ""]
    try:
        if len(parts) == 1:
            hour, minute = int(parts[0]), 0
        elif len(parts) == 2:
            hour, minute = int(parts[0]), int(parts[1])
        else:
            return None
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def to_minutes(hhmm: str) -> int:
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def from_minutes(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def code(hhmm: str) -> str:
    """"09:30" -> "0930" (callback_data ichida ":" ishlatmaslik uchun)."""
    return hhmm.replace(":", "")


def decode(raw: str) -> str:
    """"0930" -> "09:30"."""
    return f"{raw[:2]}:{raw[2:]}"


def expand_interval(start: str, end: str, hours: int) -> list[str]:
    """Boshlanishdan tugashgacha har `hours` soatda keladigan vaqtlar ro'yxati."""
    start_m, end_m, step = to_minutes(start), to_minutes(end), hours * 60
    if step <= 0 or end_m < start_m:
        return [start]
    return [from_minutes(m) for m in range(start_m, end_m + 1, step)]


def reminder_times(reminder: dict) -> list[str]:
    """Eslatma qaysi vaqtlarda yuborilishini (rejimidan qat'i nazar) ro'yxat qilib beradi."""
    if reminder.get("mode") == "interval":
        return expand_interval(
            reminder["start_time"], reminder["end_time"], reminder["interval_hours"]
        )
    raw = reminder.get("times") or ""
    return sorted({t for t in raw.split(",") if t}, key=to_minutes)


def describe_schedule(reminder: dict) -> str:
    """Eslatma jadvalini odam o'qiydigan matnga aylantiradi."""
    day = reminder["day_of_month"]
    times = reminder_times(reminder)
    if reminder.get("mode") == "interval":
        return (
            f"har oyning {day}-kuni, {reminder['start_time']} dan {reminder['end_time']} gacha "
            f"har {reminder['interval_hours']} soatda ({', '.join(times)})"
        )
    return f"har oyning {day}-kuni, soat {', '.join(times)}"


MONTHS_UZ = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]


def format_moment(moment: datetime.datetime) -> str:
    """datetime -> "22-sentabr, 09:00"."""
    return f"{moment.day}-{MONTHS_UZ[moment.month - 1]}, {moment:%H:%M}"


def format_date(day: datetime.date) -> str:
    """date -> "22-sentabr"."""
    return f"{day.day}-{MONTHS_UZ[day.month - 1]}"


# --- Sikl mantiqi -----------------------------------------------------------
#
# Har bir eslatmaning oylik sikli bor. Sikl "muddat sanasi" bilan belgilanadi
# (masalan 2026-09-22). Muddatdan `lead_days` kun oldin 1-matn ketadi, muddat
# o'tgandan keyin 2-matn — to'xtatilgunicha yoki keyingi sikl boshlangunicha.


def due_date(year: int, month: int, day_of_month: int) -> datetime.date:
    """
    Shu oydagi muddat sanasi. Oyda bunday kun bo'lmasa (31-fevral kabi),
    oyning oxirgi kuni olinadi.
    """
    last_day = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, min(day_of_month, last_day))


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = (year * 12 + month - 1) + delta
    return index // 12, index % 12 + 1


def upcoming_due(day_of_month: int, today: datetime.date) -> datetime.date:
    """Bugun yoki bugundan keyingi eng yaqin muddat sanasi."""
    current = due_date(today.year, today.month, day_of_month)
    if current >= today:
        return current
    year, month = _shift_month(today.year, today.month, 1)
    return due_date(year, month, day_of_month)


def previous_due(day_of_month: int, today: datetime.date) -> datetime.date:
    """Bugundan oldingi eng yaqin muddat sanasi."""
    current = due_date(today.year, today.month, day_of_month)
    if current < today:
        return current
    year, month = _shift_month(today.year, today.month, -1)
    return due_date(year, month, day_of_month)


def phase_on(reminder: dict, today: datetime.date) -> tuple[str | None, datetime.date | None]:
    """
    Shu kuni eslatma qaysi bosqichda ekanini aytadi:
    ("before", muddat) — muddat oldi oynasi ichidamiz, 1-matn ketadi
    ("after",  muddat) — muddat o'tib ketgan, 2-matn ketadi
    (None, None)       — bugun hech narsa yuborilmaydi

    Muhim: keyingi siklning "before" oynasi eskisining "after" quvishidan
    ustun turadi — shuning uchun matn har oy o'zi 1-matnga qaytadi.
    """
    day = reminder["day_of_month"]
    lead = reminder.get("lead_days") or DEFAULT_LEAD_DAYS

    upcoming = upcoming_due(day, today)
    if today >= upcoming - datetime.timedelta(days=lead):
        return "before", upcoming

    previous = previous_due(day, today)
    # Eslatma yaratilishidan oldingi muddatni quvmaymiz
    created = parse_date(reminder.get("created_at"))
    if created and previous < created:
        return None, None
    return "after", previous


def parse_date(raw: str | None) -> datetime.date | None:
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw[:10])
    except ValueError:
        return None


def is_silenced(reminder: dict, due: datetime.date | None) -> bool:
    """Eslatma pauzada yoki shu sikl uchun to'xtatilganmi?"""
    if reminder.get("paused"):
        return True
    return bool(due) and reminder.get("stopped_cycle") == due.isoformat()


def next_send(reminder: dict, now: datetime.datetime) -> datetime.datetime | None:
    """Eslatma keyingi marta aynan qachon yuborilishini hisoblaydi."""
    times = reminder_times(reminder)
    if not times or reminder.get("paused"):
        return None
    for offset in range(0, 400):
        day = now.date() + datetime.timedelta(days=offset)
        phase, due = phase_on(reminder, day)
        if not phase or is_silenced(reminder, due):
            continue
        for hhmm in times:
            hour, minute = (int(x) for x in hhmm.split(":"))
            moment = datetime.datetime.combine(
                day, datetime.time(hour, minute), tzinfo=now.tzinfo
            )
            if moment > now:
                return moment
    return None


# --- Xabar matni ------------------------------------------------------------

DEFAULT_TEXT_BEFORE = (
    "💰 To'lov eslatmasi\n"
    "Muddat: {muddat} — {muddat_holati}.\n"
    "{odamlar}, iltimos to'lovni o'z vaqtida amalga oshiring."
)

DEFAULT_TEXT_AFTER = (
    "⚠️ To'lov muddati o'tdi\n"
    "Muddat {muddat} edi — {muddat_holati}.\n"
    "{odamlar}, iltimos to'lovni imkon qadar tezroq amalga oshiring."
)

# Matn ichida ishlatsa bo'ladigan o'rin egallovchilar
PLACEHOLDERS = ["{odamlar}", "{muddat}", "{muddat_holati}", "{kun}", "{qolgan_kun}", "{otgan_kun}"]


def status_phrase(phase: str, due: datetime.date, today: datetime.date) -> str:
    if phase == "before":
        left = (due - today).days
        return "bugun oxirgi kun" if left == 0 else f"{left} kun qoldi"
    return f"{(today - due).days} kun kechikdi"


def render_text(
    template: str, phase: str, due: datetime.date, today: datetime.date, mentions: str
) -> str:
    """
    Foydalanuvchi yozgan shablonni tayyor xabarga aylantiradi.

    Matn HTML sifatida yuborilgani uchun shablon avval ekranlanadi — shundan
    keyingina tag'lar (<a href=...>) qo'yiladi, ya'ni odam yozgan "<" belgisi
    xabarni buzmaydi.
    """
    left = (due - today).days
    text = escape(template or "", quote=False)
    replacements = {
        "{muddat}": format_date(due),
        "{muddat_holati}": status_phrase(phase, due, today),
        "{kun}": str(due.day),
        "{qolgan_kun}": str(max(left, 0)),
        "{otgan_kun}": str(max(-left, 0)),
    }
    for key, value in replacements.items():
        text = text.replace(key, value)

    if "{odamlar}" in text:
        return text.replace("{odamlar}", mentions)
    return f"{text}\n{mentions}" if mentions else text
