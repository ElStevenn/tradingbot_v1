#!/bin/bash
# Script para iniciar el bot de trading en vivo

echo "🤖 Bot de Trading en Vivo - Bitget"
echo "=================================="
echo ""

# Verificar que existe conf.yaml
if [ ! -f "conf.yaml" ]; then
    echo "❌ Archivo conf.yaml no encontrado"
    echo ""
    echo "📝 Pasos para configurar:"
    echo "   1. Copia el archivo de ejemplo:"
    echo "      cp conf.yaml.example conf.yaml"
    echo ""
    echo "   2. Edita conf.yaml con tus credenciales de Bitget"
    echo ""
    echo "   3. Asegúrate de que BITGET_SANDBOX: true para pruebas"
    echo ""
    exit 1
fi

# Verificar que las dependencias estén instaladas
if ! python -c "import ccxt" 2>/dev/null; then
    echo "⚠️  Dependencias no instaladas"
    echo "   Ejecuta: pip install -r requirements.txt"
    exit 1
fi

# Iniciar el bot
echo "✅ Iniciando bot..."
echo ""
python bot/live_trading_bot.py conf.yaml

