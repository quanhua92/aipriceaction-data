"""Data types for stock market analysis"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Literal

@dataclass
class StockDataPoint:
    """Single stock data point (OHLCV + moving averages)"""
    date: datetime
    time: str  # ISO date string (for compatibility with TS)
    open: float
    high: float
    low: float
    close: float
    volume: float
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma50: Optional[float] = None


DateRangeType = Literal["1W", "2W", "1M", "2M", "3M", "4M", "6M", "1Y", "2Y", "ALL", "CUSTOM"]


@dataclass
class DateRangeConfig:
    """Date range configuration for data fetching"""
    range: DateRangeType
    startDate: Optional[datetime] = None
    endDate: Optional[datetime] = None
