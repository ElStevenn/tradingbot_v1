"""
Scheduler module for orchestrating the trading cycle.
Can run in real-time or on historical data.
"""
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, List

import pytz

from bot.data_feed import DataFeed, Candle
from bot.signal_engine import SignalEngine, Range
from bot.execution_simulator import ExecutionSimulator
from bot.logger import BotLogger
from config.config import TradingConfig


class TradingScheduler:
    """Orchestrates the trading cycle."""
    
    def __init__(
        self,
        config: TradingConfig,
        feed: DataFeed,
        signal_engine: SignalEngine,
        execution_simulator: ExecutionSimulator,
        logger: BotLogger,
    ):
        """
        Initialize scheduler.
        
        Args:
            config: Trading configuration
            feed: Data feed instance
            signal_engine: Signal engine instance
            execution_simulator: Execution simulator instance
            logger: Logger instance
        """
        self.config = config
        self.feed = feed
        self.signal_engine = signal_engine
        self.execution_simulator = execution_simulator
        self.logger = logger
        
        self.ny_tz = pytz.timezone(config.ny_open_tz)
        self.trades_today = 0
        self.session_start_time: Optional[datetime] = None
        self.session_end_time: Optional[datetime] = None
    
    def calculate_ny_open_time(self, date: datetime) -> datetime:
        """
        Calculate NY market open time for a given date (with DST).
        
        Args:
            date: Date to calculate open time for
        
        Returns:
            NY open timestamp (9:30 AM ET)
        """
        # NY market opens at 9:30 AM ET
        ny_time = self.ny_tz.localize(
            datetime.combine(date.date(), dt_time(9, 30))
        )
        return ny_time
    
    def calculate_session_end_time(self, ny_open_time: datetime) -> datetime:
        """
        Calculate session end time (end of trading day).
        
        Args:
            ny_open_time: NY open timestamp
        
        Returns:
            Session end timestamp (4:00 PM ET same day)
        """
        # NY market closes at 4:00 PM ET
        session_end = self.ny_tz.localize(
            datetime.combine(ny_open_time.date(), dt_time(16, 0))
        )
        return session_end
    
    def run_on_historical_data(
        self,
        start_date: datetime,
        end_date: datetime,
    ):
        """
        Run trading simulation on historical data.
        
        Args:
            start_date: Start date for simulation
            end_date: End date for simulation
        """
        current_date = start_date.date()
        end_date_obj = end_date.date()
        
        while current_date <= end_date_obj:
            try:
                # Calculate NY open for this date
                ny_open = self.calculate_ny_open_time(
                    self.ny_tz.localize(datetime.combine(current_date, dt_time(0, 0)))
                )
                
                # Only process if we have data after this time
                latest_candle = self.feed.get_latest_candle()
                if latest_candle and latest_candle.timestamp < ny_open:
                    current_date += timedelta(days=1)
                    continue
                
                # Run session for this day
                self.run_session(ny_open)
                
            except Exception as e:
                self.logger.log_error(e, {"date": current_date.isoformat()})
            
            current_date += timedelta(days=1)
            self.trades_today = 0  # Reset for next day
    
    def run_session(self, ny_open_time: datetime):
        """
        Run a single trading session.
        
        Args:
            ny_open_time: NY market open timestamp
        """
        # Calculate session times
        wait_until = ny_open_time + timedelta(minutes=self.config.wait_after_open_min)
        session_end = self.calculate_session_end_time(ny_open_time)
        
        self.session_start_time = ny_open_time
        self.session_end_time = session_end
        self.trades_today = 0
        
        # Log session start
        self.logger.log_session_start(ny_open_time, session_end)
        
        # Validate feed
        is_valid, error_msg = self.feed.validate_feed()
        if not is_valid:
            self.logger.log_cancel_setup("feed_unstable", {"error": error_msg})
            return
        
        # Build pre-open range
        range_obj = self.signal_engine.build_pre_open_range(self.feed, ny_open_time)
        
        if range_obj is None:
            self.logger.log_cancel_setup("insufficient_data", {
                "reason": "Not enough candles to build pre-open range",
            })
            return
        
        self.logger.log_range_built(range_obj)
        
        # Get all candles for this session
        session_candles = self.feed.get_candles_in_range(ny_open_time, session_end)
        
        if len(session_candles) < 5:
            self.logger.log_cancel_setup("insufficient_data", {
                "reason": "Not enough candles in session",
            })
            return
        
        # Wait until after the wait period
        evaluation_candles = [c for c in session_candles if c.timestamp >= wait_until]
        
        if not evaluation_candles:
            self.logger.log_cancel_setup("no_evaluation_window", {
                "reason": "No candles in evaluation window",
            })
            return
        
        # Process candles sequentially
        for candle in evaluation_candles:
            # Check if we should stop trading (max trades reached)
            if self.trades_today >= self.config.max_trades_per_session:
                break
            
            # Check if session ended
            if candle.timestamp >= session_end:
                break
            
            # If we have an open position, check for stop loss
            if self.execution_simulator.has_open_position():
                position = self.execution_simulator.get_current_position()
                if position:
                    # Log periodic mark
                    self.logger.log_virtual_mark(candle.close, position)
                    
                    # Check stop loss
                    if self.execution_simulator.check_stop_loss(candle.low if position.direction == "long" else candle.high):
                        # Stop hit
                        stop_price = position.stop_price
                        closed_position = self.execution_simulator.close_virtual_position(
                            stop_price,
                            "stop_out",
                            slippage_simulated=0.0,  # No slippage in simulation
                        )
                        if closed_position:
                            self.logger.log_stop_out(closed_position, stop_price)
                            self.trades_today += 1
                        continue
            
            # If no open position, look for signals
            if not self.execution_simulator.has_open_position():
                # Check for long signal
                long_signal = self.signal_engine.validate_long_signal(
                    self.feed,
                    ny_open_time,
                    wait_until,
                    end_time=session_end,
                )
                
                if long_signal and long_signal.confirmation_time <= candle.timestamp:
                    # Open long position
                    position = self.execution_simulator.open_virtual_position(long_signal)
                    self.logger.log_signal_detected(long_signal)
                    self.logger.log_open_virtual_position(position)
                    continue
                
                # Check for short signal
                short_signal = self.signal_engine.validate_short_signal(
                    self.feed,
                    ny_open_time,
                    wait_until,
                    end_time=session_end,
                )
                
                if short_signal and short_signal.confirmation_time <= candle.timestamp:
                    # Open short position
                    position = self.execution_simulator.open_virtual_position(short_signal)
                    self.logger.log_signal_detected(short_signal)
                    self.logger.log_open_virtual_position(position)
                    continue
        
        # Close any remaining open position at session end
        if self.execution_simulator.has_open_position():
            position = self.execution_simulator.get_current_position()
            if position:
                latest_candle = session_candles[-1] if session_candles else self.feed.get_latest_candle()
                if latest_candle:
                    exit_price = latest_candle.close
                    closed_position = self.execution_simulator.close_virtual_position(
                        exit_price,
                        "session_close",
                    )
                    if closed_position:
                        self.logger.log_session_close(closed_position, exit_price)
        
        # Log session close even if no position
        if not self.execution_simulator.has_open_position():
            latest_candle = session_candles[-1] if session_candles else self.feed.get_latest_candle()
            exit_price = latest_candle.close if latest_candle else None
            if exit_price:
                self.logger.log_session_close(None, exit_price)

