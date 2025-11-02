"""
Signal engine module for building ranges, detecting breakouts,
validating retests, and confirming volume.
"""
from datetime import datetime, timedelta
from typing import Optional, Literal
from dataclasses import dataclass

from bot.data_feed import Candle, DataFeed
from config.config import TradingConfig


@dataclass
class Range:
    """Trading range structure."""
    high: float
    low: float
    start_time: datetime
    end_time: datetime
    candle_count: int


@dataclass
class Signal:
    """Trading signal structure."""
    direction: Literal["long", "short"]
    confirmation_price: float
    confirmation_time: datetime
    range_high: float
    range_low: float
    breakout_candle: Candle
    retest_candle: Optional[Candle]
    reasons: dict  # Dictionary of validation reasons


class SignalEngine:
    """Engine for detecting and validating trading signals."""
    
    def __init__(self, config: TradingConfig):
        """
        Initialize signal engine.
        
        Args:
            config: Trading configuration
        """
        self.config = config
        self.current_range: Optional[Range] = None
    
    def build_pre_open_range(
        self,
        feed: DataFeed,
        ny_open_time: datetime,
    ) -> Optional[Range]:
        """
        Build the pre-open trading range.
        
        Args:
            feed: Data feed instance
            ny_open_time: NY open timestamp
        
        Returns:
            Range object or None if insufficient data
        """
        # Calculate range window
        range_end = ny_open_time
        range_start = range_end - timedelta(minutes=self.config.pre_open_window_min)
        
        # Get candles in the range window
        candles = feed.get_candles_in_range(range_start, range_end)
        
        if len(candles) < 3:
            return None  # Insufficient data
        
        # Extract high and low
        high = max(c.high for c in candles)
        low = min(c.low for c in candles)
        
        self.current_range = Range(
            high=high,
            low=low,
            start_time=range_start,
            end_time=range_end,
            candle_count=len(candles),
        )
        
        return self.current_range
    
    def calculate_relative_volume(
        self,
        candle: Candle,
        feed: DataFeed,
        lookback: Optional[int] = None,
    ) -> float:
        """
        Calculate relative volume compared to recent average.
        
        Args:
            candle: Current candle
            feed: Data feed instance
            lookback: Number of candles to look back (uses config if None)
        
        Returns:
            Relative volume ratio (current / average)
        """
        if lookback is None:
            lookback = self.config.volume_lookback
        
        # Get recent candles before this one
        candles = feed.candles
        candle_index = None
        for i, c in enumerate(candles):
            if c.timestamp == candle.timestamp:
                candle_index = i
                break
        
        if candle_index is None or candle_index < lookback:
            return 1.0  # Not enough history
        
        # Calculate average volume
        recent_candles = candles[candle_index - lookback:candle_index]
        avg_volume = sum(c.volume for c in recent_candles) / len(recent_candles)
        
        if avg_volume == 0:
            return 1.0
        
        return candle.volume / avg_volume
    
    def check_retest(
        self,
        direction: Literal["long", "short"],
        candles: list[Candle],
        range_edge: float,
        tolerance_pct: Optional[float] = None,
    ) -> tuple[bool, Optional[Candle]]:
        """
        Check if price retested the range edge with tolerance.
        
        Args:
            direction: "long" or "short"
            candles: List of candles to check
            range_edge: Range high (for long) or low (for short)
            tolerance_pct: Tolerance percentage (uses config if None)
        
        Returns:
            Tuple of (is_valid_retest, retest_candle)
        """
        if tolerance_pct is None:
            tolerance_pct = self.config.retest_tolerance_pct
        
        tolerance = range_edge * (tolerance_pct / 100.0)
        
        for candle in candles:
            if direction == "long":
                # For long: price should touch near range_high and bounce
                # Check if low touched the range high area
                if range_edge - tolerance <= candle.low <= range_edge + tolerance:
                    # Check for bullish confirmation after touch
                    if candle.is_bullish() and candle.close > range_edge:
                        return True, candle
                    # Also accept if next candles show support
                    candle_idx = candles.index(candle)
                    if candle_idx + 1 < len(candles):
                        next_candle = candles[candle_idx + 1]
                        if next_candle.low >= range_edge - tolerance and next_candle.close > range_edge:
                            return True, candle
            else:  # short
                # For short: price should touch near range_low and reject
                if range_edge - tolerance <= candle.high <= range_edge + tolerance:
                    # Check for bearish confirmation after touch
                    if candle.is_bearish() and candle.close < range_edge:
                        return True, candle
                    # Also accept if next candles show resistance
                    candle_idx = candles.index(candle)
                    if candle_idx + 1 < len(candles):
                        next_candle = candles[candle_idx + 1]
                        if next_candle.high <= range_edge + tolerance and next_candle.close < range_edge:
                            return True, candle
        
        return False, None
    
    def validate_long_signal(
        self,
        feed: DataFeed,
        ny_open_time: datetime,
        wait_until: datetime,
        end_time: Optional[datetime] = None,
    ) -> Optional[Signal]:
        """
        Validate a long signal according to the strategy rules.
        
        Args:
            feed: Data feed instance
            ny_open_time: NY open timestamp
            wait_until: Timestamp to wait until before evaluating
        
        Returns:
            Signal object or None if invalid
        """
        if self.current_range is None:
            return None
        
        # Don't trade before open
        if wait_until < ny_open_time:
            return None
        
        # Get candles after the wait period
        if end_time is None:
            # Default to end of trading day if not specified
            end_time = wait_until + timedelta(hours=8)
        candles = feed.get_candles_in_range(wait_until, end_time)
        
        if len(candles) < 2:
            return None
        
        reasons = {}
        
        # Check for breakout above range high
        breakout_candle = None
        for candle in candles:
            if candle.close > self.current_range.high:
                breakout_candle = candle
                break
        
        if breakout_candle is None:
            return None
        
        reasons["breakout"] = {
            "price": breakout_candle.close,
            "range_high": self.current_range.high,
            "timestamp": breakout_candle.timestamp.isoformat(),
        }
        
        # Check for retest
        candles_after_breakout = [c for c in candles if c.timestamp > breakout_candle.timestamp]
        is_retest_valid, retest_candle = self.check_retest(
            "long",
            candles_after_breakout,
            self.current_range.high,
        )
        
        if not is_retest_valid:
            reasons["no_retest"] = "Price broke above range but did not retest"
            return None
        
        reasons["retest"] = {
            "timestamp": retest_candle.timestamp.isoformat() if retest_candle else None,
        }
        
        # Find confirmation candle (after retest)
        confirmation_candle = None
        if retest_candle:
            candles_after_retest = [c for c in candles_after_breakout if c.timestamp > retest_candle.timestamp]
            for candle in candles_after_retest:
                if candle.is_bullish() and candle.close > self.current_range.high:
                    # Check volume
                    rel_volume = self.calculate_relative_volume(candle, feed)
                    if rel_volume >= 1.2:  # Volume must be at least 20% above average
                        # Check body ratio (predominant body)
                        if candle.body_ratio() >= 0.6:  # Body should be at least 60% of range
                            confirmation_candle = candle
                            break
        
        if confirmation_candle is None:
            reasons["no_confirmation"] = "No valid confirmation candle found"
            return None
        
        reasons["volume"] = {
            "relative": self.calculate_relative_volume(confirmation_candle, feed),
        }
        
        reasons["confirmation"] = {
            "body_ratio": confirmation_candle.body_ratio(),
            "timestamp": confirmation_candle.timestamp.isoformat(),
        }
        
        return Signal(
            direction="long",
            confirmation_price=confirmation_candle.close,
            confirmation_time=confirmation_candle.timestamp,
            range_high=self.current_range.high,
            range_low=self.current_range.low,
            breakout_candle=breakout_candle,
            retest_candle=retest_candle,
            reasons=reasons,
        )
    
    def validate_short_signal(
        self,
        feed: DataFeed,
        ny_open_time: datetime,
        wait_until: datetime,
        end_time: Optional[datetime] = None,
    ) -> Optional[Signal]:
        """
        Validate a short signal according to the strategy rules.
        
        Args:
            feed: Data feed instance
            ny_open_time: NY open timestamp
            wait_until: Timestamp to wait until before evaluating
        
        Returns:
            Signal object or None if invalid
        """
        if self.current_range is None:
            return None
        
        # Don't trade before open
        if wait_until < ny_open_time:
            return None
        
        # Get candles after the wait period
        if end_time is None:
            # Default to end of trading day if not specified
            end_time = wait_until + timedelta(hours=8)
        candles = feed.get_candles_in_range(wait_until, end_time)
        
        if len(candles) < 2:
            return None
        
        reasons = {}
        
        # Check for breakout below range low
        breakout_candle = None
        for candle in candles:
            if candle.close < self.current_range.low:
                breakout_candle = candle
                break
        
        if breakout_candle is None:
            return None
        
        reasons["breakout"] = {
            "price": breakout_candle.close,
            "range_low": self.current_range.low,
            "timestamp": breakout_candle.timestamp.isoformat(),
        }
        
        # Check for retest
        candles_after_breakout = [c for c in candles if c.timestamp > breakout_candle.timestamp]
        is_retest_valid, retest_candle = self.check_retest(
            "short",
            candles_after_breakout,
            self.current_range.low,
        )
        
        if not is_retest_valid:
            reasons["no_retest"] = "Price broke below range but did not retest"
            return None
        
        reasons["retest"] = {
            "timestamp": retest_candle.timestamp.isoformat() if retest_candle else None,
        }
        
        # Find confirmation candle (after retest)
        confirmation_candle = None
        if retest_candle:
            candles_after_retest = [c for c in candles_after_breakout if c.timestamp > retest_candle.timestamp]
            for candle in candles_after_retest:
                if candle.is_bearish() and candle.close < self.current_range.low:
                    # Check volume
                    rel_volume = self.calculate_relative_volume(candle, feed)
                    if rel_volume >= 1.2:  # Volume must be at least 20% above average
                        # Check body ratio (predominant body)
                        if candle.body_ratio() >= 0.6:  # Body should be at least 60% of range
                            confirmation_candle = candle
                            break
        
        if confirmation_candle is None:
            reasons["no_confirmation"] = "No valid confirmation candle found"
            return None
        
        reasons["volume"] = {
            "relative": self.calculate_relative_volume(confirmation_candle, feed),
        }
        
        reasons["confirmation"] = {
            "body_ratio": confirmation_candle.body_ratio(),
            "timestamp": confirmation_candle.timestamp.isoformat(),
        }
        
        return Signal(
            direction="short",
            confirmation_price=confirmation_candle.close,
            confirmation_time=confirmation_candle.timestamp,
            range_high=self.current_range.high,
            range_low=self.current_range.low,
            breakout_candle=breakout_candle,
            retest_candle=retest_candle,
            reasons=reasons,
        )

