FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Chromium is pre-installed in the Playwright image

COPY src/ ./src/
COPY .env.example .env.example

ENV PYTHONPATH=/app
ENV DB_PATH=/app/data/prices.db

CMD ["python", "-m", "src.main"]
