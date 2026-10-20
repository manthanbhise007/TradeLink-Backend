from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, model_validator

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "buyer"

    @model_validator(mode="after")
    def valid_role(self):
        if self.role not in {"buyer", "seller"}:
            raise ValueError("role must be buyer or seller")
        return self

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    model_config = ConfigDict(from_attributes=True)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class AuctionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(default="", max_length=10000)
    image_url: HttpUrl | None = None
    starting_price_paise: int = Field(gt=0)
    min_increment_paise: int = Field(default=100, gt=0, description="₹1 = 100 paise")
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def valid_times(self):
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must include a timezone, e.g. +05:30 or Z")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self

class AuctionOut(BaseModel):
    id: int
    seller_id: int
    title: str
    description: str
    image_url: str | None
    starting_price_paise: int
    min_increment_paise: int
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BidCreate(BaseModel):
    amount_paise: int = Field(gt=0, description="Integer paise; ₹10,500 = 1050000")

class BidOut(BaseModel):
    id: int
    auction_id: int
    bidder_id: int
    amount_paise: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AuctionDetail(AuctionOut):
    current_price_paise: int
    highest_bidder_id: int | None
    bid_count: int
