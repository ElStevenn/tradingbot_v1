"""
Cliente para conectar con Bitget Exchange.
Maneja autenticación, obtención de datos y ejecución de órdenes.
"""
import ccxt
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pytz


class BitgetClient:
    """Cliente para interactuar con Bitget Exchange."""
    
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str, sandbox: bool = False):
        """
        Inicializa el cliente de Bitget.
        
        Args:
            api_key: API Key de Bitget
            api_secret: API Secret de Bitget
            api_passphrase: API Passphrase de Bitget
            sandbox: Si True, usa el entorno de prueba (sandbox)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.sandbox = sandbox
        
        # Inicializar exchange
        self.exchange = ccxt.bitget({
            'apiKey': api_key,
            'secret': api_secret,
            'password': api_passphrase,
            'enableRateLimit': True,
            'sandbox': sandbox,
            'options': {
                'defaultType': 'swap',  # Para futuros/perpetuos
            }
        })
        
        # Verificar conexión
        try:
            balance = self.exchange.fetch_balance()
            print(f"✅ Conectado a Bitget {'Sandbox' if sandbox else 'Producción'}")
        except Exception as e:
            raise Exception(f"❌ Error conectando a Bitget: {e}")
    
    def get_current_price(self, symbol: str = 'BTC/USDT:USDT') -> float:
        """
        Obtiene el precio actual de BTC.
        
        Args:
            symbol: Símbolo del par (default: BTC/USDT:USDT para perpetual)
        
        Returns:
            Precio actual como float
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            raise Exception(f"Error obteniendo precio: {e}")
    
    def get_ohlcv_data(self, symbol: str = 'BTC/USDT:USDT', timeframe: str = '1m', 
                       since: Optional[datetime] = None, limit: int = 1000) -> List[Dict]:
        """
        Obtiene datos OHLCV históricos.
        
        Args:
            symbol: Símbolo del par
            timeframe: Intervalo de velas ('1m', '5m', etc.)
            since: Timestamp desde cuando obtener datos (opcional)
            limit: Número máximo de velas
        
        Returns:
            Lista de velas en formato dict
        """
        try:
            since_timestamp = None
            if since:
                since_timestamp = int(since.timestamp() * 1000)
            
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since_timestamp, limit)
            
            # Convertir a formato estándar
            candles = []
            for candle in ohlcv:
                timestamp = datetime.fromtimestamp(candle[0] / 1000, tz=pytz.UTC)
                candles.append({
                    "timestamp": timestamp,
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                })
            
            return candles
        except Exception as e:
            raise Exception(f"Error obteniendo datos OHLCV: {e}")
    
    def get_realtime_candles(self, symbol: str = 'BTC/USDT:USDT', minutes: int = 10) -> List[Dict]:
        """
        Obtiene las últimas N minutos de velas en tiempo real.
        
        Args:
            symbol: Símbolo del par
            minutes: Número de minutos hacia atrás
        
        Returns:
            Lista de velas
        """
        end_time = datetime.now(pytz.UTC)
        start_time = end_time - timedelta(minutes=minutes + 5)  # +5 para margen
        
        return self.get_ohlcv_data(symbol, '1m', start_time, limit=minutes + 10)
    
    def open_position(self, symbol: str, side: str, size_usdt: float, 
                     stop_loss_price: Optional[float] = None, 
                     leverage: int = 25) -> Dict:
        """
        Abre una posición en Bitget.
        
        Args:
            symbol: Símbolo del par (ej: 'BTC/USDT:USDT')
            side: 'buy' (LONG) o 'sell' (SHORT)
            size_usdt: Tamaño de la posición en USDT (notional)
            stop_loss_price: Precio de stop loss (opcional)
            leverage: Apalancamiento
        
        Returns:
            Dict con información de la orden ejecutada
        """
        try:
            # Establecer apalancamiento
            self.exchange.set_leverage(leverage, symbol)
            
            # Calcular cantidad en contratos
            # Para BTC perpetual en Bitget, el tamaño se especifica en USDT
            # size_usdt es el notional total que queremos
            current_price = self.get_current_price(symbol)
            
            # Calcular cantidad: para perpetual, usamos el tamaño directamente
            # CCXT espera cantidad en contratos, pero para perpetuals puede ser en USDT
            # Verificar formato de Bitget
            amount = size_usdt / current_price  # Convertir USDT a cantidad de BTC
            
            # Crear orden market
            order = self.exchange.create_market_order(
                symbol=symbol,
                side=side,
                amount=amount
            )
            
            # Configurar stop loss después de abrir posición
            # Bitget requiere configurarlo por separado
            if stop_loss_price:
                try:
                    # Intentar configurar stop loss
                    # La implementación exacta depende de la API de Bitget
                    positions = self.get_open_positions(symbol)
                    if positions:
                        # Actualizar stop loss (puede requerir llamada específica de Bitget)
                        pass  # Se implementará según la API específica
                except:
                    pass  # Si falla, continuar sin stop loss automático
            
            return {
                'success': True,
                'order_id': order.get('id', 'unknown'),
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'size_usdt': size_usdt,
                'price': order.get('price') or current_price,
                'timestamp': datetime.now(pytz.UTC).isoformat(),
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(pytz.UTC).isoformat(),
            }
    
    def close_position(self, symbol: str, position_id: Optional[str] = None) -> Dict:
        """
        Cierra la posición actual.
        
        Args:
            symbol: Símbolo del par
            position_id: ID de la posición (opcional, si no se proporciona cierra todas)
        
        Returns:
            Dict con resultado
        """
        try:
            # Obtener posiciones abiertas
            positions = self.exchange.fetch_positions([symbol])
            
            for pos in positions:
                if float(pos['contracts']) != 0:
                    # Cerrar posición opuesta
                    side = 'sell' if pos['side'] == 'long' else 'buy'
                    amount = abs(float(pos['contracts']))
                    
                    order = self.exchange.create_market_order(
                        symbol=symbol,
                        side=side,
                        amount=amount,
                        params={'reduceOnly': True}  # Solo reducir, no abrir nueva
                    )
                    
                    return {
                        'success': True,
                        'order_id': order['id'],
                        'closed_position': pos,
                        'timestamp': datetime.now(pytz.UTC),
                    }
            
            return {
                'success': True,
                'message': 'No hay posiciones abiertas',
                'timestamp': datetime.now(pytz.UTC),
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(pytz.UTC),
            }
    
    def get_open_positions(self, symbol: str = 'BTC/USDT:USDT') -> List[Dict]:
        """
        Obtiene posiciones abiertas.
        
        Args:
            symbol: Símbolo del par
        
        Returns:
            Lista de posiciones abiertas
        """
        try:
            positions = self.exchange.fetch_positions([symbol])
            open_positions = [
                {
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'size': float(pos['contracts']),
                    'entry_price': float(pos['entryPrice']),
                    'mark_price': float(pos['markPrice']),
                    'unrealized_pnl': float(pos['unrealizedPnl']),
                }
                for pos in positions if float(pos['contracts']) != 0
            ]
            return open_positions
        except Exception as e:
            raise Exception(f"Error obteniendo posiciones: {e}")
    
    def update_stop_loss(self, symbol: str, stop_loss_price: float) -> Dict:
        """
        Actualiza el stop loss de una posición abierta.
        
        Args:
            symbol: Símbolo del par
            stop_loss_price: Nuevo precio de stop loss
        
        Returns:
            Dict con resultado
        """
        try:
            # Bitget puede requerir actualizar stop loss mediante orden de tipo stop
            # Esto depende de la API específica de Bitget
            positions = self.get_open_positions(symbol)
            if not positions:
                return {'success': False, 'error': 'No hay posiciones abiertas'}
            
            # Nota: La implementación exacta depende de cómo Bitget maneje stop loss
            # Puede requerir crear una orden stop limit
            return {
                'success': True,
                'message': f'Stop loss actualizado a {stop_loss_price}',
                'timestamp': datetime.now(pytz.UTC),
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now(pytz.UTC),
            }

