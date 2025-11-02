"""
Main entry point for the BTC perp trading bot.
Runs in dry-run mode, generating only JSON logs.
"""
import sys
from pathlib import Path

from bot.data_feed import DataFeed
from bot.signal_engine import SignalEngine
from bot.execution_simulator import ExecutionSimulator
from bot.logger import BotLogger
from bot.scheduler import TradingScheduler
from config.config import TradingConfig


def main():
    """Main entry point."""
    # Load configuration
    config = TradingConfig.from_env()
    
    # Initialize components
    feed = DataFeed(timezone="UTC")
    signal_engine = SignalEngine(config)
    execution_simulator = ExecutionSimulator(config)
    logger = BotLogger(config)
    
    scheduler = TradingScheduler(
        config=config,
        feed=feed,
        signal_engine=signal_engine,
        execution_simulator=execution_simulator,
        logger=logger,
    )
    
    try:
        # For now, this is a placeholder - actual usage depends on data source
        # See examples/run_csv_example.py for CSV-based execution
        print("Trading bot initialized in dry-run mode.")
        print(f"Logs will be written to: {config.log_path}")
        print("\nUse the CSV example script or implement a real-time feed.")
        
    except Exception as e:
        logger.log_error(e)
        raise
    finally:
        logger.close()


if __name__ == "__main__":
    main()

