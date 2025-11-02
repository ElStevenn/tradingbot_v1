"""
Unit tests for execution simulator module.
"""
import pytest
from datetime import datetime

from bot.execution_simulator import ExecutionSimulator, VirtualPosition
from bot.signal_engine import Signal
from config.config import TradingConfig


@pytest.fixture
def config():
    """Create test configuration."""
    return TradingConfig(
        entry_notional_eur=10.0,
        leverage=50,
        stop_buffer_pct=0.05,
    )


@pytest.fixture
def simulator(config):
    """Create execution simulator instance."""
    return ExecutionSimulator(config)


def test_calculate_position_size(simulator):
    """Test position size calculation."""
    entry_price = 50000.0
    
    qty, notional = simulator.calculate_position_size(entry_price)
    
    assert qty > 0
    assert notional == simulator.config.entry_notional_eur * simulator.config.leverage
    assert abs(qty * entry_price - notional) < 0.01  # Allow small floating point error


def test_calculate_stop_price_long(simulator):
    """Test stop price calculation for long positions."""
    range_high = 50300.0
    
    stop_price = simulator.calculate_stop_price("long", range_high)
    
    assert stop_price < range_high
    assert stop_price > range_high * 0.999  # Should be very close to range high


def test_calculate_stop_price_short(simulator):
    """Test stop price calculation for short positions."""
    range_low = 50000.0
    
    stop_price = simulator.calculate_stop_price("short", range_low)
    
    assert stop_price > range_low
    assert stop_price < range_low * 1.001  # Should be very close to range low


def test_open_virtual_position(simulator):
    """Test opening a virtual position."""
    signal = Signal(
        direction="long",
        confirmation_price=50350.0,
        confirmation_time=datetime.now(),
        range_high=50300.0,
        range_low=50000.0,
        breakout_candle=None,
        retest_candle=None,
        reasons={},
    )
    
    position = simulator.open_virtual_position(signal)
    
    assert position is not None
    assert position.direction == "long"
    assert position.entry_price == 50350.0
    assert position.is_open is True
    assert position.quantity_base > 0
    assert position.notional > 0
    assert position.stop_price < position.entry_price  # Stop below entry for long


def test_check_stop_loss(simulator):
    """Test stop loss checking."""
    signal = Signal(
        direction="long",
        confirmation_price=50350.0,
        confirmation_time=datetime.now(),
        range_high=50300.0,
        range_low=50000.0,
        breakout_candle=None,
        retest_candle=None,
        reasons={},
    )
    
    position = simulator.open_virtual_position(signal)
    
    # Price above stop - should not trigger
    assert simulator.check_stop_loss(50200.0) is False
    
    # Price at stop - should trigger
    assert simulator.check_stop_loss(position.stop_price) is True
    
    # Price below stop - should trigger
    assert simulator.check_stop_loss(position.stop_price - 10.0) is True


def test_calculate_pnl_long(simulator):
    """Test PnL calculation for long position."""
    signal = Signal(
        direction="long",
        confirmation_price=50000.0,
        confirmation_time=datetime.now(),
        range_high=50300.0,
        range_low=50000.0,
        breakout_candle=None,
        retest_candle=None,
        reasons={},
    )
    
    position = simulator.open_virtual_position(signal)
    
    # Exit at higher price - should be profitable
    pnl = simulator.calculate_pnl(51000.0)
    assert pnl > 0
    
    # Exit at lower price - should be loss
    pnl = simulator.calculate_pnl(49000.0)
    assert pnl < 0


def test_calculate_pnl_short(simulator):
    """Test PnL calculation for short position."""
    signal = Signal(
        direction="short",
        confirmation_price=50000.0,
        confirmation_time=datetime.now(),
        range_high=50300.0,
        range_low=50000.0,
        breakout_candle=None,
        retest_candle=None,
        reasons={},
    )
    
    position = simulator.open_virtual_position(signal)
    
    # Exit at lower price - should be profitable
    pnl = simulator.calculate_pnl(49000.0)
    assert pnl > 0
    
    # Exit at higher price - should be loss
    pnl = simulator.calculate_pnl(51000.0)
    assert pnl < 0


def test_close_virtual_position(simulator):
    """Test closing a virtual position."""
    signal = Signal(
        direction="long",
        confirmation_price=50350.0,
        confirmation_time=datetime.now(),
        range_high=50300.0,
        range_low=50000.0,
        breakout_candle=None,
        retest_candle=None,
        reasons={},
    )
    
    position = simulator.open_virtual_position(signal)
    assert position.is_open is True
    
    closed = simulator.close_virtual_position(51000.0, "session_close")
    
    assert closed is not None
    assert closed.is_open is False
    assert simulator.has_open_position() is False

