# TradeLink API — MVP

A starter backend for timed product auctions with FastAPI, PostgreSQL, JWT authentication, and WebSocket live updates.

## Features
- Register and log in
- Seller creates auctions
- Public auction listing and details
- Authenticated users place bids
- PostgreSQL row locking protects bid validation against concurrent requests
- WebSocket broadcasts bid updates
- A background task marks expired auctions as ended
- Winner is derived from the highest valid bid

## Requirements
- Python 3.12
- PostgreSQL 14+
- `uv`

## Setup

1. Create a PostgreSQL database:

```sql
CREATE DATABASE tradelink;
```

2. Create and activate an environment:

```bash
uv python install 3.12
uv venv --python 3.12
source .venv/bin/activate
```

3. Install dependencies and configure environment:

```bash
uv pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set your PostgreSQL password and a strong `JWT_SECRET_KEY`.

4. Run the API:

```bash
uvicorn app.main:app --reload
```

5. Open `http://127.0.0.1:8000/docs`.

## Main endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET /auctions`
- `POST /auctions` (seller account required)
- `GET /auctions/{auction_id}`
- `POST /auctions/{auction_id}/bids`
- `GET /auctions/{auction_id}/bids`
- `WS /ws/auctions/{auction_id}?token=YOUR_JWT`

For login, Swagger's OAuth2 password form expects `username` and `password`; this API uses email as the username.

## Important MVP limitations
- `Base.metadata.create_all()` is used for local development. Use Alembic migrations in production.
- The background expiry task runs inside this API process. For multiple API replicas, move expiry handling to a durable worker/scheduler; the database deadline check still rejects late bids.
- WebSocket broadcasts are in-process. For multiple API replicas, use Redis Pub/Sub or PostgreSQL LISTEN/NOTIFY.
- Payment processing, image uploads, email notifications, moderation, refunds, and shipping are not implemented.
- Do not treat a winning bid as a payment. Add a payment provider and a documented payment deadline before accepting real transactions.
