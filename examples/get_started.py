"""
Script para empezar rápido - guía paso a paso.
"""
import sys
import importlib.util
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("🤖 BOT DE TRADING BTC - GUÍA DE INICIO")
print("=" * 80)
print()

print("PASO 1: Generar datos de prueba")
print("-" * 80)
print("Si no tienes datos históricos, puedes generar datos de ejemplo:")
print()
print("  python examples/generate_sample_csv.py sample_data.csv 5")
print()
print("Esto creará 5 días de datos de ejemplo en 'sample_data.csv'")
print()

response = input("¿Tienes ya un archivo CSV con datos históricos? (s/n): ").strip().lower()

if response == 's':
    csv_path = input("Introduce la ruta al archivo CSV: ").strip()
    if not Path(csv_path).exists():
        print(f"❌ Error: Archivo no encontrado: {csv_path}")
        sys.exit(1)
else:
    print()
    print("Generando datos de ejemplo...")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generate_sample_csv",
        Path(__file__).parent / "generate_sample_csv.py"
    )
    gen_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen_module)
    csv_path = "sample_data.csv"
    gen_module.generate_sample_csv(csv_path, days=5)
    print(f"✅ Datos generados en: {csv_path}")

print()
print("=" * 80)
print("PASO 2: Análisis de fecha específica")
print("=" * 80)
print()

print("Ahora puedes analizar qué hubiera hecho el bot en una fecha específica.")
print("Por ejemplo, para analizar el viernes 19 de enero a las 14:30:")
print()
print(f"  python examples/analyze_specific_date.py {csv_path} 2024-01-19 14:30")
print()

# First, load data to check available dates
print("Cargando datos para verificar fechas disponibles...")
feed_module = __import__('bot.data_feed', fromlist=['DataFeed'])
feed = feed_module.DataFeed(timezone="UTC")

try:
    feed.load_from_csv(csv_path)
    if feed.candles:
        first_date = feed.candles[0].timestamp.date()
        last_date = feed.candles[-1].timestamp.date()
        middle_date = feed.candles[len(feed.candles)//2].timestamp.date()
        
        print(f"✅ Datos disponibles desde {first_date} hasta {last_date}")
        print(f"💡 Sugerencia: Prueba con {middle_date} o cualquier fecha en ese rango")
        print()
        
        suggested_date = str(middle_date)
    else:
        suggested_date = None
except Exception as e:
    print(f"⚠️  No se pudo verificar el rango de fechas: {e}")
    suggested_date = None

target_date = input(f"Introduce la fecha a analizar (YYYY-MM-DD) o Enter para usar {suggested_date or 'la fecha sugerida'}: ").strip()
if not target_date:
    if suggested_date:
        target_date = suggested_date
        print(f"Usando fecha sugerida: {target_date}")
    else:
        from datetime import datetime
        target_date = datetime.now().strftime("%Y-%m-%d")
        print(f"⚠️  Usando fecha de hoy: {target_date} (puede que no haya datos)")

target_time = input("Introduce la hora (HH:MM) o Enter para 14:30: ").strip()
if not target_time:
    target_time = "14:30"

print()
print("Ejecutando análisis...")
print()

# Run analysis

import importlib.util
spec = importlib.util.spec_from_file_location(
    "analyze_specific_date",
    Path(__file__).parent / "analyze_specific_date.py"
)
analyze_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze_module)

try:
    analyze_module.analyze_specific_session(csv_path, target_date, target_time)
except SystemExit:
    pass  # Already handled
except Exception as e:
    print(f"\n❌ Error durante el análisis: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("PASO 3: Simulación completa")
print("=" * 80)
print()

print("Para ejecutar una simulación completa sobre todo el CSV:")
print()
print(f"  python examples/run_csv_example.py {csv_path}")
print()

response = input("¿Quieres ejecutar la simulación completa ahora? (s/n): ").strip().lower()
if response == 's':
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_csv_example",
        Path(__file__).parent / "run_csv_example.py"
    )
    run_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_module)
    print()
    print("Ejecutando simulación...")
    print()
    # Modify sys.argv to pass the csv_path
    old_argv = sys.argv[:]
    sys.argv = ["run_csv_example.py", csv_path]
    try:
        run_module.main()
    finally:
        sys.argv = old_argv

print()
print("=" * 80)
print("✅ TODO LISTO")
print("=" * 80)
print()
print("Próximos pasos:")
print("1. Revisa los logs en bot_log.jsonl")
print("2. Analiza diferentes fechas con analyze_specific_date.py")
print("3. Ajusta la configuración en .env si es necesario")
print()
print("Para ver los logs:")
print("  cat bot_log.jsonl | jq")
print()

