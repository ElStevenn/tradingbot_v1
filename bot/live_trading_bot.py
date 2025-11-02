"""
Bot de trading en vivo para Bitget.
Ejecuta la estrategia todos los días de lunes a viernes a la apertura de NY.
"""
import time
import schedule
from datetime import datetime, timedelta
import pytz
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.bitget_client import BitgetClient
from service.trading_strategy import analyze_session
from bot.logger_live import Logger
import yaml
from pathlib import Path
from typing import Optional


class LiveTradingBot:
    """Bot de trading en vivo."""
    
    def __init__(self, config_path: str = 'conf.yaml'):
        """
        Inicializa el bot.
        
        Args:
            config_path: Ruta al archivo de configuración
        """
        # Cargar configuración: primero variables de entorno, luego archivo
        self.config = {}
        
        # Cargar desde archivo si existe
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f) or {}
                self.config.update(file_config)
        
        # Variables de entorno tienen prioridad (más seguro para Docker)
        import os
        self.config['BITGET_API_KEY'] = os.getenv('BITGET_API_KEY', self.config.get('BITGET_API_KEY', ''))
        self.config['BITGET_API_SECRET'] = os.getenv('BITGET_API_SECRET', self.config.get('BITGET_API_SECRET', ''))
        self.config['BITGET_API_PASSPHRASE'] = os.getenv('BITGET_API_PASSPHRASE', self.config.get('BITGET_API_PASSPHRASE', ''))
        self.config['BITGET_SANDBOX'] = os.getenv('BITGET_SANDBOX', str(self.config.get('BITGET_SANDBOX', 'true'))).lower() == 'true'
        
        # Validar que las credenciales estén configuradas
        if not self.config.get('BITGET_API_KEY') or not self.config.get('BITGET_API_SECRET') or not self.config.get('BITGET_API_PASSPHRASE'):
            raise ValueError("❌ Credenciales de Bitget no configuradas. Configura BITGET_API_KEY, BITGET_API_SECRET y BITGET_API_PASSPHRASE")
        
        # Inicializar cliente de Bitget
        self.client = BitgetClient(
            api_key=self.config['BITGET_API_KEY'],
            api_secret=self.config['BITGET_API_SECRET'],
            api_passphrase=self.config['BITGET_API_PASSPHRASE'],
            sandbox=self.config['BITGET_SANDBOX']
        )
        
        # Ruta de logs (desde env o config)
        log_path = os.getenv('LOG_PATH', self.config.get('LOG_PATH', 'bot_log.jsonl'))
        self.logger = Logger(log_path)
        
        # Configuración de trading (desde config o variables de entorno)
        import os
        self.symbol = os.getenv('SYMBOL', self.config.get('SYMBOL', 'BTC/USDT:USDT'))
        self.leverage = int(os.getenv('LEVERAGE', self.config.get('LEVERAGE', 25)))
        self.initial_capital_pct = float(os.getenv('INITIAL_CAPITAL_PCT', self.config.get('INITIAL_CAPITAL_PCT', 0.35)))
        self.stop_loss_pct = float(os.getenv('STOP_LOSS_PCT', self.config.get('STOP_LOSS_PCT', 0.02)))
        
        # Estado del bot
        self.current_position = None
        self.current_capital = None
        self.session_started = False
        
        # Zonas horarias
        self.ny_tz = pytz.timezone("America/New_York")
        self.spain_tz = pytz.timezone("Europe/Madrid")
        
        print("🤖 Bot de Trading en Vivo inicializado")
        print(f"   Exchange: Bitget {'Sandbox' if self.config.get('BITGET_SANDBOX', False) else 'Producción'}")
        print(f"   Símbolo: {self.symbol}")
        print(f"   Apalancamiento: {self.leverage}x")
    
    def get_current_balance(self) -> float:
        """Obtiene el balance actual en USDT."""
        try:
            balance = self.client.exchange.fetch_balance()
            if 'USDT' in balance.get('total', {}):
                return float(balance['total']['USDT'])
            return 0.0
        except Exception as e:
            self.logger.log_error(f"Error obteniendo balance: {e}")
            return 0.0
    
    def check_ny_open_time(self) -> tuple:
        """
        Verifica si es hora de la apertura de NY.
        
        Returns:
            Tuple (is_open_time, ny_open_datetime, time_until_open)
        """
        now_utc = datetime.now(pytz.UTC)
        today = now_utc.date()
        
        # Calcular apertura NY (09:30 hora NY)
        ny_open_ny = self.ny_tz.localize(
            datetime.combine(today, datetime.min.time().replace(hour=9, minute=30))
        )
        ny_open_utc = ny_open_ny.astimezone(pytz.UTC)
        ny_open_spain = ny_open_utc.astimezone(self.spain_tz)
        
        # Ventana de operación: 5 minutos antes y 30 minutos después
        window_start = ny_open_utc - timedelta(minutes=5)
        window_end = ny_open_utc + timedelta(minutes=30)
        
        is_open_time = window_start <= now_utc <= window_end
        
        time_until_open = (ny_open_utc - now_utc).total_seconds() / 60  # minutos
        
        return is_open_time, ny_open_utc, ny_open_spain, time_until_open
    
    def should_trade_today(self) -> bool:
        """Verifica si hoy es día de trading (lunes a viernes)."""
        today = datetime.now(pytz.UTC).date()
        weekday = today.weekday()  # 0=lunes, 6=domingo
        return weekday < 5  # Lunes a viernes
    
    def get_candles_for_analysis(self) -> list:
        """Obtiene velas necesarias para el análisis."""
        try:
            # Obtener velas de las últimas 4 horas (suficiente para análisis)
            now_utc = datetime.now(pytz.UTC)
            start_time = now_utc - timedelta(hours=4)
            
            candles = self.client.get_ohlcv_data(
                symbol=self.symbol,
                timeframe='1m',
                since=start_time,
                limit=500
            )
            
            return candles
        except Exception as e:
            self.logger.log_error(f"Error obteniendo velas: {e}")
            return []
    
    def execute_trading_decision(self, decision: dict):
        """
        Ejecuta la decisión del bot.
        
        Args:
            decision: Decisión de la estrategia (de analyze_session)
        """
        if decision['entry_type'] == 'NO_ENTRY':
            self.logger.log_event('no_entry', {
                'reason': decision.get('analysis_details', {}).get('reason_no_entry', 'Sin señal válida'),
                'direction': decision['direction_detected']
            })
            return
        
        # Verificar que no haya posición abierta
        open_positions = self.client.get_open_positions(self.symbol)
        if open_positions:
            self.logger.log_event('position_already_open', {
                'existing_position': open_positions[0],
                'new_decision': decision
            })
            return
        
        # Obtener balance actual
        balance = self.get_current_balance()
        if balance == 0:
            self.logger.log_error("Balance es 0, no se puede operar")
            return
        
        # Calcular tamaño de posición
        # Usar porcentaje dinámico basado en balance
        base_pct = self.initial_capital_pct
        if balance > 600:  # Si capital > +20% desde inicio
            base_pct = 0.40
        if balance > 750:  # Si capital > +50%
            base_pct = 0.45
        if balance > 1000:  # Si capital > +100%
            base_pct = 0.50
        
        capital_to_use = balance * base_pct
        position_size = capital_to_use * self.leverage  # Tamaño total apalancado
        
        # Determinar side y calcular stop loss
        if decision['entry_type'] == 'LONG':
            side = 'buy'
            stop_loss_price = decision['entry_price'] * (1 - self.stop_loss_pct)
        else:  # SHORT
            side = 'sell'
            stop_loss_price = decision['entry_price'] * (1 + self.stop_loss_pct)
        
        # Ejecutar orden
        result = self.client.open_position(
            symbol=self.symbol,
            side=side,
            size=position_size,
            stop_loss_price=stop_loss_price,
            leverage=self.leverage
        )
        
        if result['success']:
            self.current_position = {
                'type': decision['entry_type'],
                'entry_price': decision['entry_price'],
                'entry_time': datetime.now(pytz.UTC),
                'size': position_size,
                'stop_loss': stop_loss_price,
                'order_id': result['order_id'],
            }
            
            self.logger.log_event('position_opened', {
                'entry_type': decision['entry_type'],
                'entry_price': decision['entry_price'],
                'size': position_size,
                'stop_loss': stop_loss_price,
                'support_zone': decision.get('support_zone'),
                'resistance_zone': decision.get('resistance_zone'),
            })
            
            print(f"✅ Posición {decision['entry_type']} abierta a ${decision['entry_price']:,.2f}")
        else:
            self.logger.log_error(f"Error abriendo posición: {result.get('error')}")
    
    def check_and_close_positions(self):
        """Verifica y cierra posiciones según las reglas del bot."""
        if not self.current_position:
            return
        
        open_positions = self.client.get_open_positions(self.symbol)
        if not open_positions:
            # Posición ya fue cerrada
            if self.current_position:
                self.logger.log_event('position_closed_externally', {
                    'previous_position': self.current_position
                })
                self.current_position = None
            return
        
        pos = open_positions[0]
        
        # Verificar stop loss (Bitget lo maneja automáticamente, pero verificamos)
        if self.current_position:
            entry_price = self.current_position['entry_price']
            current_price = pos['mark_price']
            
            # Verificar si se alcanzó stop loss
            if self.current_position['type'] == 'LONG':
                if current_price <= self.current_position['stop_loss']:
                    # Stop loss alcanzado
                    self.close_position_reason('stop_loss', current_price)
            else:  # SHORT
                if current_price >= self.current_position['stop_loss']:
                    self.close_position_reason('stop_loss', current_price)
        
        # Verificar cierre de sesión (16:00 hora española)
        now_utc = datetime.now(pytz.UTC)
        now_spain = now_utc.astimezone(self.spain_tz)
        
        if now_spain.hour >= 16:
            # Cerrar posición al final de sesión
            self.close_position_reason('session_end', pos['mark_price'])
    
    def close_position_reason(self, reason: str, exit_price: float):
        """Cierra la posición actual por una razón específica."""
        result = self.client.close_position(self.symbol)
        
        if result['success']:
            if self.current_position:
                pnl = self.calculate_pnl(
                    self.current_position['entry_price'],
                    exit_price,
                    self.current_position['type'],
                    self.current_position['size'],
                    self.leverage
                )
                
                self.logger.log_event('position_closed', {
                    'reason': reason,
                    'entry_price': self.current_position['entry_price'],
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'entry_type': self.current_position['type'],
                })
                
                print(f"🔒 Posición cerrada ({reason}) - PnL: ${pnl:,.2f}")
            
            self.current_position = None
    
    def calculate_pnl(self, entry_price: float, exit_price: float, 
                     entry_type: str, size: float, leverage: int) -> float:
        """Calcula el PnL de una operación."""
        position_size = size * leverage
        
        if entry_type == 'LONG':
            price_change_pct = (exit_price - entry_price) / entry_price
            pnl = price_change_pct * position_size
        else:  # SHORT
            price_change_pct = (entry_price - exit_price) / entry_price
            pnl = price_change_pct * position_size
        
        return pnl
    
    def run_trading_session(self):
        """Ejecuta una sesión de trading completa."""
        if not self.should_trade_today():
            return
        
        is_open_time, ny_open_utc, ny_open_spain, time_until = self.check_ny_open_time()
        
        if not is_open_time:
            return
        
        if self.session_started:
            # Ya ejecutamos la sesión hoy
            return
        
        print(f"🕐 Apertura NY: {ny_open_spain.strftime('%H:%M')} hora española")
        print(f"   Analizando mercado...")
        
        # Obtener velas
        candles = self.get_candles_for_analysis()
        if len(candles) < 100:
            self.logger.log_error(f"Velas insuficientes: {len(candles)}")
            return
        
        # Analizar con la estrategia
        decision = analyze_session(candles)
        
        # Ejecutar decisión
        self.execute_trading_decision(decision)
        
        self.session_started = True
        
        # Programar verificación periódica de posiciones
        self.start_position_monitoring()
    
    def start_position_monitoring(self):
        """Inicia el monitoreo periódico de posiciones."""
        # Verificar cada minuto si hay posición abierta
        schedule.every(1).minutes.do(self.check_and_close_positions)
    
    def run(self):
        """Ejecuta el bot en bucle continuo."""
        print("\n" + "="*80)
        print("🚀 BOT DE TRADING EN VIVO - INICIADO")
        print("="*80)
        print(f"Hora actual: {datetime.now(self.spain_tz).strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Programar sesión de trading diaria
        # Ejecutar cada minuto para verificar si es hora de apertura NY
        schedule.every(1).minutes.do(self.run_trading_session)
        
        # Verificar posiciones cada minuto
        schedule.every(1).minutes.do(self.check_and_close_positions)
        
        # Log de inicio
        self.logger.log_event('bot_started', {
            'timestamp': datetime.now(pytz.UTC).isoformat(),
            'config': {
                'symbol': self.symbol,
                'leverage': self.leverage,
                'sandbox': self.config.get('BITGET_SANDBOX', False),
            }
        })
        
        print("✅ Bot activo y esperando apertura de NY...")
        print("   Presiona Ctrl+C para detener\n")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
                
                # Reset session_started al inicio de cada día
                now = datetime.now(pytz.UTC)
                if now.hour == 0 and now.minute == 0:
                    self.session_started = False
                    
        except KeyboardInterrupt:
            print("\n\n🛑 Bot detenido por el usuario")
            self.logger.log_event('bot_stopped', {
                'timestamp': datetime.now(pytz.UTC).isoformat()
            })
            
            # Cerrar posición si hay alguna abierta
            if self.current_position:
                print("⚠️  Cerrando posición abierta...")
                self.client.close_position(self.symbol)


if __name__ == "__main__":
    import sys
    
    config_path = sys.argv[1] if len(sys.argv) > 1 else 'conf.yaml'
    
    bot = LiveTradingBot(config_path)
    bot.run()

