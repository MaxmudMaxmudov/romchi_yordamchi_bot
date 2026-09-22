"""
Botga shaxsiy (DM) xabar yozgan admin uchun bosqichma-bosqich oqim:

/new_reminder -> guruh -> odamlar -> kun -> necha kun oldin -> rejim ->
vaqt(lar) -> 1-matn -> 2-matn -> saqlash

Vaqt rejimlari:
- "Aniq vaqtlar"  — bir kunda bir nechta vaqt tanlanadi (09:00, 14:00, 19:00 ...)
- "Har N soatda"  — boshlanish vaqtidan tugash vaqtigacha belgilangan oraliqda

Matnlar:
- 1-matn muddat oldi oynasida, 2-matn muddat o'tgandan keyin yuboriladi.
  To'xtatish: /stop (shu sikl), /pause (butunlay), /resume (qaytarish).

Bu handlerlar faqat botning shaxsiy chatida (private) ishlaydi.
"""
from __future__ import annotations

import datetime
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
import timeslots as ts
from config import DEFAULT_LEAD_DAYS, DEFAULT_TIME, TZ
from states import NewReminder

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


HELP_TEXT = (
    "<b>To'lov eslatuvchi bot</b>\n"
    "Guruhdagi odamlarni to'lov muddatidan oldin va keyin tag qilib eslatadi.\n\n"
    "<b>Yaratish</b>\n"
    "/new_reminder — guruh → odamlar → muddat kuni → necha kun oldin →\n"
    "vaqt(lar) → 1-matn (muddatgacha) va 2-matn (muddat o'tgach)\n"
    "/cancel — yaratish oqimini yarim yo'lda bekor qilish\n\n"
    "<b>Ko'rish</b>\n"
    "/list_reminders — barcha eslatmalar, holati va keyingi yuborilish vaqti\n"
    "/show_text &lt;id&gt; — eslatmaning ikkala matni\n\n"
    "<b>Boshqarish</b>\n"
    "/stop &lt;id&gt; — to'lov qilindi: shu oylik eslatmalar to'xtaydi "
    "(keyingi oy o'zi tiklanadi)\n"
    "/pause &lt;id&gt; — butunlay to'xtatadi, keyingi oylarda ham\n"
    "/resume &lt;id&gt; — /stop yoki /pause ni bekor qiladi\n"
    "/delete_reminder &lt;id&gt; — butunlay o'chiradi\n\n"
    "Muddat o'tgach xabarlar o'zi to'xtamaydi — /stop siz to'xtatasiz."
)


@router.message(Command("start"))
@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.message(Command("new_reminder"))
async def cmd_new_reminder(message: Message, state: FSMContext):
    groups = await db.get_groups()
    if not groups:
        await message.answer(
            "Hozircha hech qanday guruh topilmadi.\n"
            "Botni kerakli guruhga qo'shing va guruhda biron kishi xabar yozsin, "
            "shundan keyin guruh shu yerda ko'rinadi."
        )
        return
    await state.set_state(NewReminder.choosing_group)
    await message.answer("Qaysi guruh uchun eslatma yaratamiz?", reply_markup=kb.groups_keyboard(groups))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer("Bekor qiladigan narsa yo'q.")
        return
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.callback_query(NewReminder.choosing_group, F.data.startswith("group:"))
async def choose_group(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":", 1)[1])
    groups = {g["chat_id"]: g["title"] for g in await db.get_groups()}
    await state.update_data(chat_id=chat_id, chat_title=groups.get(chat_id) or str(chat_id), selected_users=[])

    users = await db.get_known_users(chat_id)
    await state.update_data(available_users=users)

    if not users:
        await callback.message.edit_text(
            "Bu guruhda hali tanilgan odamlar yo'q (hech kim bot ko'rgan holatda yozmagan).\n"
            "Hozircha faqat qo'lda username qo'shishing mumkin.",
            reply_markup=kb.users_keyboard([], set()),
        )
    else:
        await callback.message.edit_text(
            "Kimlarga eslatma yuborilsin? Kerakli odamlarni bosib tanlang:",
            reply_markup=kb.users_keyboard(users, set()),
        )
    await state.set_state(NewReminder.choosing_users)
    await callback.answer()


