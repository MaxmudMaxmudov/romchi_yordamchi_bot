from aiogram.fsm.state import State, StatesGroup


class NewReminder(StatesGroup):
    choosing_group = State()
    choosing_users = State()
    waiting_manual_username = State()
    choosing_day = State()
    choosing_lead = State()            # muddatdan necha kun oldin boshlansin
    choosing_mode = State()            # aniq vaqtlar / har N soatda
    choosing_times = State()           # aniq vaqtlarni belgilash
    waiting_manual_time = State()      # HH:MM ni qo'lda yozish
    choosing_interval_start = State()
    choosing_interval_hours = State()
    choosing_interval_end = State()
    waiting_text_before = State()      # 1-matn: muddat oldi
    waiting_text_after = State()       # 2-matn: muddat o'tgach
