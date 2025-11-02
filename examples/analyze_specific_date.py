"""
Script para analizar qué hubiera hecho el bot en una fecha/hora específica.
Muestra paso a paso el análisis: rango, señales, decisiones.
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
import pytz


def analyze_specific_session(csv_path: str, target_date: str, target_time: str = "14:30"):
    """
    Analiza qué hubiera hecho el bot en una fecha/hora específica.
    
    Args:
        csv_path: Path al CSV con datos históricos
        target_date: Fecha objetivo (YYYY-MM-DD)
        target_time: Hora objetivo (HH:MM) - por defecto 14:30
    """
    # Parse target datetime (assume UTC if no timezone)
    try:
        target_dt = datetime.strptime(f"{target_date} {target_time}", "%Y-%m-%d %H:%M")
        # Make timezone aware (UTC)
        target_dt = pytz.UTC.localize(target_dt)
    except ValueError as e:
        print(f"❌ Error: Formato de fecha/hora inválido. Usa: YYYY-MM-DD HH:MM")
        print(f"   Ejemplo: 2024-01-19 14:30")
        return
    
    print("=" * 80)
    print("ANÁLISIS DE SESIÓN DE TRADING")
    print("=" * 80)
    print(f"Fecha objetivo: {target_date}")
    print(f"Hora objetivo: {target_time}")
    print(f"CSV: {csv_path}")
    print("=" * 80)
    print()
    
    # Load configuration
    config = TradingConfig.from_env()
    
    print("📊 Configuración:")
    print(f"   Símbolo: {config.symbol}")
    print(f"   Notional: {config.entry_notional_eur} EUR")
    print(f"   Leverage: {config.leverage}x")
    print(f"   Ventana pre-apertura: {config.pre_open_window_min} minutos")
    print(f"   Espera después apertura: {config.wait_after_open_min} minutos")
    print()
    
    # Load data FIRST to check date range
    print("📥 Cargando datos...")
    feed = DataFeed(timezone="UTC")
    
    try:
        candles = feed.load_from_csv(csv_path)
        print(f"✅ Cargados {len(candles)} velas")
        
        if not candles:
            print("❌ No hay velas en el CSV")
            return
        
        first_candle = candles[0].timestamp
        last_candle = candles[-1].timestamp
        print(f"   Primera vela: {first_candle.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"   Última vela: {last_candle.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print()
        
        # Check if target date is in range
        if target_dt.date() < first_candle.date():
            print(f"❌ ERROR: La fecha objetivo ({target_date}) es ANTES de los datos disponibles")
            print(f"   Los datos empiezan el {first_candle.date()}")
            print(f"   Usa una fecha entre {first_candle.date()} y {last_candle.date()}")
            return
        
        if target_dt.date() > last_candle.date():
            print(f"❌ ERROR: La fecha objetivo ({target_date}) es DESPUÉS de los datos disponibles")
            print(f"   Los datos terminan el {last_candle.date()}")
            print(f"   Usa una fecha entre {first_candle.date()} y {last_candle.date()}")
            return
        
        if target_dt > last_candle:
            print(f"⚠️  ADVERTENCIA: La hora objetivo está después de la última vela disponible")
            print(f"   Última vela: {last_candle.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Hora objetivo: {target_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
        
    except Exception as e:
        print(f"❌ Error cargando CSV: {e}")
        return
    
    # Calculate NY open for target date
    ny_tz = pytz.timezone(config.ny_open_tz)
    target_date_obj = datetime.strptime(target_date, "%Y-%m-%d")
    
    # NY market opens at 9:30 AM ET (which is 14:30 UTC in winter, 13:30 UTC in summer)
    ny_open_et = ny_tz.localize(datetime.combine(target_date_obj.date(), datetime.min.time().replace(hour=9, minute=30)))
    ny_open_utc = ny_open_et.astimezone(pytz.UTC)
    
    print("🕐 Horarios:")
    print(f"   Apertura NY (ET): {ny_open_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Apertura NY (UTC): {ny_open_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Hora objetivo (UTC): {target_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get candles around target time
    target_start = target_dt - timedelta(hours=6)  # 6 hours before (covers pre-open + session)
    target_end = target_dt + timedelta(hours=2)     # 2 hours after
    
    session_candles = feed.get_candles_in_range(target_start, target_end)
    
    if not session_candles:
        print("❌ No hay velas disponibles para la sesión objetivo")
        print()
        print("💡 Ayuda:")
        print(f"   - Necesitas datos desde al menos {target_start.strftime('%Y-%m-%d %H:%M')} hasta {target_end.strftime('%Y-%m-%d %H:%M')}")
        print(f"   - Primera vela disponible: {first_candle.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   - Última vela disponible: {last_candle.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("   Sugerencias:")
        if first_candle.date() <= target_dt.date() <= last_candle.date():
            print(f"   - Prueba con una hora anterior del mismo día")
            print(f"   - O usa: {target_dt.date()} {first_candle.strftime('%H:%M')}")
        else:
            # Suggest dates within range - find a middle date
            from datetime import timedelta
            time_diff = last_candle - first_candle
            middle_time = first_candle + timedelta(seconds=time_diff.total_seconds() / 2)
            middle_date = middle_time.date()
            print(f"   - Usa una fecha entre {first_candle.date()} y {last_candle.date()}")
            print(f"   - Ejemplo: {middle_date} 14:30")
        return
    
    print(f"📈 Velas en ventana de análisis: {len(session_candles)}")
    print()
    
    # Initialize components
    signal_engine = SignalEngine(config)
    execution_simulator = ExecutionSimulator(config)
    
    # Build range
    print("🔍 PASO 1: Construcción del rango pre-apertura")
    print("-" * 80)
    
    range_obj = signal_engine.build_pre_open_range(feed, ny_open_utc)
    
    if range_obj:
        print(f"✅ Rango construido:")
        print(f"   Rango Alto: ${range_obj.high:,.2f}")
        print(f"   Rango Bajo: ${range_obj.low:,.2f}")
        print(f"   Amplitud: ${range_obj.high - range_obj.low:,.2f}")
        print(f"   Ventana: {range_obj.start_time.strftime('%H:%M')} - {range_obj.end_time.strftime('%H:%M')}")
        print(f"   Velas usadas: {range_obj.candle_count}")
    else:
        print("❌ No se pudo construir el rango (datos insuficientes)")
        return
    
    print()
    
    # Check signals
    print("🔍 PASO 2: Análisis de señales")
    print("-" * 80)
    
    wait_until = ny_open_utc + timedelta(minutes=config.wait_after_open_min)
    session_end = ny_open_utc + timedelta(hours=6, minutes=30)  # ~4 PM ET
    
    # Get candles at target time
    target_candle = None
    for candle in session_candles:
        if candle.timestamp >= target_dt:
            target_candle = candle
            break
    
    if not target_candle:
        print(f"⚠️  No hay vela disponible exactamente a las {target_time}")
        if session_candles:
            target_candle = session_candles[-1]
            print(f"   Usando última vela disponible: {target_candle.timestamp.strftime('%H:%M')}")
    else:
        print(f"Vela objetivo: {target_candle.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   OHLC: O=${target_candle.open:,.2f} H=${target_candle.high:,.2f} L=${target_candle.low:,.2f} C=${target_candle.close:,.2f}")
        print(f"   Volumen: {target_candle.volume:,.2f}")
        print()
    
    # Analyze long signal
    print("📊 Analizando señal LONG:")
    long_signal = signal_engine.validate_long_signal(feed, ny_open_utc, wait_until, end_time=session_end)
    
    if long_signal:
        print(f"✅ SEÑAL LONG DETECTADA:")
        print(f"   Precio confirmación: ${long_signal.confirmation_price:,.2f}")
        print(f"   Tiempo: {long_signal.confirmation_time.strftime('%H:%M:%S')}")
        print(f"   Ruptura: {long_signal.reasons.get('breakout', {}).get('price', 'N/A'):,.2f}")
        print(f"   Volumen relativo: {long_signal.reasons.get('volume', {}).get('relative', 0):.2f}x")
        print()
        
        if long_signal.confirmation_time <= target_dt:
            print("✅ Esta señal se habría activado ANTES de la hora objetivo")
            position = execution_simulator.open_virtual_position(long_signal)
            print(f"   Posición virtual abierta:")
            print(f"   - Dirección: LONG")
            print(f"   - Precio entrada: ${position.entry_price:,.2f}")
            print(f"   - Cantidad: {position.quantity_base:.6f} BTC")
            print(f"   - Notional: €{position.notional:,.2f}")
            print(f"   - Stop loss: ${position.stop_price:,.2f}")
            print(f"   - Distancia al stop: ${position.entry_price - position.stop_price:,.2f}")
            
            # Check if stop was hit at target time
            if target_candle and execution_simulator.check_stop_loss(target_candle.low):
                print(f"   ⚠️  STOP HABRÍA SIDO ACTIVADO a las {target_time}")
            else:
                current_price = target_candle.close if target_candle else position.entry_price
                pnl = execution_simulator.calculate_pnl(current_price)
                print(f"   Estado a las {target_time}:")
                print(f"   - Precio actual: ${current_price:,.2f}")
                print(f"   - PnL virtual: €{pnl:,.2f}")
        else:
            print("⚠️  Señal detectada pero DESPUÉS de la hora objetivo")
    else:
        print("❌ No hay señal LONG válida")
        print("   Razones posibles:")
        # Show why signal was not valid
        # Check for breakout
        candles_after_wait = feed.get_candles_in_range(wait_until, session_end)
        broke_above = any(c.close > range_obj.high for c in candles_after_wait)
        if not broke_above:
            print("   - No hubo ruptura por encima del rango alto")
        else:
            print("   - Hubo ruptura pero falta retesteo o confirmación")
    
    print()
    
    # Analyze short signal
    print("📊 Analizando señal SHORT:")
    short_signal = signal_engine.validate_short_signal(feed, ny_open_utc, wait_until, end_time=session_end)
    
    if short_signal:
        print(f"✅ SEÑAL SHORT DETECTADA:")
        print(f"   Precio confirmación: ${short_signal.confirmation_price:,.2f}")
        print(f"   Tiempo: {short_signal.confirmation_time.strftime('%H:%M:%S')}")
        print(f"   Ruptura: {short_signal.reasons.get('breakout', {}).get('price', 'N/A'):,.2f}")
        print(f"   Volumen relativo: {short_signal.reasons.get('volume', {}).get('relative', 0):.2f}x")
        print()
        
        if short_signal.confirmation_time <= target_dt:
            print("✅ Esta señal se habría activado ANTES de la hora objetivo")
            # Close long if open, open short
            if execution_simulator.has_open_position():
                execution_simulator.close_virtual_position(
                    target_candle.close if target_candle else short_signal.confirmation_price,
                    "session_close"
                )
            position = execution_simulator.open_virtual_position(short_signal)
            print(f"   Posición virtual abierta:")
            print(f"   - Dirección: SHORT")
            print(f"   - Precio entrada: ${position.entry_price:,.2f}")
            print(f"   - Cantidad: {position.quantity_base:.6f} BTC")
            print(f"   - Notional: €{position.notional:,.2f}")
            print(f"   - Stop loss: ${position.stop_price:,.2f}")
            print(f"   - Distancia al stop: ${position.stop_price - position.entry_price:,.2f}")
            
            # Check if stop was hit at target time
            if target_candle and execution_simulator.check_stop_loss(target_candle.high):
                print(f"   ⚠️  STOP HABRÍA SIDO ACTIVADO a las {target_time}")
            else:
                current_price = target_candle.close if target_candle else position.entry_price
                pnl = execution_simulator.calculate_pnl(current_price)
                print(f"   Estado a las {target_time}:")
                print(f"   - Precio actual: ${current_price:,.2f}")
                print(f"   - PnL virtual: €{pnl:,.2f}")
        else:
            print("⚠️  Señal detectada pero DESPUÉS de la hora objetivo")
    else:
        print("❌ No hay señal SHORT válida")
        candles_after_wait = feed.get_candles_in_range(wait_until, session_end)
        broke_below = any(c.close < range_obj.low for c in candles_after_wait)
        if not broke_below:
            print("   - No hubo ruptura por debajo del rango bajo")
        else:
            print("   - Hubo ruptura pero falta retesteo o confirmación")
    
    print()
    print("=" * 80)
    print("ANÁLISIS COMPLETADO")
    print("=" * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Uso: python analyze_specific_date.py <csv_file> <fecha> [hora]")
        print("Ejemplo: python analyze_specific_date.py data.csv 2024-01-19 14:30")
        print("Ejemplo: python analyze_specific_date.py data.csv 2024-01-19")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    target_date = sys.argv[2]
    target_time = sys.argv[3] if len(sys.argv) >= 4 else "14:30"
    
    if not Path(csv_path).exists():
        print(f"❌ Error: Archivo no encontrado: {csv_path}")
        sys.exit(1)
    
    analyze_specific_session(csv_path, target_date, target_time)


if __name__ == "__main__":
    main()

