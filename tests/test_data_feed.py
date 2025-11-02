"""
Unit tests for data feed module.
"""
import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import csv

from bot.data_feed import DataFeed, Candle


@pytest.fixture
def feed():
    """Create data feed instance."""
    return DataFeed(timezone="UTC")


def test_candle_body_size():
    """Test candle body size calculation."""
    candle = Candle(
        timestamp=datetime.now(),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50200.0,
        volume=100.0,
    )
    
    assert candle.body_size() == 200.0
    assert candle.is_bullish() is True
    assert candle.is_bearish() is False


def test_candle_body_ratio():
    """Test candle body ratio calculation."""
    # Candle with large body
    candle = Candle(
        timestamp=datetime.now(),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50200.0,
        volume=100.0,
    )
    
    ratio = candle.body_ratio()
    assert 0 <= ratio <= 1
    assert ratio > 0.5  # Large body


def test_add_candle(feed):
    """Test adding a candle."""
    candle = feed.add_candle(
        timestamp=datetime.now(),
        open_price=50000.0,
        high=50100.0,
        low=49900.0,
        close=50200.0,
        volume=100.0,
    )
    
    assert candle is not None
    assert len(feed.candles) == 1
    assert feed.candles[0] == candle


def test_load_from_csv(feed):
    """Test loading candles from CSV."""
    # Create temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        writer.writerow({
            'timestamp': '2024-01-15 09:00:00',
            'open': '50000',
            'high': '50100',
            'low': '49900',
            'close': '50200',
            'volume': '100',
        })
        writer.writerow({
            'timestamp': '2024-01-15 09:01:00',
            'open': '50200',
            'high': '50300',
            'low': '50100',
            'close': '50250',
            'volume': '150',
        })
        csv_path = f.name
    
    try:
        candles = feed.load_from_csv(csv_path)
        
        assert len(candles) == 2
        assert candles[0].open == 50000.0
        assert candles[1].close == 50250.0
        # Should be sorted by timestamp
        assert candles[0].timestamp < candles[1].timestamp
    finally:
        Path(csv_path).unlink()


def test_get_candles_in_range(feed):
    """Test getting candles in a time range."""
    base_time = datetime(2024, 1, 15, 9, 0, 0)
    
    for i in range(10):
        feed.add_candle(
            timestamp=base_time.replace(minute=i),
            open_price=50000.0,
            high=50100.0,
            low=49900.0,
            close=50200.0,
            volume=100.0,
        )
    
    start = base_time.replace(minute=2)
    end = base_time.replace(minute=7)
    
    candles = feed.get_candles_in_range(start, end)
    
    assert len(candles) == 5  # Minutes 2, 3, 4, 5, 6


def test_validate_feed(feed):
    """Test feed validation."""
    base_time = datetime(2024, 1, 15, 9, 0, 0)
    
    # Add valid candles
    for i in range(5):
        feed.add_candle(
            timestamp=base_time.replace(minute=i),
            open_price=50000.0,
            high=50100.0,
            low=49900.0,
            close=50200.0,
            volume=100.0,
        )
    
    is_valid, error = feed.validate_feed()
    assert is_valid is True
    assert error is None
    
    # Add invalid candle (low > high)
    feed.add_candle(
        timestamp=base_time.replace(minute=10),
        open_price=50000.0,
        high=49900.0,  # Invalid: high < low
        low=50100.0,
        close=50200.0,
        volume=100.0,
    )
    
    is_valid, error = feed.validate_feed()
    assert is_valid is False
    assert error is not None

