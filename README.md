# Hot Sale Scraper

Monitor MacBook Pro 14" M4 Pro prices from **Best Buy** and **Apple Refurbished**. Get email and Telegram alerts when the price drops to your target.

**Target product:** MacBook Pro 14" M4 Pro – Space Black, 24 GB RAM, 12-core CPU, 16-core GPU, 512 GB SSD

## Quick start

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:

- `BESTBUY_API_KEY` – from [developer.bestbuy.com](https://developer.bestbuy.com/) (use the **Developer API** key, not Company Keys). If the product returns 404, the fetcher will try a search fallback; the app continues with Apple Refurbished only.
- `TARGET_PRICE_USD` – e.g. 1999
- `SMTP_USER`, `SMTP_PASS` – Gmail App Password
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` – optional, for push notifications

### 2. Run with Docker (recommended)

```bash
docker compose up -d
```

The container runs 24/7 and checks prices every 30 minutes (configurable via `CHECK_INTERVAL_MINUTES`).

### 3. Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

## Deployment 24/7

### VPS (DigitalOcean, Hetzner, etc.)

1. Clone the repo on the server.
2. Create `.env` with your credentials.
3. Run `docker compose up -d`.

### Raspberry Pi

1. Install Docker and Docker Compose.
2. Clone and configure as above.
3. Run `docker compose up -d`.

### Data persistence

- SQLite database is stored in `./data/prices.db` (or `DB_PATH` from env).
- Docker Compose mounts `./data` so history survives restarts.

## Notifications

| Method   | Env vars                              |
|----------|---------------------------------------|
| Email    | `SMTP_USER`, `SMTP_PASS`, `SMTP_TO`   |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

- Gmail: use an [App Password](https://support.google.com/accounts/answer/185833), not your main password.
- Telegram: create a bot with [@BotFather](https://t.me/BotFather) and get your chat ID from [@userinfobot](https://t.me/userinfobot).

## Project structure

```
hot-sale-scrapper/
├── src/
│   ├── main.py          # Entry + scheduler
│   ├── fetchers/        # Best Buy API, Apple refurbished
│   ├── models.py        # Product, PriceRecord
│   ├── storage.py       # SQLite persistence
│   ├── comparator.py    # Threshold logic
│   └── notifiers/       # Email, Telegram
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

## License

See [LICENSE](LICENSE).
