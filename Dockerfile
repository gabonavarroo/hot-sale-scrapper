FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY .env.example .env.example

ENV PYTHONPATH=/app
ENV DB_PATH=/app/data/prices.db

CMD ["python", "-m", "src.main"]
