"""
Script de testeo para la estrategia de trading.
Analiza datos históricos y muestra las decisiones del bot.
"""
import sys
from pathlib import Path
import csv
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from service.trading_strategy import analyze_session, format_decision_log


def load_candles_from_csv(csv_path: str) -> list:
    """
    Carga velas desde un archivo CSV.
    
    Args:
        csv_path: Ruta al archivo CSV
    
    Returns:
        Lista de diccionarios con velas OHLCV
    """
    candles = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                # Parse timestamp
                ts_str = row['timestamp'].strip()
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    except:
                        ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
                
                candles.append({
                    "timestamp": ts,
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close']),
                    "volume": float(row.get('volume', 0)),
                })
            except (KeyError, ValueError, TypeError) as e:
                continue
    
    return candles


def generate_sample_data(output_path: str = "sample_btc_data.csv", days: int = 3):
    """
    Genera datos de ejemplo para testing.
    
    Args:
        output_path: Ruta donde guardar el CSV
        days: Número de días a generar
    """
    import random
    from datetime import datetime, timedelta
    
    base_price = 50000.0
    base_date = datetime(2024, 1, 15, 13, 0, 0)  # 14:00 hora española (13:00 UTC)
    
    candles = []
    current_price = base_price
    
    for day in range(days):
        date = base_date + timedelta(days=day)
        
        # Generar velas para el día (desde 13:00 UTC hasta 16:00 UTC = 14:00-17:00 hora española)
        for hour in range(13, 17):
            for minute in range(0, 60):
                ts = date.replace(hour=hour, minute=minute, second=0)
                
                # Variar precio alrededor de current_price
                price_change = random.uniform(-100, 100)
                
                # Simular dirección alrededor de 14:30 (13:30 UTC)
                if hour == 13 and minute >= 30:
                    # Después de 14:30, simular tendencia (baja o sube)
                    if day % 2 == 0:
                        # Día par: tendencia bajista
                        price_change = random.uniform(-150, -50)
                    else:
                        # Día impar: tendencia alcista
                        price_change = random.uniform(50, 150)
                
                open_price = current_price
                close_price = current_price + price_change
                high = max(open_price, close_price) + random.uniform(0, 50)
                low = min(open_price, close_price) - random.uniform(0, 50)
                volume = random.uniform(80, 200)
                
                candles.append({
                    "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": f"{open_price:.2f}",
                    "high": f"{high:.2f}",
                    "low": f"{low:.2f}",
                    "close": f"{close_price:.2f}",
                    "volume": f"{volume:.2f}",
                })
                
                current_price = close_price
    
    # Guardar a CSV
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        writer.writerows(candles)
    
    print(f"✅ Datos de ejemplo generados: {output_path}")
    print(f"   {len(candles)} velas generadas")
    return output_path


def main():
    """Función principal."""
    csv_path = None
    
    if len(sys.argv) >= 2:
        csv_path = sys.argv[1]
    
    # Si no se proporciona archivo o no existe, generar datos de ejemplo
    if not csv_path or not Path(csv_path).exists():
        if not csv_path:
            csv_path = "sample_btc_data.csv"
        
        print("📝 No se encontró archivo CSV. Generando datos de ejemplo...")
        print()
        
        try:
            csv_path = generate_sample_data(csv_path, days=3)
        except Exception as e:
            print(f"❌ Error generando datos de ejemplo: {e}")
            print()
            print("💡 Alternativas:")
            print("   1. Descarga datos históricos de:")
            print("      - TradingView (exportar a CSV)")
            print("      - Binance (https://www.binance.com/es/markets/spot)")
            print("      - O cualquier exchange que permita descargar datos históricos")
            print("   2. El CSV debe tener estas columnas:")
            print("      timestamp,open,high,low,close,volume")
            print("   3. Formato de timestamp: 'YYYY-MM-DD HH:MM:SS'")
            sys.exit(1)
    
    print(f"📥 Cargando velas desde: {csv_path}")
    candles = load_candles_from_csv(csv_path)
    
    if not candles:
        print("❌ No se pudieron cargar velas del CSV")
        print()
        print("💡 Verifica que el CSV tenga estas columnas:")
        print("   timestamp,open,high,low,close,volume")
        sys.exit(1)
    
    print(f"✅ Cargadas {len(candles)} velas")
    print(f"   Primera vela: {candles[0]['timestamp']}")
    print(f"   Última vela: {candles[-1]['timestamp']}")
    print()
    
    print("🔍 Analizando sesión...")
    print()
    
    # Analizar sesión
    decision = analyze_session(candles)
    
    # Mostrar log formateado
    log = format_decision_log(decision)
    print(log)
    
    print()
    print("📊 Decisión en formato JSON:")
    import json
    print(json.dumps(decision, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

