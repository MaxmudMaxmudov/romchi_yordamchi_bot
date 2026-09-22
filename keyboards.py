from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import timeslots as ts


def groups_keyboard(groups: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for g in groups:
        builder.button(text=g["title"] or str(g["chat_id"]), callback_data=f"group:{g['chat_id']}")
    builder.adjust(1)
    return builder.as_markup()


def users_keyboard(users: list, selected_keys: set) -> InlineKeyboardMarkup:
    """
    Har bir odam uchun toggle tugma. selected_keys — tanlangan odamlarning
    unikal kaliti (user_id yoki username asosida).
    """
    builder = InlineKeyboardBuilder()
    for u in users:
        key = _user_key(u)
        mark = "✅ " if key in selected_keys else "☐ "
        label = u["full_name"] or (f"@{u['username']}" if u["username"] else "Noma'lum")
        builder.button(text=mark + label, callback_data=f"user:{key}")
    builder.button(text="➕ Qo'lda username qo'shish", callback_data="user:manual_add")
    builder.button(text="✅ Tanlash tugadi, davom etish", callback_data="users_done")
    builder.adjust(1)
    return builder.as_markup()


def _user_key(u: dict) -> str:
    if u.get("user_id"):
        return f"id:{u['user_id']}"
    return f"un:{u['username']}"


def days_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for day in range(1, 32):
        builder.button(text=str(day), callback_data=f"day:{day}")
    builder.adjust(7)
    return builder.as_markup()


def lead_keyboard() -> InlineKeyboardMarkup:
    """Muddatdan necha kun oldin eslatishni boshlash kerakligi."""
    builder = InlineKeyboardBuilder()
    for days in ts.LEAD_CHOICES:
        builder.button(text=f"{days} kun", callback_data=f"lead:{days}")
    builder.adjust(3)
    return builder.as_markup()


def default_text_keyboard() -> InlineKeyboardMarkup:
    """Matn so'ralayotganda: o'zim yozmayman, standart matn ishlatilsin."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Standart matnni ishlatish", callback_data="text:default")
    builder.adjust(1)
    return builder.as_markup()


def mode_keyboard() -> InlineKeyboardMarkup:
    """O'sha kuni qanday eslatilsin: aniq vaqtlarda yoki har N soatda."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🕐 Aniq vaqtlarni tanlash", callback_data="mode:times")
    builder.button(text="🔁 Har N soatda takrorlash", callback_data="mode:interval")
    builder.adjust(1)
    return builder.as_markup()


def times_keyboard(selected: set) -> InlineKeyboardMarkup:
    """
    Tayyor vaqtlar toggle tugma sifatida. Qo'lda qo'shilgan vaqtlar ham
    ro'yxatga qo'shilib, shu yerda belgilangan holda ko'rinadi.
    """
    builder = InlineKeyboardBuilder()
    options = sorted(set(ts.PRESET_TIMES) | set(selected), key=ts.to_minutes)
    for slot in options:
        mark = "✅ " if slot in selected else "☐ "
        builder.button(text=mark + slot, callback_data=f"time:{ts.code(slot)}")
    builder.adjust(3)
    builder.row(_button("➕ Boshqa vaqt (HH:MM)", "time:manual"))
    builder.row(_button("✅ Vaqtlar tayyor, saqlash", "times_done"))
    return builder.as_markup()


def interval_time_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Interval rejimi uchun boshlanish/tugash vaqtini tanlash (prefix: istart yoki iend)."""
    builder = InlineKeyboardBuilder()
    for slot in ts.PRESET_TIMES:
        builder.button(text=slot, callback_data=f"{prefix}:{ts.code(slot)}")
    builder.adjust(3)
    builder.row(_button("➕ Boshqa vaqt (HH:MM)", f"{prefix}:manual"))
    return builder.as_markup()


def interval_hours_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for hours in ts.INTERVAL_CHOICES:
        builder.button(text=f"{hours} soat", callback_data=f"ihours:{hours}")
    builder.adjust(3)
    return builder.as_markup()


def _button(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)
