"""
Data feed module for loading and normalizing OHLCV candles.
Supports CSV files and real-time feeds.
"""
import csv
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
import pytz


@dataclass
class Candle:
    """OHLCV candle data structure."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def body_size(self) -> float:
        """Calculate absolute body size."""
        return abs(self.close - self.open)
    
    def upper_wick(self) -> float:
        """Calculate upper wick size."""
        return self.high - max(self.open, self.close)
    
    def lower_wick(self) -> float:
        """Calculate lower wick size."""
        return min(self.open, self.close) - self.low
    
    def is_bullish(self) -> bool:
        """Check if candle is bullish (close > open)."""
        return self.close > self.open
    
    def is_bearish(self) -> bool:
        """Check if candle is bearish (close < open)."""
        return self.close < self.open
    
    def body_ratio(self) -> float:
        """Calculate body to total range ratio."""
        total_range = self.high - self.low
        if total_range == 0:
            return 0.0
        return self.body_size() / total_range


class DataFeed:
    """Handles loading and normalizing OHLCV data."""
    
    def __init__(self, timezone: str = "UTC"):
        """
        Initialize data feed.
        
        Args:
            timezone: Timezone for timestamp normalization
        """
        self.timezone = pytz.timezone(timezone)
        self.candles: List[Candle] = []
    
    def load_from_csv(
        self,
        file_path: str,
        timestamp_col: str = "timestamp",
        open_col: str = "open",
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
        volume_col: str = "volume",
        timestamp_format: Optional[str] = None,
    ) -> List[Candle]:
        """
        Load candles from CSV file.
        
        Args:
            file_path: Path to CSV file
            timestamp_col: Column name for timestamp
            open_col: Column name for open price
            high_col: Column name for high price
            low_col: Column name for low price
            close_col: Column name for close price
            volume_col: Column name for volume
            timestamp_format: Optional datetime format string (auto-detect if None)
        
        Returns:
            List of normalized Candle objects
        """
        candles = []
        
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    # Parse timestamp
                    ts_str = row[timestamp_col].strip()
                    if timestamp_format:
                        ts = datetime.strptime(ts_str, timestamp_format)
                    else:
                        # Try common formats
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]:
                            try:
                                ts = datetime.strptime(ts_str, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            # Try parsing as ISO format
                            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    
                    # Make timezone aware
                    if ts.tzinfo is None:
                        ts = self.timezone.localize(ts)
                    else:
                        ts = ts.astimezone(self.timezone)
                    
                    # Parse OHLCV
                    candle = Candle(
                        timestamp=ts,
                        open=float(row[open_col]),
                        high=float(row[high_col]),
                        low=float(row[low_col]),
                        close=float(row[close_col]),
                        volume=float(row[volume_col]),
                    )
                    
                    candles.append(candle)
                    
                except (KeyError, ValueError, TypeError) as e:
                    # Skip invalid rows
                    continue
        
        # Sort by timestamp
        candles.sort(key=lambda x: x.timestamp)
        self.candles = candles
        return candles
    
    def add_candle(
        self,
        timestamp: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> Candle:
        """
        Add a single candle to the feed (for real-time usage).
        
        Args:
            timestamp: Candle timestamp
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume
        
        Returns:
            Created Candle object
        """
        # Normalize timestamp
        if timestamp.tzinfo is None:
            timestamp = self.timezone.localize(timestamp)
        else:
            timestamp = timestamp.astimezone(self.timezone)
        
        candle = Candle(
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
        
        self.candles.append(candle)
        self.candles.sort(key=lambda x: x.timestamp)
        return candle
    
    def get_candles_in_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Candle]:
        """
        Get candles within a time range.
        
        Args:
            start_time: Start timestamp (inclusive)
            end_time: End timestamp (exclusive)
        
        Returns:
            List of candles in the range
        """
        if start_time.tzinfo is None:
            start_time = self.timezone.localize(start_time)
        if end_time.tzinfo is None:
            end_time = self.timezone.localize(end_time)
        
        return [
            c for c in self.candles
            if start_time <= c.timestamp < end_time
        ]
    
    def get_latest_candle(self) -> Optional[Candle]:
        """Get the most recent candle."""
        if not self.candles:
            return None
        return self.candles[-1]
    
    def validate_feed(self, max_gap_minutes: int = 5) -> tuple[bool, Optional[str]]:
        """
        Validate feed quality: check for gaps, missing data, etc.
        
        Args:
            max_gap_minutes: Maximum allowed gap between candles in minutes
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(self.candles) < 2:
            return True, None  # Too few candles to validate
        
        # Check for gaps
        for i in range(1, len(self.candles)):
            prev = self.candles[i-1]
            curr = self.candles[i]
            
            gap_minutes = (curr.timestamp - prev.timestamp).total_seconds() / 60
            
            if gap_minutes > max_gap_minutes:
                return False, f"Feed gap detected: {gap_minutes:.1f} minutes between candles"
            
            # Check for invalid OHLCV
            if not (curr.low <= curr.open <= curr.high and
                    curr.low <= curr.close <= curr.high and
                    curr.volume >= 0):
                return False, f"Invalid OHLCV data at {curr.timestamp}"
        
        return True, None

