"""
Script para analizar una semana completa de trading.
Analiza cada día de la semana y genera un resumen.
"""
import sys
from pathlib import Path
import csv
from datetime import datetime, timedelta
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from service.trading_strategy import analyze_session, format_decision_log
from service.test_strategy import load_candles_from_csv


def group_candles_by_day(candles):
    """
    Agrupa las velas por día.
    
    Args:
        candles: Lista de velas
    
    Returns:
        Dict con fecha como clave y lista de velas como valor
    """
    candles_by_day = defaultdict(list)
    
    for candle in candles:
        if isinstance(candle.get("timestamp"), str):
            try:
                ts = datetime.fromisoformat(candle["timestamp"].replace('Z', '+00:00'))
            except ValueError:
                ts = datetime.strptime(candle["timestamp"], "%Y-%m-%d %H:%M:%S")
        else:
            ts = candle["timestamp"]
        
        # Obtener fecha (asumiendo hora española si no tiene timezone)
        if ts.tzinfo is None:
            import pytz
            spain_tz = pytz.timezone("Europe/Madrid")
            ts = spain_tz.localize(ts)
        
        date_key = ts.date()
        candles_by_day[date_key].append(candle)
    
    return candles_by_day


def simulate_trade_pnl(entry_price: float, entry_type: str, exit_price: float, capital_used: float, leverage: int = 50, exit_reason: str = "session_end", partial_tp_price: float = None) -> float:
    """
    Simula el PnL de una operación.
    
    Args:
        entry_price: Precio de entrada
        entry_type: "LONG" o "SHORT"
        exit_price: Precio de salida
        capital_used: Capital usado en la operación (en USDT)
        leverage: Apalancamiento (x50)
    
    Returns:
        PnL en USDT (positivo = ganancia, negativo = pérdida)
    """
    # Calcular posición size
    position_size = capital_used * leverage
    
    # Si hay Take Profit parcial, calcular PnL combinado
    if partial_tp_price and ("partial_tp" in exit_reason.lower() or exit_reason == "session_end_with_partial_tp"):
        # 50% de la posición se cerró en TP (+2.5%)
        # 50% se cerró al final de sesión
        half_position = position_size * 0.5
        
        if entry_type == "LONG":
            # TP parcial: +2.5%
            tp_pnl = (partial_tp_price - entry_price) / entry_price * half_position
            # Resto de posición
            remaining_pnl = (exit_price - entry_price) / entry_price * half_position
            pnl = tp_pnl + remaining_pnl
        else:  # SHORT
            tp_pnl = (entry_price - partial_tp_price) / entry_price * half_position
            remaining_pnl = (entry_price - exit_price) / entry_price * half_position
            pnl = tp_pnl + remaining_pnl
    else:
        # Cálculo normal sin TP parcial
        if entry_type == "LONG":
            # PnL = (exit_price - entry_price) / entry_price * position_size
            price_change_pct = (exit_price - entry_price) / entry_price
            pnl = price_change_pct * position_size
        else:  # SHORT
            # PnL = (entry_price - exit_price) / entry_price * position_size
            price_change_pct = (entry_price - exit_price) / entry_price
            pnl = price_change_pct * position_size
    
    return pnl


