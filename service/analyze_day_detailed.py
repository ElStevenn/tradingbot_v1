"""
Análisis detallado día a día con información completa.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from service.trading_strategy import analyze_session, format_decision_log
from service.test_strategy import load_candles_from_csv
from datetime import datetime
import pytz


def analyze_single_day(csv_path: str, target_date: str):
    """
    Analiza un día específico con máximo detalle.
    
    Args:
        csv_path: Path al CSV
        target_date: Fecha a analizar (YYYY-MM-DD)
    """
    print("=" * 80)
    print(f"ANÁLISIS DETALLADO: {target_date}")
    print("=" * 80)
    print()
    
    # Cargar velas
    all_candles = load_candles_from_csv(csv_path)
    
    # Filtrar por fecha
    spain_tz = pytz.timezone("Europe/Madrid")
    target_dt = spain_tz.localize(datetime.strptime(target_date, "%Y-%m-%d"))
    target_date_obj = target_dt.date()
    
    day_candles = []
    for candle in all_candles:
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
        
        if ts.date() == target_date_obj:
            day_candles.append(candle)
    
    if not day_candles:
        print(f"❌ No se encontraron velas para la fecha {target_date}")
        return
    
    print(f"✅ Cargadas {len(day_candles)} velas para {target_date}")
    print()
    
    # Analizar
    decision = analyze_session(day_candles)
    
    # Mostrar log completo
    log = format_decision_log(decision)
    print(log)
    
    # Mostrar detalles adicionales
    print()
    print("=" * 80)
    print("📋 DETALLES TÉCNICOS")
    print("=" * 80)
    
    details = decision.get("analysis_details", {})
    
    if "resistance_search" in details:
        rs = details["resistance_search"]
        print(f"Resistencia identificada: ${rs.get('resistance_zone', 'N/A'):,.2f}")
        print(f"Precio actual: ${rs.get('current_price', 'N/A'):,.2f}")
        print(f"Distancia a resistencia: ${rs.get('distance_to_resistance', 'N/A'):,.2f}")
        print(f"Rechazo encontrado: {rs.get('rejection_found', False)}")
        if not rs.get('rejection_found'):
            print(f"Razón: {rs.get('reason_no_entry', 'N/A')}")
    
    if "support_search" in details:
        ss = details["support_search"]
        print(f"Soporte identificado: ${ss.get('support_zone', 'N/A'):,.2f}")
        print(f"Precio actual: ${ss.get('current_price', 'N/A'):,.2f}")
        print(f"Distancia a soporte: ${ss.get('distance_to_support', 'N/A'):,.2f}")
    
    print(f"Velas en observación: {details.get('observation_candles_count', 'N/A')}")
    print("=" * 80)


def main():
    if len(sys.argv) < 3:
        print("Uso: python service/analyze_day_detailed.py <archivo_csv> <fecha>")
        print("Ejemplo: python service/analyze_day_detailed.py october_2024_data.csv 2024-10-28")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    target_date = sys.argv[2]
    
    if not Path(csv_path).exists():
        print(f"❌ Error: Archivo no encontrado: {csv_path}")
        sys.exit(1)
    
    analyze_single_day(csv_path, target_date)


if __name__ == "__main__":
    main()

