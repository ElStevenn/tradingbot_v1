"""
Genera datos de ejemplo para la semana del 27-31 de octubre de 2024.
"""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_week_data(output_path: str, start_date: str, base_price: float = 65000.0):
    """
    Genera datos de ejemplo para una semana completa.
    
    Args:
        output_path: Ruta donde guardar el CSV
        start_date: Fecha de inicio en formato YYYY-MM-DD
        base_price: Precio base inicial
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    # Calcular hasta el viernes (6 días después para cubrir lunes-viernes)
    end_dt = start_dt + timedelta(days=6)
    
    candles = []
    current_price = base_price
    
    # Importar timezone para convertir
    import pytz
    spain_tz = pytz.timezone("Europe/Madrid")
    
    current_date = start_dt
    while current_date < end_dt:
        # Saltar sábados y domingos (si es fin de semana)
        weekday = current_date.weekday()
        if weekday >= 5:  # Sábado = 5, Domingo = 6
            current_date += timedelta(days=1)
            continue
        
        # Generar velas para el día
        # Desde las 09:00 hasta las 16:00 hora española (mercado activo)
        for hour in range(9, 17):
            for minute in range(0, 60):
                # IMPORTANTE: Velas cada minuto hasta 10:00, luego cada 15 min
                # PERO alrededor de 14:30 (apertura NY) generar cada minuto para testing
                if hour >= 10 and hour < 14:
                    # Entre 10:00 y 14:00: velas cada 15 minutos
                    if minute not in [0, 15, 30, 45]:
                        continue
                elif hour == 14:
                    # A las 14:xx: generar cada minuto (especialmente importante 14:30-14:40)
                    # Esto es crítico para la estrategia que observa los primeros 10 min después de 14:30
                    pass  # Generar todos los minutos
                elif hour >= 15:
                    # Después de 15:00: volver a cada 15 minutos
                    if minute not in [0, 15, 30, 45]:
                        continue
                
                ts = spain_tz.localize(
                    datetime.combine(current_date.date(), datetime.min.time().replace(hour=hour, minute=minute))
                )
                
                # Variar precio alrededor de current_price
                price_change = random.uniform(-200, 200)
                
                # Simular comportamiento alrededor de 14:30 (apertura NY)
                # Crear patrones más claros para que el bot pueda detectar señales
                day_of_week = current_date.weekday()
                
                if hour == 14:
                    if minute == 30:
                        # En la apertura (14:30), precio inicial
                        price_change = random.uniform(-50, 50)
                    elif minute > 30 and minute <= 40:
                        # PRIMEROS 10 MINUTOS después de 14:30 - CRÍTICO para la estrategia
                        # Crear tendencias claras aquí
                        if day_of_week == 0:  # Lunes: movimiento lateral
                            price_change = random.uniform(-30, 30)
                        elif day_of_week == 1:  # Martes: BAJADA CLARA (para LONG)
                            price_change = random.uniform(-80, -20)  # Bajada consistente
                        elif day_of_week == 2:  # Miércoles: SUBIDA CLARA (para SHORT)
                            price_change = random.uniform(20, 80)  # Subida consistente
                        elif day_of_week == 3:  # Jueves: Subida moderada
                            price_change = random.uniform(10, 60)
                        elif day_of_week == 4:  # Viernes: Volatilidad
                            price_change = random.uniform(-60, 60)
                    else:
                        # Después de 14:40, comportamiento normal
                        price_change = random.uniform(-100, 100)
                
                # Simular un salto/ruptura ocasional alrededor de 09:36 (como en datos reales)
                if hour == 9 and minute == 36:
                    # A veces hay un salto de precio grande
                    if random.random() > 0.5:
                        price_change = random.uniform(-500, 500)
                
                open_price = current_price
                close_price = current_price + price_change
                high = max(open_price, close_price) + random.uniform(0, 150)
                low = min(open_price, close_price) - random.uniform(0, 150)
                volume = random.uniform(80, 250)
                
                candles.append({
                    "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": f"{open_price:.2f}",
                    "high": f"{high:.2f}",
                    "low": f"{low:.2f}",
                    "close": f"{close_price:.2f}",
                    "volume": f"{volume:.2f}",
                })
                
                current_price = close_price
        
        current_date += timedelta(days=1)
    
    # Guardar a CSV
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        writer.writerows(candles)
    
    print(f"✅ Datos generados: {output_path}")
    print(f"   {len(candles)} velas generadas")
    print(f"   Desde: {start_date} hasta {(current_date - timedelta(days=1)).strftime('%Y-%m-%d')}")
    print(f"   Fechas incluidas: {len(set(c['timestamp'][:10] for c in candles))} días")
    
    return output_path


def main():
    """Función principal."""
    import sys
    
    output_path = "october_2024_data.csv"
    start_date = "2024-10-27"
    
    if len(sys.argv) >= 2:
        output_path = sys.argv[1]
    
    if len(sys.argv) >= 3:
        start_date = sys.argv[2]
    
    print("=" * 80)
    print("GENERADOR DE DATOS - SEMANA DEL 27-31 OCTUBRE 2024")
    print("=" * 80)
    print()
    
    generate_week_data(output_path, start_date)
    
    print()
    print("=" * 80)
    print("✅ Datos listos para analizar")
    print("=" * 80)
    print()
    print("Ahora puedes analizar la semana:")
    print(f"  python service/analyze_week.py {output_path} 2024-10-27 2024-10-31")


if __name__ == "__main__":
    main()

