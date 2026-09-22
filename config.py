import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env faylida BOT_TOKEN=... deb yozing.")

# Eslatma vaqtlari shu vaqt zonasi bo'yicha tushuniladi (server qayerda
# turishidan qat'i nazar — VPS odatda UTC'da bo'ladi).
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")
TZ = ZoneInfo(TIMEZONE)

# Yangi eslatma yaratilganda oldindan tanlab qo'yiladigan vaqt
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "9"))
REMINDER_MINUTE = int(os.getenv("REMINDER_MINUTE", "0"))
DEFAULT_TIME = f"{REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d}"

# Yangi eslatmada oldindan tanlab qo'yiladigan "muddatdan necha kun oldin"
DEFAULT_LEAD_DAYS = int(os.getenv("DEFAULT_LEAD_DAYS", "7"))

# Bot o'chib qolgan bo'lsa, shuncha daqiqa ichidagi o'tkazib yuborilgan
# eslatmalarni qayta ishga tushganda baribir yuboradi
CATCHUP_MINUTES = int(os.getenv("CATCHUP_MINUTES", "15"))

DB_PATH = os.getenv("DB_PATH", "bot.db")
