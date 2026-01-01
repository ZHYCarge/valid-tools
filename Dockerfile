FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY static /app/static

ENV DATA_DIR=/data
ENV TSA_URL=

RUN mkdir -p /data/db /data/files /data/logs

VOLUME ["/data/db", "/data/files", "/data/logs"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
