from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, BigInteger, CheckConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def utcnow():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="buyer", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    auctions: Mapped[list["Auction"]] = relationship(back_populates="seller")
    bids: Mapped[list["Bid"]] = relationship(back_populates="bidder")

class Auction(Base):
    __tablename__ = "auctions"
    __table_args__ = (
        CheckConstraint("starting_price_paise > 0", name="ck_auction_start_price_positive"),
        CheckConstraint("min_increment_paise > 0", name="ck_auction_increment_positive"),
        Index("ix_auctions_status_end_time", "status", "end_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    starting_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_increment_paise: Mapped[int] = mapped_column(BigInteger, default=100, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    seller: Mapped["User"] = relationship(back_populates="auctions")
    bids: Mapped[list["Bid"]] = relationship(back_populates="auction", cascade="all, delete-orphan")

class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_bid_amount_positive"),
        Index("ix_bids_auction_amount", "auction_id", "amount_paise"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False, index=True)
    bidder_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    auction: Mapped["Auction"] = relationship(back_populates="bids")
    bidder: Mapped["User"] = relationship(back_populates="bids")
