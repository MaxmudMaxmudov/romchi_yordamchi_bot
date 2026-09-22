FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite bazasi volume'ga yoziladi — redeploy'da o'chib ketmaydi.
# .env dagi DB_PATH buni bosib ketmaydi: load_dotenv() mavjud env'ni almashtirmaydi.
ENV DB_PATH=/data/bot.db \
    PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
