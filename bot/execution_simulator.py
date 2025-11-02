"""
Execution simulator module for managing virtual positions.
No real orders are sent - only virtual position tracking.
"""
from datetime import datetime
from typing import Optional, Literal
from dataclasses import dataclass

from bot.signal_engine import Signal
from config.config import TradingConfig


@dataclass
class VirtualPosition:
    """Virtual position structure."""
    direction: Literal["long", "short"]
    entry_price: float
    entry_time: datetime
    quantity_base: float
    notional: float
    stop_price: float
    is_open: bool = True


class ExecutionSimulator:
    """Simulates position execution in dry-run mode."""
    
    def __init__(self, config: TradingConfig):
        """
        Initialize execution simulator.
        
        Args:
            config: Trading configuration
        """
        self.config = config
        self.current_position: Optional[VirtualPosition] = None
    
    def calculate_position_size(self, entry_price: float) -> tuple[float, float]:
        """
        Calculate position size based on fixed notional and leverage.
        
        Args:
            entry_price: Entry price for the position
        
        Returns:
            Tuple of (quantity_base, notional_actual)
        """
        notional = self.config.entry_notional_eur * self.config.leverage
        quantity_base = notional / entry_price
        
        return quantity_base, notional
    
    def calculate_stop_price(
        self,
        direction: Literal["long", "short"],
        range_edge: float,
        buffer_pct: Optional[float] = None,
    ) -> float:
        """
        Calculate stop loss price just outside the range edge.
        
        Args:
            direction: "long" or "short"
            range_edge: Range high (for long) or low (for short)
            buffer_pct: Buffer percentage (uses config if None)
        
        Returns:
            Stop loss price
        """
        if buffer_pct is None:
            buffer_pct = self.config.stop_buffer_pct
        
        buffer = range_edge * (buffer_pct / 100.0)
        
        if direction == "long":
            # Stop just below the range high
            return range_edge - buffer
        else:  # short
            # Stop just above the range low
            return range_edge + buffer
    
    def open_virtual_position(self, signal: Signal) -> VirtualPosition:
        """
        Open a virtual position based on a validated signal.
        
        Args:
            signal: Validated trading signal
        
        Returns:
            VirtualPosition object
        """
        entry_price = signal.confirmation_price
        quantity_base, notional = self.calculate_position_size(entry_price)
        
        # Calculate stop price
        range_edge = signal.range_high if signal.direction == "long" else signal.range_low
        stop_price = self.calculate_stop_price(signal.direction, range_edge)
        
        self.current_position = VirtualPosition(
            direction=signal.direction,
            entry_price=entry_price,
            entry_time=signal.confirmation_time,
            quantity_base=quantity_base,
            notional=notional,
            stop_price=stop_price,
        )
        
        return self.current_position
    
    def check_stop_loss(self, current_price: float) -> bool:
        """
        Check if current price has hit the stop loss.
        
        Args:
            current_price: Current market price
        
        Returns:
            True if stop was hit, False otherwise
        """
        if self.current_position is None or not self.current_position.is_open:
            return False
        
        if self.current_position.direction == "long":
            return current_price <= self.current_position.stop_price
        else:  # short
            return current_price >= self.current_position.stop_price
    
    def calculate_pnl(self, exit_price: float) -> float:
        """
        Calculate PnL for the current position.
        
        Args:
            exit_price: Exit price
        
        Returns:
            PnL in EUR
        """
        if self.current_position is None:
            return 0.0
        
        if self.current_position.direction == "long":
            pnl_base = exit_price - self.current_position.entry_price
        else:  # short
            pnl_base = self.current_position.entry_price - exit_price
        
        # PnL is proportional to quantity
        pnl = pnl_base * self.current_position.quantity_base
        
        return pnl
    
    def close_virtual_position(
        self,
        exit_price: float,
        reason: str,
        slippage_simulated: float = 0.0,
    ) -> Optional[VirtualPosition]:
        """
        Close the current virtual position.
        
        Args:
            exit_price: Exit price
            reason: Reason for closing ("stop_out" or "session_close")
            slippage_simulated: Simulated slippage (default 0)
        
        Returns:
            Closed VirtualPosition or None if no position was open
        """
        if self.current_position is None or not self.current_position.is_open:
            return None
        
        self.current_position.is_open = False
        
        # Calculate final exit price with slippage
        if self.current_position.direction == "long":
            final_exit = exit_price - slippage_simulated
        else:  # short
            final_exit = exit_price + slippage_simulated
        
        # Position is closed
        return self.current_position
    
    def has_open_position(self) -> bool:
        """Check if there is an open virtual position."""
        return self.current_position is not None and self.current_position.is_open
    
    def get_current_position(self) -> Optional[VirtualPosition]:
        """Get the current virtual position."""
        return self.current_position

