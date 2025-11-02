"""
Example script to run the trading bot on historical CSV data.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.data_feed import DataFeed
from bot.signal_engine import SignalEngine
from bot.execution_simulator import ExecutionSimulator
from bot.logger import BotLogger
from bot.scheduler import TradingScheduler
from config.config import TradingConfig


def main():
    """Run bot simulation on CSV data."""
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python run_csv_example.py <csv_file_path> [start_date] [end_date]")
        print("Example: python run_csv_example.py data/btc_1m.csv 2024-01-01 2024-01-31")
        sys.exit(1)
    
    csv_path = Path(sys.argv[1])
    
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    # Parse optional date arguments
    start_date = datetime(2024, 1, 1)
    end_date = datetime.now()
    
    if len(sys.argv) >= 3:
        try:
            start_date = datetime.fromisoformat(sys.argv[2])
        except ValueError:
            print(f"Error: Invalid start_date format: {sys.argv[2]}. Use YYYY-MM-DD")
            sys.exit(1)
    
    if len(sys.argv) >= 4:
        try:
            end_date = datetime.fromisoformat(sys.argv[3])
        except ValueError:
            print(f"Error: Invalid end_date format: {sys.argv[3]}. Use YYYY-MM-DD")
            sys.exit(1)
    
    # Load configuration
    config = TradingConfig.from_env()
    
    print("=" * 60)
    print("BTC Perp Trading Bot - CSV Simulation")
    print("=" * 60)
    print(f"CSV File: {csv_path}")
    print(f"Start Date: {start_date.date()}")
    print(f"End Date: {end_date.date()}")
    print(f"Configuration:")
    print(f"  Symbol: {config.symbol}")
    print(f"  Entry Notional: {config.entry_notional_eur} EUR")
    print(f"  Leverage: {config.leverage}x")
    print(f"  Pre-Open Window: {config.pre_open_window_min} minutes")
    print(f"  Wait After Open: {config.wait_after_open_min} minutes")
    print(f"  Log Path: {config.log_path}")
    print("=" * 60)
    print()
    
    # Initialize components
    feed = DataFeed(timezone="UTC")
    
    print("Loading candles from CSV...")
    try:
        candles = feed.load_from_csv(
            str(csv_path),
            timestamp_col="timestamp",
            open_col="open",
            high_col="high",
            low_col="low",
            close_col="close",
            volume_col="volume",
        )
        print(f"Loaded {len(candles)} candles")
        
        if candles:
            print(f"First candle: {candles[0].timestamp}")
            print(f"Last candle: {candles[-1].timestamp}")
    except Exception as e:
        print(f"Error loading CSV: {e}")
        sys.exit(1)
    
    if len(candles) == 0:
        print("Error: No candles loaded from CSV")
        sys.exit(1)
    
    # Validate feed
    is_valid, error_msg = feed.validate_feed()
    if not is_valid:
        print(f"Warning: Feed validation issue: {error_msg}")
        print("Continuing anyway...")
    
    # Initialize other components
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
    
    print("\nRunning simulation...")
    print("-" * 60)
    
    try:
        # Run simulation on historical data
        scheduler.run_on_historical_data(start_date, end_date)
        
        print("\nSimulation completed!")
        print(f"Logs written to: {config.log_path}")
        print("\nTo view logs:")
        print(f"  tail -f {config.log_path}")
        print(f"  cat {config.log_path} | jq")
        
    except Exception as e:
        logger.log_error(e)
        print(f"\nError during simulation: {e}")
        raise
    finally:
        logger.close()


if __name__ == "__main__":
    main()

