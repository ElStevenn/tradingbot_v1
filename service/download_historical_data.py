"""
Script para descargar datos históricos de Binance.
Descarga velas de 1 minuto para múltiples días.
"""
import requests
import csv
from datetime import datetime, timedelta
from pathlib import Path
import time


def download_binance_candles(symbol: str, start_date: str, end_date: str, interval: str = "1m"):
    """
    Descarga velas históricas de Binance.
    
    Args:
        symbol: Símbolo (ej: "BTCUSDT")
        start_date: Fecha inicio (YYYY-MM-DD)
        end_date: Fecha fin (YYYY-MM-DD)
        interval: Intervalo de velas ("1m", "5m", etc.)
    
    Returns:
        Lista de velas en formato dict
    """
    base_url = "https://api.binance.com/api/v3/klines"
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    all_candles = []
    current_date = start_dt
    
    print(f"📥 Descargando datos de Binance...")
    print(f"   Símbolo: {symbol}")
    print(f"   Intervalo: {interval}")
    print(f"   Desde: {start_date} hasta {end_date}")
    print()
    
    while current_date <= end_dt:
        # Binance API limit: 1000 velas por request
        # Para 1 minuto = ~16.6 horas por request
        
        # Calcular timestamp inicio y fin
        start_timestamp = int(current_date.timestamp() * 1000)
        
        # Avanzar ~16 horas para obtener 1000 velas de 1 minuto
        next_date = current_date + timedelta(hours=16)
        if next_date > end_dt:
            next_date = end_dt + timedelta(days=1)
        
        end_timestamp = int(next_date.timestamp() * 1000)  # Binance usa ms
        
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_timestamp,
            "endTime": end_timestamp,
            "limit": 1000
        }
        
        try:
            print(f"   Descargando {current_date.strftime('%Y-%m-%d %H:%M')}...", end=" ")
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                print("sin datos")
                current_date = next_date
                continue
            
            # Convertir formato Binance a nuestro formato
            for kline in data:
                # Binance formato: [timestamp, open, high, low, close, volume, ...]
                timestamp_ms = int(kline[0])
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                
                # Solo incluir días laborables (lunes a viernes)
                if timestamp.weekday() < 5:  # 0-4 = lunes a viernes
                    all_candles.append({
                        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": kline[1],
                        "high": kline[2],
                        "low": kline[3],
                        "close": kline[4],
                        "volume": kline[5],
                    })
            
            print(f"✅ {len(data)} velas")
            current_date = next_date
            
            # Rate limiting: Binance permite 1200 requests/minuto
            time.sleep(0.1)  # Pequeña pausa entre requests
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error: {e}")
            time.sleep(1)
            continue
    
    # Eliminar duplicados y ordenar
    seen = set()
    unique_candles = []
    for candle in all_candles:
        key = candle["timestamp"]
        if key not in seen:
            seen.add(key)
            unique_candles.append(candle)
    
    unique_candles.sort(key=lambda x: x["timestamp"])
    
    print()
    print(f"✅ Total descargado: {len(unique_candles)} velas únicas")
    
    return unique_candles


def save_to_csv(candles: list, output_path: str):
    """
    Guarda velas en formato CSV.
    
    Args:
        candles: Lista de velas
        output_path: Ruta de salida
    """
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        writer.writerows(candles)
    
    print(f"💾 Datos guardados en: {output_path}")


def main():
    """Función principal."""
    import sys
    
    if len(sys.argv) < 4:
        print("Uso: python service/download_historical_data.py <symbol> <fecha_inicio> <fecha_fin> [output_file]")
        print()
        print("Ejemplos:")
        print("  python service/download_historical_data.py BTCUSDT 2024-10-01 2024-10-31")
        print("  python service/download_historical_data.py BTCUSDT 2024-09-01 2024-09-30 btc_septiembre.csv")
        print()
        print("Símbolos disponibles: BTCUSDT, ETHUSDT, etc.")
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    output_file = sys.argv[4] if len(sys.argv) >= 5 else f"{symbol.lower()}_{start_date}_{end_date}.csv"
    
    # Validar fechas
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        print("❌ Error: Formato de fecha inválido. Usa YYYY-MM-DD")
        sys.exit(1)
    
    print("=" * 80)
    print("DESCARGA DE DATOS HISTÓRICOS - BINANCE")
    print("=" * 80)
    print()
    
    # Descargar datos
    candles = download_binance_candles(symbol, start_date, end_date)
    
    if not candles:
        print("❌ No se descargaron datos")
        sys.exit(1)
    
    # Guardar
    save_to_csv(candles, output_file)
    
    print()
    print("=" * 80)
    print("✅ DESCARGA COMPLETADA")
    print("=" * 80)
    print()
    print(f"Ahora puedes analizar los datos:")
    print(f"  python service/analyze_week.py {output_file} {start_date} {end_date} 500")
    print()


if __name__ == "__main__":
    main()

