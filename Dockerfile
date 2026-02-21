FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Camoufox browser (patched Firefox for anti-detect scraping).
# Only runs if BESTBUY_USE_CAMOUFOX=true at runtime; having it pre-downloaded
# avoids a slow first-run download inside the container.
RUN python -m camoufox fetch || true

COPY src/ ./src/
COPY .env.example .env.example

ENV PYTHONPATH=/app
ENV DB_PATH=/app/data/prices.db

CMD ["python", "-m", "src.main"]