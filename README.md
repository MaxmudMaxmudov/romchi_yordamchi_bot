# To'lov eslatuvchi bot

Guruhlarda to'lov muddatidan bir necha kun oldin boshlab, belgilangan
vaqt(lar)da tanlangan odamlarni tag qilib eslatib turadigan Telegram bot.
Muddat o'tib ketsa, matn o'zgaradi va eslatma siz to'xtatguningizcha davom etadi.

## Qanday ishlaydi

1. Botni kerakli guruh(lar)ga qo'shasan.
2. Guruh a'zolari xabar yozgani sayin, bot ularni "tanilgan odamlar" sifatida eslab qoladi
   (agar odam hali yozmagan bo'lsa, keyinroq qo'lda username orqali ham qo'shish mumkin).
3. Botga shaxsiy (DM) xabar yozib `/new_reminder` buyrug'ini yuborasan →
   guruh → odamlar → to'lov muddati (oyning kuni) → muddatdan necha kun oldin
   boshlansin → vaqt(lar) → **1-matn** va **2-matn**.
4. Bot har daqiqada tekshirib turadi va vaqti kelgan eslatmalarni tegishli
   guruhga odamlarni tag qilib yuboradi.

### Ikki bosqich: muddatgacha va muddatdan keyin

```
Muddat 22-kun, "7 kun oldin" tanlangan bo'lsa:

  16–22-sentabr   1-matn  — har kuni, tanlangan vaqt(lar)da
  23-sentabr dan  2-matn  — har kuni, /stop bilan to'xtatilgunicha
  16-oktabr       1-matn  — yangi sikl o'zi boshlanadi
```

Ya'ni muddat o'tgach xabar **o'zi to'xtamaydi** — to'lov qilinganda siz
`/stop <id>` yuborasiz. Keyingi oy eslatma avtomatik qaytadan boshlanadi,
qayta yoqish shart emas.

Matnlar har bir eslatmaga alohida saqlanadi — demak har guruhga boshqa-boshqa
matn yozish mumkin.

### Matn ichidagi o'rin egallovchilar

| Yozasan | O'rniga qo'yiladi |
|---|---|
| `{odamlar}` | tag qilinadigan odamlar (yozmasang, matn oxiriga o'zi qo'shiladi) |
| `{muddat}` | `22-sentabr` |
| `{muddat_holati}` | `3 kun qoldi` / `bugun oxirgi kun` / `5 kun kechikdi` |
| `{kun}` | `22` |
| `{qolgan_kun}` / `{otgan_kun}` | raqam |

Matn so'ralganda "📝 Standart matnni ishlatish" tugmasi ham bor.

### Bir kunda bir necha marta eslatish

Kun tanlangandan keyin ikki rejimdan birini tanlaysan:

- **🕐 Aniq vaqtlar** — bir nechta vaqtni belgilaysan (masalan 09:00, 14:00, 19:00).
  O'sha kuni har bir vaqt uchun alohida xabar ketadi. Tayyor tugmalardan tanlash
  yoki "➕ Boshqa vaqt" orqali `HH:MM` yozish mumkin.
- **🔁 Har N soatda** — boshlanish vaqti, interval va tugash vaqtini tanlaysan
  (masalan 09:00 dan 21:00 gacha har 3 soatda → 09:00, 12:00, 15:00, 18:00, 21:00).

Kunning birinchi xabari "💰 Bugun to'lov kuni!", keyingilari
"🔁 Eslatma: bugun to'lov kuni!" deb ketadi.

### Vaqt zonasi

Barcha vaqtlar `.env` dagi `TIMEZONE` bo'yicha hisoblanadi (standart:
`Asia/Tashkent`) — server UTC'da turgan bo'lsa ham vaqt siljimaydi.

## Buyruqlar (botning shaxsiy chatida)

Shaxsiy chatda `/` bosilsa, buyruqlar menyusi o'zi chiqadi — ro'yxat
`main.py` dagi `BOT_COMMANDS` dan olinadi va bot ishga tushganda Telegram'ga
yoziladi. Guruhlarda menyu ataylab bo'sh qoldirilgan.

- `/start`, `/help` — qisqa yordam
- `/new_reminder` — yangi eslatma yaratish
- `/cancel` — yaratish oqimini yarim yo'lda bekor qilish
- `/list_reminders` — barcha eslatmalar: guruh, muddat, necha kun oldin, vaqt(lar),
  odamlar, holat va keyingi eslatma sanasi
- `/show_text <id>` — eslatmaning ikkala matnini ko'rish
- `/stop <id>` — **shu oylik** eslatmalarni to'xtatish (to'lov qilindi).
  Keyingi oy o'zi qaytadan boshlanadi.
- `/pause <id>` — eslatmani **butunlay** to'xtatish (keyingi oylarda ham)
- `/resume <id>` — `/stop` yoki `/pause` ni bekor qilish
- `/delete_reminder <id>` — eslatmani butunlay o'chirish

## O'rnatish (PyCharm'da)

