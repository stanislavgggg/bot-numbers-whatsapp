FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# On Render: attach a Disk mounted at /var/data and set DB_PATH=/var/data/leads.db (see render.yaml)
CMD ["python", "bot.py"]
