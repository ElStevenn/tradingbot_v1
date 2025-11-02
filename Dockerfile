# Dockerfile para Bot de Trading en Vivo
FROM python:3.11-slim

# Metadatos
LABEL maintainer="Auto-Trader Bot"
LABEL description="Bot de trading BTC en Bitget - Ejecuta estrategia automáticamente"

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Madrid

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Establecer zona horaria
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY . .

# Crear directorio para logs
RUN mkdir -p /app/logs

# Variables de entorno por defecto (se pueden sobrescribir)
ENV BITGET_SANDBOX=true \
    SYMBOL=BTC/USDT:USDT \
    LEVERAGE=25 \
    INITIAL_CAPITAL_PCT=0.35 \
    STOP_LOSS_PCT=0.02 \
    LOG_PATH=/app/logs/bot_log.jsonl

# Healthcheck para monitorear el bot
HEALTHCHECK --interval=5m --timeout=30s --start-period=1m --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/app/logs/bot_log.jsonl') else 1)" || exit 1

# Comando por defecto: ejecutar el bot
CMD ["python", "bot/live_trading_bot.py", "/app/conf.yaml"]