def simulate_session_end_price(candles: list, entry_price: float, entry_time_str: str, entry_type: str, use_tp: bool = True, use_trailing: bool = True) -> tuple:
    """
    Simula el precio de cierre al final de la sesión o cuando se alcanza el stop.
    
    Args:
        candles: Lista de velas del día
        entry_price: Precio de entrada
        entry_time_str: Timestamp de entrada (ISO string)
        entry_type: "LONG" o "SHORT"
    
    Returns:
        Tuple de (exit_price, exit_reason, exit_minute)
    """
    import pytz
    spain_tz = pytz.timezone("Europe/Madrid")
    
    # Parse entry time
    try:
        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
    except:
        entry_time = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
        entry_time = spain_tz.localize(entry_time)
    
    if entry_time.tzinfo is None:
        entry_time = spain_tz.localize(entry_time)
    
    # Encontrar velas después de la entrada
    candles_after_entry = []
    for candle in candles:
        ts_str = candle.get("timestamp", "")
        if isinstance(ts_str, str):
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except:
                try:
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                except:
                    continue
        else:
            ts = ts_str
        
        if ts.tzinfo is None:
            ts = spain_tz.localize(ts)
        
        if ts > entry_time:
            candles_after_entry.append({
                "timestamp": ts,
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
            })
    
    if not candles_after_entry:
        # No hay más velas, usar última vela del día
        if candles:
            last_candle = candles[-1]
            return float(last_candle["close"]), "session_end", 0, None
    
    # Stop loss más estricto: 2% para reducir pérdidas grandes
    # Con apalancamiento x25, una pérdida del 2% = 50% del capital usado (más manejable)
    stop_pct = 0.02
    initial_stop_price = None
    current_stop_price = None
    take_profit_price = None
    tp_activated = False
    partial_close_price = None
    
    if entry_type == "LONG":
        initial_stop_price = entry_price * (1 - stop_pct)
        current_stop_price = initial_stop_price
        # TP parcial más agresivo: solo a +2.5% (en lugar de +1%)
        if use_tp:
            take_profit_price = entry_price * 1.025  # TP en +2.5%
        
        # Buscar eventos: stop, TP parcial, trailing stop
        for candle in candles_after_entry:
            # 1. Verificar stop loss (siempre activo)
            if candle["low"] <= current_stop_price:
                exit_minute = int((candle["timestamp"] - entry_time).total_seconds() / 60)
                return current_stop_price, "stop_loss", exit_minute, None
            
            # 2. Take Profit parcial (50% de posición) - solo a +2.5%
            if use_tp and not tp_activated and candle["high"] >= take_profit_price:
                tp_activated = True
                partial_close_price = take_profit_price
                # Continuar buscando el resto de la posición
            
            # 3. Trailing stop CONSERVADOR: solo break-even si precio sube +2%
            # (más conservador para no cerrar ganancias grandes demasiado pronto)
            if use_trailing and candle["close"] >= entry_price * 1.02:
                # Mover stop a break-even (entrada) - solo protege capital, no cierra ganancias
                if current_stop_price < entry_price:
                    current_stop_price = entry_price
            
            # 4. Trailing stop avanzado: mover stop solo a +1% si precio sube +4% o más
            # (mucho más conservador para permitir ganancias grandes)
            if use_trailing and candle["close"] >= entry_price * 1.04:
                new_stop = entry_price * 1.01  # Solo asegurar +1% en ganancias grandes
                if new_stop > current_stop_price:
                    current_stop_price = new_stop
    
    else:  # SHORT
        initial_stop_price = entry_price * (1 + stop_pct)
        current_stop_price = initial_stop_price
        # TP parcial más agresivo: solo a +2.5% (precio baja 2.5%)
        if use_tp:
            take_profit_price = entry_price * 0.975  # TP en +2.5% (precio baja)
        
        # Buscar eventos: stop, TP parcial, trailing stop
        for candle in candles_after_entry:
            # 1. Verificar stop loss (siempre activo)
            if candle["high"] >= current_stop_price:
                exit_minute = int((candle["timestamp"] - entry_time).total_seconds() / 60)
                return current_stop_price, "stop_loss", exit_minute, None
            
            # 2. Take Profit parcial (50% de posición) - solo a +2.5%
            if use_tp and not tp_activated and candle["low"] <= take_profit_price:
                tp_activated = True
                partial_close_price = take_profit_price
                # Continuar buscando el resto de la posición
            
            # 3. Trailing stop CONSERVADOR: solo break-even si precio baja +2%
            if use_trailing and candle["close"] <= entry_price * 0.98:
                # Mover stop a break-even (entrada)
                if current_stop_price > entry_price:
                    current_stop_price = entry_price
            
            # 4. Trailing stop avanzado: mover stop solo a +1% si precio baja +4% o más
            if use_trailing and candle["close"] <= entry_price * 0.96:
                new_stop = entry_price * 0.99  # Solo asegurar +1% en ganancias grandes
                if new_stop < current_stop_price:
                    current_stop_price = new_stop
    
    # Si no se alcanzó el stop, cerrar al final de sesión (16:00 hora española)
    session_end = entry_time.replace(hour=16, minute=0)
    last_candle_before_end = None
    
    for candle in candles_after_entry:
        if candle["timestamp"] <= session_end:
            last_candle_before_end = candle
        else:
            break
    
    if last_candle_before_end:
        exit_minute = int((last_candle_before_end["timestamp"] - entry_time).total_seconds() / 60)
        exit_reason = "session_end"
        if tp_activated:
            # Si se activó TP parcial, calcular PnL combinado
            exit_reason = "session_end_with_partial_tp"
        return last_candle_before_end["close"], exit_reason, exit_minute, partial_close_price if tp_activated else None
    
    # Usar última vela disponible
    last_candle = candles_after_entry[-1]
    exit_minute = int((last_candle["timestamp"] - entry_time).total_seconds() / 60)
    exit_reason = "session_end"
    if tp_activated:
        exit_reason = "session_end_with_partial_tp"
    return last_candle["close"], exit_reason, exit_minute, partial_close_price if tp_activated else None


