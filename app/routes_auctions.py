from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Auction, Bid, User
from app.schemas import AuctionCreate, AuctionOut, AuctionDetail, BidCreate, BidOut
from app.security import get_current_user, require_seller
from app.realtime import manager

router = APIRouter(prefix="/auctions", tags=["Auctions"])

def now_utc():
    return datetime.now(timezone.utc)

async def update_status(auction: Auction):
    now = now_utc()
    if auction.status == "scheduled" and auction.start_time <= now < auction.end_time:
        auction.status = "active"
    if auction.status in {"scheduled", "active"} and now >= auction.end_time:
        auction.status = "ended"

@router.post("", response_model=AuctionOut, status_code=201)
async def create_auction(payload: AuctionCreate, seller: User = Depends(require_seller), db: AsyncSession = Depends(get_db)):
    now = now_utc()
    if payload.end_time <= now:
        raise HTTPException(status_code=400, detail="end_time must be in the future")
    auction = Auction(
        seller_id=seller.id, title=payload.title, description=payload.description,
        image_url=str(payload.image_url) if payload.image_url else None,
        starting_price_paise=payload.starting_price_paise,
        min_increment_paise=payload.min_increment_paise,
        start_time=payload.start_time, end_time=payload.end_time,
        status="scheduled" if payload.start_time > now else "active",
    )
    db.add(auction)
    await db.commit()
    await db.refresh(auction)
    return auction

@router.get("", response_model=list[AuctionOut])
async def list_auctions(status_filter: str | None = Query(default=None, alias="status"), limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db)):
    query = select(Auction).order_by(desc(Auction.created_at)).limit(limit).offset(offset)
    if status_filter:
        if status_filter not in {"scheduled", "active", "ended"}:
            raise HTTPException(status_code=400, detail="status must be scheduled, active, or ended")
        query = query.where(Auction.status == status_filter)
    auctions = list((await db.scalars(query)).all())
    now = now_utc()
    changed = False
    for auction in auctions:
        old = auction.status
        await update_status(auction)
        changed = changed or old != auction.status
    if changed:
        await db.commit()
    return auctions

@router.get("/{auction_id}", response_model=AuctionDetail)
async def auction_detail(auction_id: int, db: AsyncSession = Depends(get_db)):
    auction = await db.get(Auction, auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    old = auction.status
    await update_status(auction)
    if old != auction.status:
        await db.commit()
    highest = await db.scalar(select(Bid).where(Bid.auction_id == auction_id).order_by(desc(Bid.amount_paise), Bid.created_at, Bid.id).limit(1))
    count = await db.scalar(select(func.count(Bid.id)).where(Bid.auction_id == auction_id))
    return AuctionDetail(
        id=auction.id, seller_id=auction.seller_id, title=auction.title,
        description=auction.description, image_url=auction.image_url,
        starting_price_paise=auction.starting_price_paise,
        min_increment_paise=auction.min_increment_paise,
        start_time=auction.start_time, end_time=auction.end_time,
        status=auction.status, created_at=auction.created_at,
        current_price_paise=highest.amount_paise if highest else auction.starting_price_paise,
        highest_bidder_id=highest.bidder_id if highest else None,
        bid_count=count or 0,
    )

@router.get("/{auction_id}/bids", response_model=list[BidOut])
async def list_bids(auction_id: int, limit: int = Query(default=50, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    if not await db.get(Auction, auction_id):
        raise HTTPException(status_code=404, detail="Auction not found")
    query = select(Bid).where(Bid.auction_id == auction_id).order_by(desc(Bid.created_at), desc(Bid.id)).limit(limit)
    return list((await db.scalars(query)).all())

@router.post("/{auction_id}/bids", response_model=BidOut, status_code=201)
async def place_bid(auction_id: int, payload: BidCreate, bidder: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Read plain values first: after commit/rollback, ORM objects are expired
    # and touching their attributes in async code raises MissingGreenlet.
    bidder_id = bidder.id

    # A transaction is already open (get_current_user queried the user), so
    # we reuse it and commit explicitly instead of calling db.begin().
    try:
        # Serialize bids for this auction. All bid writers must lock this row first.
        auction = await db.scalar(select(Auction).where(Auction.id == auction_id).with_for_update())
        if not auction:
            raise HTTPException(status_code=404, detail="Auction not found")

        now = now_utc()
        if bidder_id == auction.seller_id:
            raise HTTPException(status_code=403, detail="Sellers cannot bid on their own auction")
        if now < auction.start_time:
            raise HTTPException(status_code=409, detail="Auction has not started")
        if now >= auction.end_time:
            auction.status = "ended"
            await db.commit()  # persist the status change before rejecting
            raise HTTPException(status_code=409, detail="Auction has ended")

        auction.status = "active"
        highest = await db.scalar(
            select(Bid).where(Bid.auction_id == auction_id)
            .order_by(desc(Bid.amount_paise), desc(Bid.id)).limit(1)
        )
        current_price = highest.amount_paise if highest else auction.starting_price_paise
        minimum = current_price + auction.min_increment_paise
        if payload.amount_paise < minimum:
            raise HTTPException(status_code=400, detail=f"Bid must be at least {minimum} paise")

        bid = Bid(auction_id=auction_id, bidder_id=bidder_id, amount_paise=payload.amount_paise)
        db.add(bid)
        await db.flush()
        bid_data = {
            "id": bid.id, "auction_id": auction_id, "bidder_id": bidder_id,
            "amount_paise": bid.amount_paise, "created_at": bid.created_at.isoformat(),
        }
        bid_id = bid.id
        await db.commit()  # releases the row lock
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    await manager.broadcast(auction_id, {"type": "bid_update", "bid": bid_data})
    return await db.get(Bid, bid_id)
