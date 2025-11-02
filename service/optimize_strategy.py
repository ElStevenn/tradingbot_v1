"""
Script para optimizar los parámetros de la estrategia analizando resultados históricos.
Ajusta parámetros como umbrales de dirección, tolerancias, etc.
"""
import sys
from pathlib import Path
from itertools import product

sys.path.insert(0, str(Path(__file__).parent.parent))

from service.trading_strategy import analyze_session
from service.test_strategy import load_candles_from_csv
from service.analyze_week import group_candles_by_day, simulate_trade_pnl, simulate_session_end_price
from datetime import datetime


def test_strategy_parameters(candles_by_day: dict, params: dict):
    """
    Prueba la estrategia con diferentes parámetros.
    
    Args:
        candles_by_day: Diccionario con velas agrupadas por día
        params: Diccionario con parámetros a probar
    
    Returns:
        Dict con estadísticas de resultados
    """
    # Estos parámetros se pueden ajustar modificando analyze_session internamente
    # Por ahora, solo simulamos con capital
    initial_capital = 500.0
    leverage = 50
    current_capital = initial_capital
    trades = []
    
    for date, day_candles in sorted(candles_by_day.items()):
        day_candles.sort(key=lambda x: x.get("timestamp", ""))
        
        # Analizar sesión
        decision = analyze_session(day_candles)
        
        if decision['entry_type'] in ['LONG', 'SHORT']:
            entry_price = decision['entry_price']
            entry_type = decision['entry_type']
            
            # Simular operación
            capital_used = current_capital * 0.5
            exit_price, exit_reason, _ = simulate_session_end_price(
                day_candles, entry_price, decision['entry_timestamp'], entry_type
            )
            pnl = simulate_trade_pnl(entry_price, entry_type, exit_price, capital_used, leverage)
            current_capital += pnl
            
            trades.append({
                'entry_type': entry_type,
                'pnl': pnl,
                'win': pnl > 0,
            })
    
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'final_capital': initial_capital,
            'avg_win': 0,
            'avg_loss': 0,
        }
    
    winning_trades = [t for t in trades if t['win']]
    losing_trades = [t for t in trades if not t['win']]
    total_pnl = sum(t['pnl'] for t in trades)
    
    return {
        'total_trades': len(trades),
        'win_rate': len(winning_trades) / len(trades) * 100 if trades else 0,
        'total_pnl': total_pnl,
        'final_capital': current_capital,
        'avg_win': sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0,
        'avg_loss': sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0,
        'profit_factor': abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades and sum(t['pnl'] for t in losing_trades) != 0 else 0,
    }


