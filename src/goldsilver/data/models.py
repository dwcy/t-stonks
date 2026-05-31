from datetime import datetime

from pydantic import BaseModel, ConfigDict


GOLD = "XAU"
SILVER = "XAG"
SYMBOLS = (GOLD, SILVER)


class Tick(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    price: float
    time: datetime
    change: float
    change_percent: float
    day_high: float
    day_low: float
    prev_close: float


class Bar(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
