import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.staticfiles import StaticFiles
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import engine, SessionLocal, get_db
from app.models import Base, Auction, User, Bid
from app.routes_auth import router as auth_router
from app.routes_auctions import router as auctions_router, update_status
from app.routes_uploads import router as uploads_router, UPLOAD_DIR
from app.realtime import manager

async def expiry_worker():
    while True:
        try:
            async with SessionLocal() as db:
                now = datetime.now(timezone.utc)
                result = await db.scalars(select(Auction).where(Auction.status.in_(["scheduled", "active"]), Auction.end_time <= now))
                expired = list(result.all())
                for auction in expired:
                    auction.status = "ended"
                if expired:
                    await db.commit()
        except Exception as exc:
            print(f"Expiry worker error: {exc}")
        await asyncio.sleep(2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Convenient for local development. Use Alembic migrations in production.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    task = asyncio.create_task(expiry_worker())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    await engine.dispose()

app = FastAPI(title="TradeLink API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(auctions_router)
app.include_router(uploads_router)
app.mount("/uploads/files", StaticFiles(directory=UPLOAD_DIR), name="upload-files")

@app.get("/")
async def root():
    return {"app": "TradeLink", "status": "running", "docs": "/docs"}

@app.websocket("/ws/auctions/{auction_id}")
async def auction_socket(websocket: WebSocket, auction_id: int, token: str = Query(...)):
    # Authenticate the WebSocket connection using the same JWT as REST endpoints.
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub", ""))
    except (JWTError, ValueError, TypeError):
        await websocket.close(code=1008)
        return

    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        auction = await db.get(Auction, auction_id)
        if not user or not auction:
            await websocket.close(code=1008)
            return

    await manager.connect(auction_id, websocket)
    try:
        async with SessionLocal() as db:
            auction = await db.get(Auction, auction_id)
            highest = await db.scalar(select(Bid).where(Bid.auction_id == auction_id).order_by(Bid.amount_paise.desc(), Bid.id.desc()).limit(1))
            await websocket.send_json({
                "type": "snapshot",
                "auction_id": auction_id,
                "status": auction.status,
                "end_time": auction.end_time.isoformat(),
                "current_price_paise": highest.amount_paise if highest else auction.starting_price_paise,
                "highest_bidder_id": highest.bidder_id if highest else None,
            })
        while True:
            # Keep the connection alive; clients may send ping messages.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(auction_id, websocket)