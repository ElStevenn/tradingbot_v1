"""
Configuration management for the BTC perp trading bot.
All parameters are overridable via environment variables or config file.
"""
import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class TradingConfig:
    """Trading bot configuration with default values."""
    
    # Symbol and market
    symbol: str = "BTC/USDT:USDT"  # BTC perp symbol (informational only)
    
    # Position sizing (fixed, no risk management)
    entry_notional_eur: float = 10.0
    leverage: int = 50
    
    # Time settings
    timeframe: str = "1m"  # Intraday candles (default: 1 minute)
    ny_open_tz: str = "America/New_York"
    
    # Trading window
    pre_open_window_min: int = 30  # Minutes before open to build range
    wait_after_open_min: int = 5  # Minutes to wait after open before evaluating signals
    
    # Signal validation
    volume_lookback: int = 20  # Candles to compare for relative volume
    retest_tolerance_pct: float = 0.1  # Tolerance for valid touch on range edge (0.1%)
    stop_buffer_pct: float = 0.05  # Small margin beyond range edge for stop (0.05%)
    
    # Session limits
    max_trades_per_session: int = 3
    
    # Logging
    log_path: str = "bot_log.jsonl"
    
    @classmethod
    def from_env(cls) -> "TradingConfig":
        """Load configuration from environment variables."""
        return cls(
            symbol=os.getenv("SYMBOL", cls().symbol),
            entry_notional_eur=float(os.getenv("ENTRY_NOTIONAL_EUR", cls().entry_notional_eur)),
            leverage=int(os.getenv("LEVERAGE", cls().leverage)),
            timeframe=os.getenv("TIMEFRAME", cls().timeframe),
            ny_open_tz=os.getenv("NY_OPEN_TZ", cls().ny_open_tz),
            pre_open_window_min=int(os.getenv("PRE_OPEN_WINDOW_MIN", cls().pre_open_window_min)),
            wait_after_open_min=int(os.getenv("WAIT_AFTER_OPEN_MIN", cls().wait_after_open_min)),
            volume_lookback=int(os.getenv("VOLUME_LOOKBACK", cls().volume_lookback)),
            retest_tolerance_pct=float(os.getenv("RETEST_TOLERANCE_PCT", cls().retest_tolerance_pct)),
            stop_buffer_pct=float(os.getenv("STOP_BUFFER_PCT", cls().stop_buffer_pct)),
            max_trades_per_session=int(os.getenv("MAX_TRADES_PER_SESSION", cls().max_trades_per_session)),
            log_path=os.getenv("LOG_PATH", cls().log_path),
        )
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "TradingConfig":
        """Load configuration from a dictionary."""
        # Use defaults and override with provided values
        defaults = cls()
        return cls(
            symbol=config_dict.get("symbol", defaults.symbol),
            entry_notional_eur=config_dict.get("entry_notional_eur", defaults.entry_notional_eur),
            leverage=config_dict.get("leverage", defaults.leverage),
            timeframe=config_dict.get("timeframe", defaults.timeframe),
            ny_open_tz=config_dict.get("ny_open_tz", defaults.ny_open_tz),
            pre_open_window_min=config_dict.get("pre_open_window_min", defaults.pre_open_window_min),
            wait_after_open_min=config_dict.get("wait_after_open_min", defaults.wait_after_open_min),
            volume_lookback=config_dict.get("volume_lookback", defaults.volume_lookback),
            retest_tolerance_pct=config_dict.get("retest_tolerance_pct", defaults.retest_tolerance_pct),
            stop_buffer_pct=config_dict.get("stop_buffer_pct", defaults.stop_buffer_pct),
            max_trades_per_session=config_dict.get("max_trades_per_session", defaults.max_trades_per_session),
            log_path=config_dict.get("log_path", defaults.log_path),
        )