def optimize_strategy(csv_path: str, start_date: str = None, end_date: str = None):
    """
    Optimiza parámetros de la estrategia analizando datos históricos.
    
    Args:
        csv_path: Path al CSV con datos
        start_date: Fecha inicio (opcional)
        end_date: Fecha fin (opcional)
    """
    print("=" * 80)
    print("OPTIMIZACIÓN DE ESTRATEGIA")
    print("=" * 80)
    print(f"CSV: {csv_path}")
    print()
    
    # Cargar datos
    from service.analyze_week import load_candles_from_csv
    all_candles = load_candles_from_csv(csv_path)
    
    if not all_candles:
        print("❌ No se pudieron cargar velas")
        return
    
    print(f"✅ Cargadas {len(all_candles)} velas")
    
    # Agrupar por día
    candles_by_day = group_candles_by_day(all_candles)
    dates = sorted(candles_by_day.keys())
    
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        dates = [d for d in dates if d >= start_dt]
    
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        dates = [d for d in dates if d <= end_dt]
    
    # Dividir en train/test (80/20)
    split_idx = int(len(dates) * 0.8)
    train_dates = dates[:split_idx]
    test_dates = dates[split_idx:]
    
    train_data = {d: candles_by_day[d] for d in train_dates}
    test_data = {d: candles_by_day[d] for d in test_dates}
    
    print(f"📊 Datos de entrenamiento: {len(train_dates)} días ({train_dates[0]} a {train_dates[-1]})")
    print(f"📊 Datos de prueba: {len(test_dates)} días ({test_dates[0]} a {test_dates[-1]})")
    print()
    
    # Analizar resultados actuales
    print("🔍 Analizando resultados con parámetros actuales...")
    print()
    
    # Resultados en datos de entrenamiento
    train_results = test_strategy_parameters(train_data, {})
    print("RESULTADOS EN DATOS DE ENTRENAMIENTO:")
    print(f"  Total operaciones: {train_results['total_trades']}")
    print(f"  Win Rate: {train_results['win_rate']:.1f}%")
    print(f"  PnL total: ${train_results['total_pnl']:,.2f}")
    print(f"  Capital final: ${train_results['final_capital']:,.2f}")
    if train_results['total_trades'] > 0:
        print(f"  Ganancia promedio: ${train_results['avg_win']:,.2f}")
        print(f"  Pérdida promedio: ${train_results['avg_loss']:,.2f}")
        if train_results['profit_factor'] > 0:
            print(f"  Profit Factor: {train_results['profit_factor']:.2f}")
    print()
    
    # Resultados en datos de prueba
    test_results = test_strategy_parameters(test_data, {})
    print("RESULTADOS EN DATOS DE PRUEBA:")
    print(f"  Total operaciones: {test_results['total_trades']}")
    print(f"  Win Rate: {test_results['win_rate']:.1f}%")
    print(f"  PnL total: ${test_results['total_pnl']:,.2f}")
    print(f"  Capital final: ${test_results['final_capital']:,.2f}")
    if test_results['total_trades'] > 0:
        print(f"  Ganancia promedio: ${test_results['avg_win']:,.2f}")
        print(f"  Pérdida promedio: ${test_results['avg_loss']:,.2f}")
        if test_results['profit_factor'] > 0:
            print(f"  Profit Factor: {test_results['profit_factor']:.2f}")
    print()
    
    # Recomendaciones
    print("=" * 80)
    print("💡 RECOMENDACIONES")
    print("=" * 80)
    
    if train_results['total_trades'] == 0:
        print("⚠️  No se detectaron operaciones. Posibles causas:")
        print("   - Umbrales de dirección muy estrictos")
        print("   - Tolerancias de retesteo muy pequeñas")
        print("   - Requisitos de volumen muy altos")
    elif train_results['win_rate'] < 40:
        print("⚠️  Win rate bajo (<40%). Considera:")
        print("   - Ajustar umbrales de confirmación")
        print("   - Mejorar detección de soporte/resistencia")
        print("   - Añadir filtros adicionales")
    elif train_results['total_pnl'] < 0:
        print("⚠️  Pérdidas detectadas. Posibles mejoras:")
        print("   - Ajustar stop loss (actualmente 5%)")
        print("   - Mejorar selección de entradas")
        print("   - Reducir tamaño de posición")
    else:
        print("✅ La estrategia muestra resultados positivos en datos de entrenamiento")
        print("   Verifica que los resultados en datos de prueba también sean consistentes")
    
    print()
    print("=" * 80)


def main():
    """Función principal."""
    if len(sys.argv) < 2:
        print("Uso: python service/optimize_strategy.py <archivo_csv> [fecha_inicio] [fecha_fin]")
        print()
        print("Ejemplo:")
        print("  python service/optimize_strategy.py btc_data.csv 2024-09-01 2024-10-31")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    start_date = sys.argv[2] if len(sys.argv) >= 3 else None
    end_date = sys.argv[3] if len(sys.argv) >= 4 else None
    
    if not Path(csv_path).exists():
        print(f"❌ Error: Archivo no encontrado: {csv_path}")
        sys.exit(1)
    
    optimize_strategy(csv_path, start_date, end_date)


if __name__ == "__main__":
    main()

