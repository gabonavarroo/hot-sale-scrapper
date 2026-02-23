FROM python:3.11-slim

WORKDIR /app

# Copiamos e instalamos dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el código fuente
COPY src/ ./src/
COPY .env.example .env.example

# Variables de entorno por defecto
ENV PYTHONPATH=/app
ENV DB_PATH=/app/data/prices.db

# Comando de inicio
CMD ["python", "-m", "src.main"]