1. Bu papkani PyCharm'da ochasan.
2. Virtual environment yarating:
   ```
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. `.env.example` faylini `.env` deb nusxalab, ichiga haqiqiy tokeningni yoz:
   ```
   cp .env.example .env
   ```
   `BOT_TOKEN` — @BotFather'dan olasan (agar hali bot yaratmagan bo'lsang, unga
   `/newbot` yuborib, tokenni ol).
4. Test uchun mahalliy ishga tushirish:
   ```
   python main.py
   ```

## Muhim: guruh sozlamasi

Bot guruhda ishlashi uchun, guruh admin sozlamalarida **Privacy Mode**'ni
o'chirish kerak (aks holda bot faqat o'ziga yo'naltirilgan xabarlarni ko'radi,
guruhdagi barcha xabarlarni emas — bu esa "tanilgan odamlar" ro'yxatini
to'ldirishga xalaqit beradi):

1. @BotFather'ga yozing → `/mybots` → botingizni tanlang
2. `Bot Settings` → `Group Privacy` → `Turn off`

## Droplet'ga avtomatik deploy (GitHub Actions + Docker)

`master`'ga push bo'lishi bilan GitHub Actions kodni tekshiradi, droplet'ga
yuklaydi, Docker image'ni qayta build qilib, botni qayta ishga tushiradi.
Workflow: [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml).

### 1. Droplet tomonida talab

- `docker` o'rnatilgan bo'lsin (root bo'lmasa: `sudo usermod -aG docker $USER`)
- `rsync` bo'lsin: `apt install -y rsync`
- Deploy foydalanuvchisining `~/.ssh/authorized_keys`'iga public kalit qo'shilgan bo'lsin

### 2. GitHub secret'lar (Settings → Secrets and variables → Actions)

| Secret | Nima | Misol |
|---|---|---|
| `SSH_HOST` | Droplet IP yoki domen | `159.89.x.x` |
| `SSH_USER` | SSH foydalanuvchi | `root` |
| `SSH_PRIVATE_KEY` | Private kalit (`-----BEGIN ...` dan `-----END ...` gacha, to'liq) | |
| `WORK_DIR` | Droplet'dagi papka (absolute yo'l) | `/opt/romchi-bot` |
| `ENV_FILE` | `.env` faylining **to'liq matni** (`.env.example` asosida) | `BOT_TOKEN=123:ABC`<br>`TIMEZONE=Asia/Tashkent` |
| `SSH_PORT` | *(ixtiyoriy)* SSH port, default `22` | `2222` |

**Diqqat:** `ENV_FILE` — serverdagi `.env` ning yagona manbasi, har deploy'da
uning ustiga yoziladi. Secret bo'sh bo'lsa workflow serverdagi `.env` ga
tegmaydi; `.env` umuman bo'lmasa deploy qizil bo'lib to'xtaydi (bot o'lik
holatda qolmaydi).

Yangi sozlama qo'shish kerak bo'lsa — faqat `ENV_FILE` secret'ini tahrirlash
kifoya, workflow'ga tegish shart emas.

### 3. Baza qayerda qoladi

SQLite `romchi-bot-data` nomli docker volume'da (`/data/bot.db`) yashaydi, ya'ni
redeploy'da o'chmaydi. Image ichida `DB_PATH=/data/bot.db` majburan qo'yilgan —
`.env` dagi `DB_PATH` buni bosib ketmaydi.

Mavjud bazani ko'chirish (bir marta):
```bash
docker cp bot.db romchi-bot:/data/bot.db && docker restart romchi-bot
```

### 4. Foydali buyruqlar (droplet'da)

```bash
docker logs -f romchi-bot      # loglar
docker restart romchi-bot      # qayta ishga tushirish
docker ps                      # holati
```

Deploy oxirida workflow 10 soniya kutib konteyner tirikligini tekshiradi —
bot ko'tarilmasa, Actions qizil bo'ladi va loglarni ko'rsatadi.

## VPS'da doimiy ishlatish (systemd bilan — Docker'siz muqobil yo'l)

VPS'ga kodni yuklab (`git clone` yoki `scp`), quyidagicha systemd service yaratish tavsiya etiladi:

```ini
# /etc/systemd/system/payment-reminder-bot.service
[Unit]
Description=Payment Reminder Telegram Bot
After=network.target

[Service]
Type=simple
User=<sening_user_ismi>
WorkingDirectory=/root/payment_reminder_bot
ExecStart=/root/payment_reminder_bot/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Keyin:
```
sudo systemctl daemon-reload
sudo systemctl enable payment-reminder-bot
sudo systemctl start payment-reminder-bot
sudo systemctl status payment-reminder-bot   # ishlayotganini tekshirish
```

Loglarni ko'rish: `journalctl -u payment-reminder-bot -f`

## Bilishing kerak bo'lgan cheklov

Telegram Bot API guruhning to'liq a'zolar ro'yxatini botga bermaydi (privacy).
Shuning uchun bot faqat guruhda **xabar yozgan** yoki **qo'lda username orqali
qo'shilgan** odamlarni "tanigan" bo'ladi. Agar kerakli odam ro'yxatda yo'q bo'lsa —
`/new_reminder` oqimidagi "➕ Qo'lda username qo'shish" tugmasidan foydalaning.

## Keyingi qadamlar (agar kerak bo'lsa)

- Standart matnlarni o'zgartirish (`timeslots.py` ichidagi `DEFAULT_TEXT_BEFORE`
  va `DEFAULT_TEXT_AFTER`)
- Mavjud eslatmaning matnini/vaqtini tahrirlash (hozircha o'chirib, qaytadan
  yaratish kerak)
- To'lov qilinganini guruhdagi tugma orqali belgilash (hozir faqat DM buyrug'i)

## Bilib qo'yish kerak bo'lgan ikki nuqta

- **Oyda muddat kuni bo'lmasa** (masalan 31-kun, fevralda) muddat o'sha oyning
  oxirgi kuniga tushadi.
- **Yaratilishdan oldingi muddat quvilmaydi.** Bugun yaratilgan eslatma o'tgan
  oyning muddati uchun "kechikdi" xabarini yubormaydi.
