FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# On Railway: attach a Volume mounted at /data and set DB_PATH=/data/leads.db
CMD ["python", "bot.py"]
