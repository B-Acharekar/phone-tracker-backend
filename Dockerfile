FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# Flask-SocketIO is configured for threading mode. One Gunicorn worker is
# required for Socket.IO rooms; Cloud Run handles container-level scaling.
CMD ["gunicorn", "--workers", "1", "--threads", "100", "--bind", "0.0.0.0:8080", "--timeout", "0", "app:app"]
