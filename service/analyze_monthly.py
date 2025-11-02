"""
Script para analizar resultados por mes y identificar patrones.
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from service.analyze_week import analyze_week
from datetime import datetime


def analyze_by_month(csv_path: str, start_date: str, end_date: str, initial_capital: float = 500.0):
    """
    Analiza los resultados por mes para identificar patrones.
    """
    print("=" * 80)
    print("ANÁLISIS MENSUAL DE TRADING")
    print("=" * 80)
    print(f"CSV: {csv_path}")
    print(f"Período: {start_date} a {end_date}")
    print()
    
    # Dividir por meses
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    current_date = start_dt
    monthly_results = []
    
    while current_date <= end_dt:
        # Calcular inicio y fin del mes
        month_start = current_date.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)
        
        # Asegurar que no exceda la fecha final
        if month_end > end_dt:
            month_end = end_dt
        
        month_str = month_start.strftime("%Y-%m")
        print(f"📅 Analizando {month_str}...")
        
        try:
            results, stats = analyze_week(
                csv_path,
                month_start.strftime("%Y-%m-%d"),
                (month_end - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                initial_capital,
                quiet=True
            )
            
            monthly_results.append({
                "month": month_str,
                "stats": stats,
                "capital_final": initial_capital  # Se actualizará después
            })
            
            print(f"   ✅ {stats['entries_long'] + stats['entries_short']} operaciones")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Avanzar al siguiente mes
        if month_start.month == 12:
            current_date = month_start.replace(year=month_start.year + 1, month=1)
        else:
            current_date = month_start.replace(month=month_start.month + 1)
    
    print()
    print("=" * 80)
    print("RESUMEN MENSUAL")
    print("=" * 80)
    
    for result in monthly_results:
        stats = result["stats"]
        total_entries = stats['entries_long'] + stats['entries_short']
        if total_entries > 0:
            win_rate = (stats['entries_long'] + stats['entries_short'] - stats['no_entries']) / total_entries * 100
            print(f"{result['month']}: {total_entries} operaciones, Win Rate: {win_rate:.1f}%")
    
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python service/analyze_monthly.py <archivo_csv> <fecha_inicio> <fecha_fin> [capital]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    initial_capital = float(sys.argv[4]) if len(sys.argv) >= 5 else 500.0
    
    analyze_by_month(csv_path, start_date, end_date, initial_capital)

