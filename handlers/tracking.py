"""
Bu handler guruhdagi HAR BIR xabarni tinglaydi (faqat guruh/superguruh turida)
va xabar yuborgan odamni "tanilgan odamlar" bazasiga yozib qo'yadi.
Shu orqali /new_reminder buyrug'ida odamni ro'yxatdan tanlash mumkin bo'ladi.

Muhim: bu odamning ISHTIROKINI o'qimaydi, faqat kim ekanini (user_id, username,
ism) eslab qoladi — xabar matni saqlanmaydi.
"""
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated

import database as db

router = Router()


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def track_group_message(message: Message):
    await db.upsert_group(message.chat.id, message.chat.title or str(message.chat.id))
    if message.from_user and not message.from_user.is_bot:
        await db.upsert_known_user(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )


@router.my_chat_member()
async def on_bot_added_to_group(event: ChatMemberUpdated):
    """Bot guruhga qo'shilganda, guruhni darrov ro'yxatga yozib qo'yamiz."""
    if event.chat.type in ("group", "supergroup"):
        new_status = event.new_chat_member.status
        if new_status in ("member", "administrator"):
            await db.upsert_group(event.chat.id, event.chat.title or str(event.chat.id))
