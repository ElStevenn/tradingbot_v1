"""
Generate a sample CSV file for testing the trading bot.
Creates realistic OHLCV data around NY market open.
"""
import csv
from datetime import datetime, timedelta
import random


def generate_sample_csv(output_path: str, days: int = 5, base_price: float = 50000.0):
    """
    Generate a sample CSV file with OHLCV data.
    
    Args:
        output_path: Path to output CSV file
        days: Number of days to generate
        base_price: Starting price for BTC
    """
    # NY market open is 9:30 AM ET
    base_date = datetime(2024, 1, 15, 9, 0, 0)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        
        current_price = base_price
        
        for day in range(days):
            date = base_date + timedelta(days=day)
            
            # Generate candles for the day
            # Pre-market (9:00 - 9:30): Range building
            for minute in range(30):
                ts = date.replace(minute=minute)
                
                # Small movements in range
                price_change = random.uniform(-50, 50)
                open_price = current_price
                close_price = current_price + price_change
                high = max(open_price, close_price) + random.uniform(0, 100)
                low = min(open_price, close_price) - random.uniform(0, 100)
                volume = random.uniform(80, 120)
                
                writer.writerow({
                    'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': f"{open_price:.2f}",
                    'high': f"{high:.2f}",
                    'low': f"{low:.2f}",
                    'close': f"{close_price:.2f}",
                    'volume': f"{volume:.2f}",
                })
                
                current_price = close_price
            
            # NY Open: 9:30
            ny_open_time = date.replace(hour=9, minute=30)
            
            # Define range from pre-market
            range_low = current_price - 200
            range_high = current_price + 200
            
            # Post-open: Potential breakout scenarios
            for minute in range(30, 60):
                ts = date.replace(minute=minute)
                
                # Sometimes breakout occurs
                if minute == 36:  # Breakout at 9:36
                    # Breakout above range
                    current_price = range_high + 50
                    open_price = range_high - 10
                    close_price = current_price
                    high = current_price + random.uniform(0, 50)
                    low = open_price - random.uniform(0, 20)
                    volume = random.uniform(180, 250)  # Higher volume
                elif minute == 38:  # Retest
                    # Retest of range high
                    current_price = range_high - 5
                    open_price = range_high + 10
                    close_price = current_price
                    high = range_high + 10
                    low = range_high - 15
                    volume = random.uniform(120, 180)
                elif minute == 39:  # Confirmation
                    # Bullish confirmation
                    current_price = range_high + 80
                    open_price = range_high + 10
                    close_price = current_price
                    high = current_price + random.uniform(0, 30)
                    low = open_price - random.uniform(0, 10)
                    volume = random.uniform(200, 300)  # High volume
                else:
                    # Normal movement
                    price_change = random.uniform(-30, 30)
                    open_price = current_price
                    close_price = current_price + price_change
                    high = max(open_price, close_price) + random.uniform(0, 50)
                    low = min(open_price, close_price) - random.uniform(0, 50)
                    volume = random.uniform(100, 150)
                
                writer.writerow({
                    'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': f"{open_price:.2f}",
                    'high': f"{high:.2f}",
                    'low': f"{low:.2f}",
                    'close': f"{close_price:.2f}",
                    'volume': f"{volume:.2f}",
                })
                
                current_price = close_price
            
            # Continue generating for rest of day (simplified)
            for hour in range(10, 16):
                for minute in [0, 15, 30, 45]:
                    if hour == 16 and minute > 0:
                        break
                    
                    ts = date.replace(hour=hour, minute=minute)
                    
                    price_change = random.uniform(-100, 100)
                    open_price = current_price
                    close_price = current_price + price_change
                    high = max(open_price, close_price) + random.uniform(0, 80)
                    low = min(open_price, close_price) - random.uniform(0, 80)
                    volume = random.uniform(80, 120)
                    
                    writer.writerow({
                        'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                        'open': f"{open_price:.2f}",
                        'high': f"{high:.2f}",
                        'low': f"{low:.2f}",
                        'close': f"{close_price:.2f}",
                        'volume': f"{volume:.2f}",
                    })
                    
                    current_price = close_price
    
    print(f"Generated sample CSV with {days} days of data: {output_path}")


if __name__ == "__main__":
    import sys
    
    output_path = "sample_btc_data.csv"
    days = 5
    
    if len(sys.argv) >= 2:
        output_path = sys.argv[1]
    
    if len(sys.argv) >= 3:
        days = int(sys.argv[2])
    
    generate_sample_csv(output_path, days)
    print(f"\nUsage:")
    print(f"  python examples/run_csv_example.py {output_path}")

