"""
Logger module for writing JSONL events.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from bot.execution_simulator import VirtualPosition
from bot.signal_engine import Range, Signal
from config.config import TradingConfig


class BotLogger:
    """Logger for trading bot events in JSONL format."""
    
    def __init__(self, config: TradingConfig):
        """
        Initialize logger.
        
        Args:
            config: Trading configuration
        """
        self.config = config
        self.log_path = Path(config.log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open file in append mode
        self.log_file = open(self.log_path, 'a')
    
    def _write_event(self, event_type: str, data: Dict[str, Any]):
        """
        Write an event to the log file.
        
        Args:
            event_type: Type of event
            data: Event data dictionary
        """
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "data": data,
        }
        
        json_line = json.dumps(event, ensure_ascii=False)
        self.log_file.write(json_line + "\n")
        self.log_file.flush()  # Ensure immediate write
    
    def log_session_start(
        self,
        ny_open_time: datetime,
        session_end_time: datetime,
    ):
        """
        Log session start event.
        
        Args:
            ny_open_time: NY open timestamp
            session_end_time: Expected session end timestamp
        """
        self._write_event("session_start", {
            "symbol": self.config.symbol,
            "ny_open_time": ny_open_time.isoformat(),
            "session_end_time": session_end_time.isoformat(),
            "config": {
                "entry_notional_eur": self.config.entry_notional_eur,
                "leverage": self.config.leverage,
                "timeframe": self.config.timeframe,
                "pre_open_window_min": self.config.pre_open_window_min,
                "wait_after_open_min": self.config.wait_after_open_min,
                "volume_lookback": self.config.volume_lookback,
                "retest_tolerance_pct": self.config.retest_tolerance_pct,
                "stop_buffer_pct": self.config.stop_buffer_pct,
                "max_trades_per_session": self.config.max_trades_per_session,
            },
        })
    
    def log_range_built(self, range_obj: Range):
        """
        Log range built event.
        
        Args:
            range_obj: Built range object
        """
        self._write_event("range_built", {
            "range_high": range_obj.high,
            "range_low": range_obj.low,
            "range_start": range_obj.start_time.isoformat(),
            "range_end": range_obj.end_time.isoformat(),
            "candle_count": range_obj.candle_count,
        })
    
    def log_signal_detected(self, signal: Signal):
        """
        Log signal detected event.
        
        Args:
            signal: Detected signal
        """
        self._write_event("signal_detected", {
            "direction": signal.direction,
            "confirmation_price": signal.confirmation_price,
            "confirmation_time": signal.confirmation_time.isoformat(),
            "range_high": signal.range_high,
            "range_low": signal.range_low,
            "breakout_timestamp": signal.breakout_candle.timestamp.isoformat(),
            "retest_timestamp": signal.retest_candle.timestamp.isoformat() if signal.retest_candle else None,
            "reasons": signal.reasons,
        })
    
    def log_open_virtual_position(self, position: VirtualPosition):
        """
        Log virtual position opened event.
        
        Args:
            position: Virtual position
        """
        self._write_event("open_virtual_position", {
            "direction": position.direction,
            "entry_price": position.entry_price,
            "entry_time": position.entry_time.isoformat(),
            "quantity_base": position.quantity_base,
            "notional": position.notional,
            "stop_price": position.stop_price,
        })
    
    def log_virtual_mark(
        self,
        current_price: float,
        position: VirtualPosition,
    ):
        """
        Log periodic mark event.
        
        Args:
            current_price: Current market price
            position: Virtual position
        """
        if position.direction == "long":
            distance_to_stop = current_price - position.stop_price
        else:  # short
            distance_to_stop = position.stop_price - current_price
        
        self._write_event("virtual_mark", {
            "current_price": current_price,
            "entry_price": position.entry_price,
            "stop_price": position.stop_price,
            "distance_to_stop": distance_to_stop,
            "distance_to_stop_pct": (distance_to_stop / position.entry_price) * 100,
            "unrealized_pnl": position.notional * ((current_price - position.entry_price) / position.entry_price) if position.direction == "long" else position.notional * ((position.entry_price - current_price) / position.entry_price),
        })
    
    def log_stop_out(
        self,
        position: VirtualPosition,
        exit_price: float,
        slippage_simulated: float = 0.0,
    ):
        """
        Log stop out event.
        
        Args:
            position: Virtual position
            exit_price: Exit price
            slippage_simulated: Simulated slippage
        """
        final_exit = exit_price - slippage_simulated if position.direction == "long" else exit_price + slippage_simulated
        pnl = self._calculate_pnl(position, final_exit)
        
        self._write_event("stop_out", {
            "exit_price": exit_price,
            "final_exit_price": final_exit,
            "slippage_simulated": slippage_simulated,
            "entry_price": position.entry_price,
            "stop_price": position.stop_price,
            "direction": position.direction,
            "quantity_base": position.quantity_base,
            "notional": position.notional,
            "pnl_virtual": pnl,
        })
    
    def log_session_close(
        self,
        position: Optional[VirtualPosition],
        exit_price: float,
    ):
        """
        Log session close event.
        
        Args:
            position: Virtual position if any
            exit_price: Exit price at session close
        """
        data = {
            "exit_price": exit_price,
        }
        
        if position and position.is_open:
            pnl = self._calculate_pnl(position, exit_price)
            data.update({
                "entry_price": position.entry_price,
                "direction": position.direction,
                "quantity_base": position.quantity_base,
                "notional": position.notional,
                "pnl_virtual": pnl,
            })
        
        self._write_event("session_close", data)
    
    def log_cancel_setup(self, reason: str, details: Optional[Dict[str, Any]] = None):
        """
        Log setup cancellation.
        
        Args:
            reason: Cancellation reason
            details: Optional additional details
        """
        data = {"reason": reason}
        if details:
            data.update(details)
        
        self._write_event("cancel_setup", data)
    
    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        Log error event.
        
        Args:
            error: Exception object
            context: Optional context information
        """
        data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        
        if context:
            data.update(context)
        
        self._write_event("error", data)
    
    def _calculate_pnl(self, position: VirtualPosition, exit_price: float) -> float:
        """Helper to calculate PnL."""
        if position.direction == "long":
            pnl_base = exit_price - position.entry_price
        else:  # short
            pnl_base = position.entry_price - exit_price
        
        return pnl_base * position.quantity_base
    
    def close(self):
        """Close the log file."""
        if self.log_file:
            self.log_file.close()

