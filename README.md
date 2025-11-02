# Bot de Trading BTC - Bitget

Bot de trading automático para BTC perpetual que opera alrededor de la apertura de NY (15:30/14:30 hora española).

## 🚀 Inicio Rápido

### Configuración

1. **Obtener credenciales de Bitget:**
   - Ve a Bitget → API Management
   - Crea API Key con permisos de Trading
   - Copia: API Key, Secret Key, Passphrase

2. **Configurar variables de entorno o archivo:**
   ```bash
   # Opción A: Variables de entorno (recomendado para Docker)
   export BITGET_API_KEY="tu_api_key"
   export BITGET_API_SECRET="tu_secret"
   export BITGET_API_PASSPHRASE="tu_passphrase"
   export BITGET_SANDBOX=true  # true para pruebas
   
   # Opción B: Archivo conf.yaml
   cp conf.yaml.example conf.yaml
   nano conf.yaml  # Edita con tus credenciales
   ```

### Ejecutar con Docker (Recomendado)

```bash
# Construir imagen
make build

# Ejecutar en producción
make run-prod

# Ver logs
make logs

# Ver todos los comandos
make help
```

### Ejecutar sin Docker

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python bot/live_trading_bot.py conf.yaml
```

## 📊 Análisis Histórico

```bash
# Analizar datos históricos
python service/analyze_week.py btc_may_oct.csv 2024-05-05 2024-10-17 500

# Analizar día específico
python service/analyze_day_detailed.py btc_may_oct.csv 2024-10-14
```

## ⚙️ Configuración

El bot usa la estrategia optimizada con:
- Apalancamiento: 25x
- Capital por operación: 35% base (hasta 50%)
- Stop loss: 2% (trailing)
- Take Profit parcial: 50% en +2.5%
- Filtros de tendencia diaria

## 📝 Comandos Docker (Makefile)

```bash
make build      # Construir imagen
make run        # Ejecutar bot
make run-prod   # Ejecutar en producción
make stop       # Detener bot
make restart    # Reiniciar bot
make logs       # Ver logs
make status     # Ver estado
make update     # Actualizar y reiniciar
```

## 🔒 Seguridad

- ✅ Empieza con `BITGET_SANDBOX=true` para pruebas
- ✅ NO subas `conf.yaml` o credenciales a Git
- ✅ Usa permisos limitados en API Key (solo Trading)
- ✅ Empieza con capital pequeño

## 📁 Estructura

```
bot/
├── live_trading_bot.py    # Bot principal
├── bitget_client.py       # Cliente Bitget
└── logger_live.py        # Sistema de logs

service/
└── trading_strategy.py    # Estrategia optimizada

conf.yaml.example         # Plantilla de configuración
Makefile                  # Comandos Docker
Dockerfile               # Imagen Docker
```