@router.callback_query(NewReminder.choosing_users, F.data.startswith("user:"))
async def toggle_user(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]

    if key == "manual_add":
        await state.set_state(NewReminder.waiting_manual_username)
        await callback.message.answer(
            "Odamning Telegram username'ini yuboring (masalan: @ali_valiyev).\n"
            "Eslatma: agar bu odam hali botga /start bosmagan yoki guruhda yozmagan bo'lsa, "
            "eslatmada uni faqat @username sifatida tag qilamiz (bosilganda profili ochiladi)."
        )
        await callback.answer()
        return

    data = await state.get_data()
    selected = set(data.get("selected_users", []))
    if key in selected:
        selected.remove(key)
    else:
        selected.add(key)
    await state.update_data(selected_users=list(selected))

    users = data.get("available_users", [])
    await callback.message.edit_reply_markup(reply_markup=kb.users_keyboard(users, selected))
    await callback.answer()


@router.message(NewReminder.waiting_manual_username, F.text)
async def manual_username_added(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        await message.answer("Hozir username kutyapman. Oqimni bekor qilish uchun /cancel yuboring.")
        return
    username = message.text.strip().lstrip("@")
    if not username:
        await message.answer("Username bo'sh bo'lmasligi kerak. Qaytadan yuboring, masalan: @ali_valiyev")
        return

    data = await state.get_data()
    chat_id = data["chat_id"]

    await db.upsert_known_user(chat_id=chat_id, user_id=None, username=username, full_name=f"@{username}")

    users = await db.get_known_users(chat_id)
    selected = set(data.get("selected_users", []))
    selected.add(f"un:{username}")
    await state.update_data(available_users=users, selected_users=list(selected))
    await state.set_state(NewReminder.choosing_users)

    await message.answer(
        f"@{username} ro'yxatga qo'shildi va tanlandi. Davom eting:",
        reply_markup=kb.users_keyboard(users, selected),
    )


@router.callback_query(NewReminder.choosing_users, F.data == "users_done")
async def users_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = set(data.get("selected_users", []))
    if not selected:
        await callback.answer("Kamida bitta odam tanlashingiz kerak.", show_alert=True)
        return

    await state.set_state(NewReminder.choosing_day)
    await callback.message.edit_text(
        "Oyning qaysi kunida eslatma yuborilsin?", reply_markup=kb.days_keyboard()
    )
    await callback.answer()


# --- Kun tanlangandan keyin: rejim va vaqtlar -------------------------------


@router.callback_query(NewReminder.choosing_day, F.data.startswith("day:"))
async def choose_day(callback: CallbackQuery, state: FSMContext):
    day = int(callback.data.split(":", 1)[1])
    await state.update_data(day=day)
    await state.set_state(NewReminder.choosing_lead)
    await callback.message.edit_text(
        f"To'lov muddati: har oyning <b>{day}</b>-kuni.\n\n"
        "Eslatish muddatdan necha kun oldin boshlansin?\n"
        "(o'sha kundan muddatgacha har kuni eslatma ketadi)",
        parse_mode="HTML",
        reply_markup=kb.lead_keyboard(),
    )
    await callback.answer()


@router.callback_query(NewReminder.choosing_lead, F.data.startswith("lead:"))
async def choose_lead(callback: CallbackQuery, state: FSMContext):
    lead_days = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    await state.update_data(lead_days=lead_days)
    await state.set_state(NewReminder.choosing_mode)
    await callback.message.edit_text(
        f"Muddat: har oyning {data['day']}-kuni, eslatish {lead_days} kun oldin boshlanadi.\n\n"
        "O'sha kunlarda qanday eslatamiz?",
        reply_markup=kb.mode_keyboard(),
    )
    await callback.answer()


@router.callback_query(NewReminder.choosing_mode, F.data == "mode:times")
async def mode_times(callback: CallbackQuery, state: FSMContext):
    await state.update_data(times=[DEFAULT_TIME])
    await state.set_state(NewReminder.choosing_times)
    await callback.message.edit_text(
        f"Qaysi vaqt(lar)da eslatma yuborilsin? Bir nechtasini tanlashingiz mumkin "
        f"— o'sha kuni har biri uchun alohida xabar ketadi.\n\n"
        f"Vaqtlar {TZ} bo'yicha.",
        reply_markup=kb.times_keyboard({DEFAULT_TIME}),
    )
    await callback.answer()


@router.callback_query(NewReminder.choosing_times, F.data.startswith("time:"))
async def toggle_time(callback: CallbackQuery, state: FSMContext):
    raw = callback.data.split(":", 1)[1]

    if raw == "manual":
        await state.update_data(manual_target="times")
        await state.set_state(NewReminder.waiting_manual_time)
        await callback.message.answer("Vaqtni HH:MM ko'rinishida yuboring, masalan: 09:30")
        await callback.answer()
        return

    slot = ts.decode(raw)
    data = await state.get_data()
    times = set(data.get("times", []))
    if slot in times:
        times.remove(slot)
    else:
        times.add(slot)
    await state.update_data(times=sorted(times, key=ts.to_minutes))
    await callback.message.edit_reply_markup(reply_markup=kb.times_keyboard(times))
    await callback.answer()


@router.callback_query(NewReminder.choosing_times, F.data == "times_done")
async def times_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    times = sorted(set(data.get("times", [])), key=ts.to_minutes)
    if not times:
        await callback.answer("Kamida bitta vaqt tanlang.", show_alert=True)
        return
    await _ask_text_before(callback.message, state, {"mode": "times", "times": times})
    await callback.answer()


# --- "Har N soatda" rejimi --------------------------------------------------


@router.callback_query(NewReminder.choosing_mode, F.data == "mode:interval")
async def mode_interval(callback: CallbackQuery, state: FSMContext):
    await state.set_state(NewReminder.choosing_interval_start)
    await callback.message.edit_text(
        f"Takrorlash soat nechada boshlansin?\n\nVaqtlar {TZ} bo'yicha.",
        reply_markup=kb.interval_time_keyboard("istart"),
    )
    await callback.answer()


@router.callback_query(NewReminder.choosing_interval_start, F.data.startswith("istart:"))
async def interval_start(callback: CallbackQuery, state: FSMContext):
    raw = callback.data.split(":", 1)[1]
    if raw == "manual":
        await state.update_data(manual_target="start")
        await state.set_state(NewReminder.waiting_manual_time)
        await callback.message.answer("Boshlanish vaqtini HH:MM ko'rinishida yuboring, masalan: 08:30")
        await callback.answer()
        return

    await state.update_data(start_time=ts.decode(raw))
    await state.set_state(NewReminder.choosing_interval_hours)
    await callback.message.edit_text(
        f"Boshlanish: {ts.decode(raw)}.\n\nHar necha soatda takrorlansin?",
        reply_markup=kb.interval_hours_keyboard(),
    )
    await callback.answer()


@router.callback_query(NewReminder.choosing_interval_hours, F.data.startswith("ihours:"))
async def interval_hours(callback: CallbackQuery, state: FSMContext):
    hours = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    await state.update_data(interval_hours=hours)
    await state.set_state(NewReminder.choosing_interval_end)
    await callback.message.edit_text(
        f"Boshlanish: {data['start_time']}, har {hours} soatda.\n\n"
        "Qaysi vaqtgacha takrorlansin?",
        reply_markup=kb.interval_time_keyboard("iend"),
    )
    await callback.answer()


@router.callback_query(NewReminder.choosing_interval_end, F.data.startswith("iend:"))
async def interval_end(callback: CallbackQuery, state: FSMContext):
    raw = callback.data.split(":", 1)[1]
    if raw == "manual":
        await state.update_data(manual_target="end")
        await state.set_state(NewReminder.waiting_manual_time)
        await callback.message.answer("Tugash vaqtini HH:MM ko'rinishida yuboring, masalan: 21:00")
        await callback.answer()
        return

    data = await state.get_data()
    end_time = ts.decode(raw)
    if ts.to_minutes(end_time) < ts.to_minutes(data["start_time"]):
        await callback.answer(
            f"Tugash vaqti boshlanishdan ({data['start_time']}) oldin bo'lmasligi kerak.",
            show_alert=True,
        )
        return

    await _ask_text_before(
        callback.message,
        state,
        {
            "mode": "interval",
            "start_time": data["start_time"],
            "end_time": end_time,
            "interval_hours": data["interval_hours"],
        },
    )
    await callback.answer()


@router.message(NewReminder.waiting_manual_time, F.text)
async def manual_time_added(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        await message.answer("Hozir vaqt kutyapman. Oqimni bekor qilish uchun /cancel yuboring.")
        return
    slot = ts.parse_time(message.text)
    if not slot:
        await message.answer("Vaqtni tushunmadim. HH:MM ko'rinishida yuboring, masalan: 09:30")
        return

    data = await state.get_data()
    target = data.get("manual_target", "times")

    if target == "times":
        times = set(data.get("times", []))
        times.add(slot)
        await state.update_data(times=sorted(times, key=ts.to_minutes))
        await state.set_state(NewReminder.choosing_times)
        await message.answer(
            f"{slot} qo'shildi. Yana qo'shishingiz yoki saqlashingiz mumkin:",
            reply_markup=kb.times_keyboard(times),
        )
        return

    if target == "start":
        await state.update_data(start_time=slot)
        await state.set_state(NewReminder.choosing_interval_hours)
        await message.answer(
            f"Boshlanish: {slot}.\n\nHar necha soatda takrorlansin?",
            reply_markup=kb.interval_hours_keyboard(),
        )
        return

    # target == "end"
    if ts.to_minutes(slot) < ts.to_minutes(data["start_time"]):
        await message.answer(
            f"Tugash vaqti boshlanishdan ({data['start_time']}) oldin bo'lmasligi kerak. "
            "Boshqa vaqt yuboring."
        )
        return
    await _ask_text_before(
        message,
        state,
        {
            "mode": "interval",
            "start_time": data["start_time"],
            "end_time": slot,
            "interval_hours": data["interval_hours"],
        },
    )


PLACEHOLDER_HELP = (
    "Matn ichida ishlatishingiz mumkin:\n"
    "<code>{odamlar}</code> — tag qilinadigan odamlar (yozmasangiz, oxiriga o'zi qo'shiladi)\n"
    "<code>{muddat}</code> — muddat sanasi, masalan 22-sentabr\n"
    "<code>{muddat_holati}</code> — «3 kun qoldi» / «bugun oxirgi kun» / «5 kun kechikdi»\n"
    "<code>{kun}</code>, <code>{qolgan_kun}</code>, <code>{otgan_kun}</code> — raqamlar"
)


async def _ask_text_before(message: Message, state: FSMContext, schedule: dict):
    """Vaqtlar tanlangach — muddat oldi matnini so'raymiz."""
    await state.update_data(schedule=schedule)
    await state.set_state(NewReminder.waiting_text_before)
    await message.answer(
        "<b>1-matn</b> — muddat yetib kelgunicha yuboriladigan xabar.\n"
        "Matnni yuboring yoki standartini ishlating.\n\n" + PLACEHOLDER_HELP,
        parse_mode="HTML",
        reply_markup=kb.default_text_keyboard(),
    )


async def _ask_text_after(message: Message, state: FSMContext):
    await state.set_state(NewReminder.waiting_text_after)
    await message.answer(
        "<b>2-matn</b> — muddat o'tib ketgandan keyin yuboriladigan xabar.\n"
        "Matnni yuboring yoki standartini ishlating.\n\n" + PLACEHOLDER_HELP,
        parse_mode="HTML",
        reply_markup=kb.default_text_keyboard(),
    )


@router.message(NewReminder.waiting_text_before, F.text)
async def text_before_received(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        await message.answer("Hozir matn kutyapman. Oqimni bekor qilish uchun /cancel yuboring.")
        return
    await state.update_data(text_before=message.text)
    await _ask_text_after(message, state)


@router.callback_query(NewReminder.waiting_text_before, F.data == "text:default")
async def text_before_default(callback: CallbackQuery, state: FSMContext):
    await state.update_data(text_before=ts.DEFAULT_TEXT_BEFORE)
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_text_after(callback.message, state)
    await callback.answer("Standart matn olindi")


@router.message(NewReminder.waiting_text_after, F.text)
async def text_after_received(message: Message, state: FSMContext):
    if message.text.startswith("/"):
        await message.answer("Hozir matn kutyapman. Oqimni bekor qilish uchun /cancel yuboring.")
        return
    await state.update_data(text_after=message.text)
    await _save_reminder(message, state)


@router.callback_query(NewReminder.waiting_text_after, F.data == "text:default")
async def text_after_default(callback: CallbackQuery, state: FSMContext):
    await state.update_data(text_after=ts.DEFAULT_TEXT_AFTER)
    await callback.message.edit_reply_markup(reply_markup=None)
    await _save_reminder(callback.message, state)
    await callback.answer("Standart matn olindi")


@router.message(NewReminder.waiting_text_before)
@router.message(NewReminder.waiting_text_after)
async def text_not_understood(message: Message):
    await message.answer("Matn kutyapman — oddiy matn xabar yuboring.")


async def _save_reminder(message: Message, state: FSMContext):
    """Oqim oxiri: tanlanganlarni bazaga yozib, xulosani ko'rsatamiz."""
    data = await state.get_data()
    schedule = data["schedule"]
    chat_id = data["chat_id"]
    day = data["day"]
    lead_days = data.get("lead_days", DEFAULT_LEAD_DAYS)
    text_before = data.get("text_before") or ts.DEFAULT_TEXT_BEFORE
    text_after = data.get("text_after") or ts.DEFAULT_TEXT_AFTER

    selected_keys = set(data.get("selected_users", []))
    available = {_user_key(u): u for u in data.get("available_users", [])}
    users_to_save = [available[key] for key in selected_keys if key in available]

    reminder_id = await db.create_reminder(
        chat_id=chat_id,
        day_of_month=day,
        users=users_to_save,
        schedule=schedule,
        lead_days=lead_days,
        text_before=text_before,
        text_after=text_after,
    )

    saved = await db.get_reminder(reminder_id)
    names = ", ".join(escape(u["full_name"] or f"@{u['username']}", quote=False) for u in users_to_save)
    upcoming = ts.next_send(saved, datetime.datetime.now(TZ))

    lines = [
        f"✅ Eslatma saqlandi (#{reminder_id})",
        "",
        f"👥 Guruh: {escape(str(data.get('chat_title')), quote=False)}",
        f"📅 Muddat: har oyning {day}-kuni",
        f"⏳ Eslatish: muddatdan {lead_days} kun oldin boshlanadi",
        f"🕐 Vaqt: {', '.join(ts.reminder_times(saved))}",
    ]
    if schedule["mode"] == "interval":
        lines.append(
            f"🔁 {schedule['start_time']} dan {schedule['end_time']} gacha "
            f"har {schedule['interval_hours']} soatda"
        )
    lines.append(f"🏷 Tag qilinadi: {names}")
    if upcoming:
        lines.append(f"⏭ Keyingi eslatma: {ts.format_moment(upcoming)}")
    lines += [
        "",
        "<b>1-matn (muddatgacha):</b>",
        escape(text_before, quote=False),
        "",
        "<b>2-matn (muddat o'tgach):</b>",
        escape(text_after, quote=False),
        "",
        f"Muddat o'tgach xabarlar to'xtamaydi — /stop {reminder_id} bilan to'xtatasiz.",
    ]

    await message.answer("\n".join(lines), parse_mode="HTML")
    await state.clear()


def _user_key(u: dict) -> str:
    if u.get("user_id"):
        return f"id:{u['user_id']}"
    return f"un:{u['username']}"


# --- Ro'yxat va o'chirish ---------------------------------------------------


def _status_label(reminder: dict, today: datetime.date) -> str:
    if reminder["paused"]:
        return "⏸ pauza (/resume bilan yoqiladi)"
    phase, due = ts.phase_on(reminder, today)
    if due and reminder["stopped_cycle"] == due.isoformat():
        return f"⏹ {ts.format_date(due)} sikli to'xtatilgan (keyingi oy o'zi tiklanadi)"
    if phase == "before":
        return f"🟢 faol — muddatgacha ({ts.status_phrase(phase, due, today)})"
    if phase == "after":
        return f"🔴 muddat o'tgan — {ts.status_phrase(phase, due, today)}, /stop bilan to'xtatiladi"
    return "⚪️ kutilmoqda (eslatish oynasi hali boshlanmagan)"


@router.message(Command("list_reminders"))
async def cmd_list_reminders(message: Message):
    reminders = await db.get_all_reminders()
    if not reminders:
        await message.answer("Hozircha hech qanday eslatma sozlanmagan.")
        return

    now = datetime.datetime.now(TZ)
    blocks = []
    for r in reminders:
        upcoming = ts.next_send(r, now)
        lines = [
            f"<b>#{r['id']}</b> — {escape(str(r['chat_title'] or r['chat_id']), quote=False)}",
            f"📅 Muddat: har oyning {r['day_of_month']}-kuni",
            f"⏳ Eslatish: {r['lead_days']} kun oldin boshlanadi",
            f"🕐 Vaqt: {', '.join(ts.reminder_times(r))}",
        ]
        if r["mode"] == "interval":
            lines.append(
                f"🔁 {r['start_time']} dan {r['end_time']} gacha har {r['interval_hours']} soatda"
            )
        lines.append(f"🏷 Tag qilinadi: {', '.join(escape(u, quote=False) for u in r['users']) or '—'}")
        lines.append(f"📌 Holat: {_status_label(r, now.date())}")
        lines.append(f"⏭ Keyingi: {ts.format_moment(upcoming) if upcoming else '—'}")
        blocks.append("\n".join(lines))

    await message.answer(
        "\n\n".join(blocks)
        + f"\n\nVaqtlar {TZ} bo'yicha."
        + "\nBoshqarish: /stop &lt;id&gt; · /pause &lt;id&gt; · /resume &lt;id&gt; · /delete_reminder &lt;id&gt;",
        parse_mode="HTML",
    )


@router.message(Command("show_text"))
async def cmd_show_text(message: Message):
    """Eslatmaning ikkala matnini ko'rsatadi."""
    reminder_id = _parse_id(message.text)
    if reminder_id is None:
        await message.answer("Foydalanish: /show_text &lt;id&gt;", parse_mode="HTML")
        return
    reminder = await db.get_reminder(reminder_id)
    if not reminder:
        await message.answer(f"#{reminder_id} raqamli eslatma topilmadi.")
        return
    before = reminder["text_before"] or ts.DEFAULT_TEXT_BEFORE
    after = reminder["text_after"] or ts.DEFAULT_TEXT_AFTER
    await message.answer(
        f"<b>#{reminder_id} matnlari</b>\n\n"
        f"<b>1-matn (muddatgacha):</b>\n{escape(before, quote=False)}\n\n"
        f"<b>2-matn (muddat o'tgach):</b>\n{escape(after, quote=False)}",
        parse_mode="HTML",
    )


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    """Shu oylik siklni to'xtatadi — keyingi oy o'zi qaytadan boshlanadi."""
    reminder_id = _parse_id(message.text)
    if reminder_id is None:
        await message.answer(
            "Foydalanish: /stop &lt;id&gt;\n(shu oylik eslatmalar to'xtaydi, keyingi oy o'zi tiklanadi)",
            parse_mode="HTML",
        )
        return
    reminder = await db.get_reminder(reminder_id)
    if not reminder:
        await message.answer(f"#{reminder_id} raqamli eslatma topilmadi.")
        return

    today = datetime.datetime.now(TZ).date()
    phase, due = ts.phase_on(reminder, today)
    if not due:
        due = ts.upcoming_due(reminder["day_of_month"], today)
    await db.set_stopped_cycle(reminder_id, due.isoformat())

    reminder = await db.get_reminder(reminder_id)
    upcoming = ts.next_send(reminder, datetime.datetime.now(TZ))
    await message.answer(
        f"⏹ #{reminder_id}: {ts.format_date(due)} sikli to'xtatildi — bu oyda boshqa xabar ketmaydi.\n"
        f"⏭ Keyingi eslatma: {ts.format_moment(upcoming) if upcoming else '—'}\n"
        f"Fikringiz o'zgarsa: /resume {reminder_id}"
    )


@router.message(Command("pause"))
async def cmd_pause(message: Message):
    """Eslatmani butunlay to'xtatadi (keyingi oylarda ham ishlamaydi)."""
    reminder_id = _parse_id(message.text)
    if reminder_id is None:
        await message.answer(
            "Foydalanish: /pause &lt;id&gt;\n(eslatma /resume qilinmaguncha umuman ishlamaydi)",
            parse_mode="HTML",
        )
        return
    if not await db.get_reminder(reminder_id):
        await message.answer(f"#{reminder_id} raqamli eslatma topilmadi.")
        return
    await db.set_paused(reminder_id, True)
    await message.answer(
        f"⏸ #{reminder_id} pauzaga qo'yildi — keyingi oylarda ham xabar ketmaydi.\n"
        f"Qaytarish: /resume {reminder_id}"
    )


@router.message(Command("resume"))
async def cmd_resume(message: Message):
    """Pauzani ham, shu sikl to'xtatishini ham bekor qiladi."""
    reminder_id = _parse_id(message.text)
    if reminder_id is None:
        await message.answer("Foydalanish: /resume &lt;id&gt;", parse_mode="HTML")
        return
    if not await db.get_reminder(reminder_id):
        await message.answer(f"#{reminder_id} raqamli eslatma topilmadi.")
        return
    await db.resume_reminder(reminder_id)

    reminder = await db.get_reminder(reminder_id)
    upcoming = ts.next_send(reminder, datetime.datetime.now(TZ))
    await message.answer(
        f"▶️ #{reminder_id} qayta yoqildi.\n"
        f"⏭ Keyingi eslatma: {ts.format_moment(upcoming) if upcoming else '—'}"
    )


def _parse_id(text: str) -> int | None:
    parts = (text or "").split()
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return None


@router.message(Command("delete_reminder"))
async def cmd_delete_reminder(message: Message):
    reminder_id = _parse_id(message.text)
    if reminder_id is None:
        await message.answer(
            "Foydalanish: /delete_reminder &lt;id&gt;\n(ID'ni /list_reminders orqali ko'rasiz)",
            parse_mode="HTML",
        )
        return
    if await db.delete_reminder(reminder_id):
        await message.answer("O'chirildi.")
    else:
        await message.answer(f"#{reminder_id} raqamli eslatma topilmadi.")