def analyze_week(csv_path: str, start_date: str = None, end_date: str = None, initial_capital: float = 500.0, leverage: int = 25):
    """
    Analiza una semana completa de trading.
    
    Args:
        csv_path: Path al CSV con datos
        start_date: Fecha inicio (YYYY-MM-DD) - si no se proporciona, usa primera fecha
        end_date: Fecha fin (YYYY-MM-DD) - si no se proporciona, usa última fecha
    """
    print("=" * 80)
    print("ANÁLISIS SEMANAL DE TRADING")
    print("=" * 80)
    print(f"CSV: {csv_path}")
    
    if start_date:
        print(f"Fecha inicio: {start_date}")
    if end_date:
        print(f"Fecha fin: {end_date}")
    print()
    
    # Cargar velas
    print("📥 Cargando datos...")
    all_candles = load_candles_from_csv(csv_path)
    
    if not all_candles:
        print("❌ No se pudieron cargar velas")
        return
    
    print(f"✅ Cargadas {len(all_candles)} velas totales")
    print()
    
    # Agrupar por día
    candles_by_day = group_candles_by_day(all_candles)
    dates = sorted(candles_by_day.keys())
    
    if not dates:
        print("❌ No se encontraron fechas en los datos")
        return
    
    # Filtrar por rango de fechas si se proporciona
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        dates = [d for d in dates if d >= start_dt]
    
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        dates = [d for d in dates if d <= end_dt]
    
    if not dates:
        print(f"❌ No hay datos en el rango especificado")
        return
    
    print(f"📅 Fechas encontradas: {len(dates)} días")
    print(f"   Desde: {dates[0]} hasta {dates[-1]}")
    print()
    
    # Simulación de capital
    current_capital = initial_capital
    trades = []
    
    # Analizar cada día
    results = []
    stats = {
        "total_days": len(dates),
        "entries_long": 0,
        "entries_short": 0,
        "no_entries": 0,
        "direction_up": 0,
        "direction_down": 0,
        "direction_lateral": 0,
    }
    
    print("🔍 Analizando cada día...")
    print()
    print("=" * 80)
    
    for date in dates:
        day_candles = candles_by_day[date]
        day_candles.sort(key=lambda x: x.get("timestamp", ""))
        
        print(f"\n📆 DÍA: {date.strftime('%A, %d de %B de %Y')}")
        print("-" * 80)
        
        # Analizar sesión del día
        decision = analyze_session(day_candles)
        results.append({
            "date": date,
            "decision": decision
        })
        
        # Mostrar resultado breve
        direction = decision["direction_detected"]
        entry_type = decision["entry_type"]
        
        if direction == "up":
            stats["direction_up"] += 1
            print(f"📈 Dirección: SUBIDA")
        elif direction == "down":
            stats["direction_down"] += 1
            print(f"📉 Dirección: BAJADA")
        else:
            stats["direction_lateral"] += 1
            print(f"➡️  Dirección: LATERAL")
        
        if entry_type == "LONG":
            stats["entries_long"] += 1
            entry_price = decision['entry_price']
            
            # Simular operación
            # Simular operación - Tamaño de posición MÁS AGRESIVO para maximizar ganancias
            base_percentage = 0.35  # 35% base (más agresivo)
            if current_capital > initial_capital * 1.1:  # Si ganamos más del 10%
                base_percentage = 0.40  # 40% cuando vamos bien
            if current_capital > initial_capital * 1.3:  # Si ganamos más del 30%
                base_percentage = 0.45  # 45% cuando vamos muy bien (muy agresivo)
            if current_capital > initial_capital * 1.5:  # Si ganamos más del 50%
                base_percentage = 0.50  # 50% cuando vamos excelente (máximo)
            
            capital_used = current_capital * base_percentage
            exit_price, exit_reason, exit_minute, partial_tp_price = simulate_session_end_price(
                day_candles, entry_price, decision['entry_timestamp'], "LONG", use_tp=True, use_trailing=True
            )
            
            pnl = simulate_trade_pnl(entry_price, "LONG", exit_price, capital_used, leverage, exit_reason, partial_tp_price)
            current_capital += pnl  # Actualizar capital
            
            trades.append({
                "date": date,
                "type": "LONG",
                "entry_price": entry_price,
                "exit_price": exit_price,
                "capital_used": capital_used,
                "pnl": pnl,
                "exit_reason": exit_reason,
                "entry_minute": decision['entry_minute'],
                "exit_minute": exit_minute,
            })
            
            pnl_symbol = "💰" if pnl >= 0 else "📉"
            print(f"✅ Entrada: LONG a ${entry_price:,.2f}")
            print(f"   Minuto: {decision['entry_minute']} después de la apertura NY")
            if decision.get('support_zone'):
                print(f"   Soporte: ${decision['support_zone']:,.2f}")
            print(f"   Capital usado: ${capital_used:,.2f} ({capital_used/initial_capital*100:.1f}% inicial)")
            print(f"   Salida: ${exit_price:,.2f} ({exit_reason})")
            print(f"   {pnl_symbol} PnL: ${pnl:,.2f} ({pnl/capital_used*100:+.2f}%)")
            print(f"   Capital después: ${current_capital:,.2f}")
            
        elif entry_type == "SHORT":
            stats["entries_short"] += 1
            entry_price = decision['entry_price']
            
            # Simular operación
            # Simular operación - Tamaño de posición MÁS AGRESIVO para maximizar ganancias
            base_percentage = 0.35  # 35% base (más agresivo)
            if current_capital > initial_capital * 1.1:  # Si ganamos más del 10%
                base_percentage = 0.40  # 40% cuando vamos bien
            if current_capital > initial_capital * 1.3:  # Si ganamos más del 30%
                base_percentage = 0.45  # 45% cuando vamos muy bien (muy agresivo)
            if current_capital > initial_capital * 1.5:  # Si ganamos más del 50%
                base_percentage = 0.50  # 50% cuando vamos excelente (máximo)
            
            capital_used = current_capital * base_percentage
            exit_price, exit_reason, exit_minute, partial_tp_price = simulate_session_end_price(
                day_candles, entry_price, decision['entry_timestamp'], "SHORT", use_tp=True, use_trailing=True
            )
            
            pnl = simulate_trade_pnl(entry_price, "SHORT", exit_price, capital_used, leverage, exit_reason, partial_tp_price)
            current_capital += pnl  # Actualizar capital
            
            trades.append({
                "date": date,
                "type": "SHORT",
                "entry_price": entry_price,
                "exit_price": exit_price,
                "capital_used": capital_used,
                "pnl": pnl,
                "exit_reason": exit_reason,
                "entry_minute": decision['entry_minute'],
                "exit_minute": exit_minute,
            })
            
            pnl_symbol = "💰" if pnl >= 0 else "📉"
            print(f"✅ Entrada: SHORT a ${entry_price:,.2f}")
            print(f"   Minuto: {decision['entry_minute']} después de la apertura NY")
            if decision.get('resistance_zone'):
                print(f"   Resistencia: ${decision['resistance_zone']:,.2f}")
            print(f"   Capital usado: ${capital_used:,.2f} ({capital_used/initial_capital*100:.1f}% inicial)")
            print(f"   Salida: ${exit_price:,.2f} ({exit_reason})")
            print(f"   {pnl_symbol} PnL: ${pnl:,.2f} ({pnl/capital_used*100:+.2f}%)")
            print(f"   Capital después: ${current_capital:,.2f}")
        else:
            stats["no_entries"] += 1
            print(f"⏸️  Sin entrada")
            if 'error' in decision.get('analysis_details', {}):
                print(f"   Razón: {decision['analysis_details']['error']}")
            elif direction == "none":
                print(f"   Razón: Movimiento lateral sin dirección clara")
            else:
                print(f"   Razón: No se detectó rebote/rechazo válido")
        
        print()
    
    # Resumen final
    print()
    print("=" * 80)
    print("📊 RESUMEN SEMANAL")
    print("=" * 80)
    print()
    print(f"Total de días analizados: {stats['total_days']}")
    print()
    print("Direcciones detectadas:")
    print(f"  📈 Subida: {stats['direction_up']} días ({stats['direction_up']/stats['total_days']*100:.1f}%)")
    print(f"  📉 Bajada: {stats['direction_down']} días ({stats['direction_down']/stats['total_days']*100:.1f}%)")
    print(f"  ➡️  Lateral: {stats['direction_lateral']} días ({stats['direction_lateral']/stats['total_days']*100:.1f}%)")
    print()
    print("Entradas detectadas:")
    print(f"  ✅ LONG: {stats['entries_long']} días ({stats['entries_long']/stats['total_days']*100:.1f}%)")
    print(f"  ✅ SHORT: {stats['entries_short']} días ({stats['entries_short']/stats['total_days']*100:.1f}%)")
    print(f"  ⏸️  Sin entrada: {stats['no_entries']} días ({stats['no_entries']/stats['total_days']*100:.1f}%)")
    print()
    
    # Simulación de capital
    print("=" * 80)
    print("💰 SIMULACIÓN DE CAPITAL")
    print("=" * 80)
    print(f"Capital inicial: ${initial_capital:,.2f} USDT")
    print(f"Apalancamiento: {leverage}x")
    print(f"Capital por operación: 35% base (dinámico hasta 50% si capital > +50%)")
    print(f"Stop loss: 2% (trailing conservador: break-even a +2%, +1% solo si precio > +4%)")
    print(f"Take Profit parcial: 50% de posición en +2.5% (más agresivo)")
    print(f"Filtros activos: Tendencia diaria, evitar SHORT en tendencias alcistas fuertes")
    print()
    
    if trades:
        total_pnl = 0
        winning_trades = 0
        losing_trades = 0
        
        print("Operaciones realizadas:")
        for i, trade in enumerate(trades, 1):
            date_str = trade['date'].strftime('%Y-%m-%d')
            pnl_symbol = "💰" if trade['pnl'] >= 0 else "📉"
            total_pnl += trade['pnl']
            
            if trade['pnl'] > 0:
                winning_trades += 1
            else:
                losing_trades += 1
            
            print(f"  {i}. {date_str} - {trade['type']}")
            print(f"     Entrada: ${trade['entry_price']:,.2f} | Salida: ${trade['exit_price']:,.2f} ({trade['exit_reason']})")
            print(f"     Capital: ${trade['capital_used']:,.2f} | {pnl_symbol} PnL: ${trade['pnl']:,.2f} ({trade['pnl']/trade['capital_used']*100:+.2f}%)")
        
        print()
        print(f"Capital final: ${current_capital:,.2f} USDT")
        print(f"Ganancia/Pérdida total: ${total_pnl:,.2f} USDT ({total_pnl/initial_capital*100:+.2f}%)")
        print(f"Operaciones ganadoras: {winning_trades} | Operaciones perdedoras: {losing_trades}")
        
        if winning_trades + losing_trades > 0:
            win_rate = (winning_trades / (winning_trades + losing_trades)) * 100
            print(f"Win Rate: {win_rate:.1f}%")
    else:
        print("No se realizaron operaciones (sin entradas detectadas)")
        print(f"Capital final: ${current_capital:,.2f} USDT (sin cambios)")
    
    print()
    print("=" * 80)
    
    # Días con entrada
    if stats['entries_long'] > 0 or stats['entries_short'] > 0:
        print("Días con entrada detectada:")
        for result in results:
            if result['decision']['entry_type'] in ['LONG', 'SHORT']:
                date_str = result['date'].strftime('%Y-%m-%d (%A)')
                entry_type = result['decision']['entry_type']
                entry_price = result['decision']['entry_price']
                entry_minute = result['decision']['entry_minute']
                print(f"  • {date_str}: {entry_type} @ ${entry_price:,.2f} (minuto {entry_minute})")
        print()
    
    print("=" * 80)
    
    return results, stats


def main():
    """Función principal."""
    if len(sys.argv) < 2:
        print("Uso: python service/analyze_week.py <archivo_csv> [fecha_inicio] [fecha_fin] [capital_inicial]")
        print()
        print("Ejemplos:")
        print("  python service/analyze_week.py sample_data.csv")
        print("  python service/analyze_week.py sample_data.csv 2024-10-27 2024-10-31")
        print("  python service/analyze_week.py sample_data.csv 2024-10-27 2024-10-31 500")
        print()
        print("Parámetros:")
        print("  capital_inicial: Capital inicial en USDT (default: 500)")
        print("  - Usa 50% del capital disponible por operación")
        print("  - Apalancamiento: 50x")
        print()
        sys.exit(1)
    
    csv_path = sys.argv[1]
    start_date = sys.argv[2] if len(sys.argv) >= 3 else None
    end_date = sys.argv[3] if len(sys.argv) >= 4 else None
    initial_capital = float(sys.argv[4]) if len(sys.argv) >= 5 else 500.0
    
    if not Path(csv_path).exists():
        print(f"❌ Error: Archivo no encontrado: {csv_path}")
        sys.exit(1)
    
    analyze_week(csv_path, start_date, end_date, initial_capital)


if __name__ == "__main__":
    main()

