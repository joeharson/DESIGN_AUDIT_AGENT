FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

COPY . .

RUN mkdir -p output output/baselines output/scans

EXPOSE 8001 8501

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8001", "--loop", "asyncio"]
