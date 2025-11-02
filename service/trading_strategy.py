"""
Estrategia de trading BTC: Análisis de apertura NY
Detecta dirección inicial y busca zonas de entrada (soporte/resistencia)

Nota: La apertura de NY cambia según el horario:
- Horario de verano (marzo-octubre): 09:30 EST = 15:30 hora española
- Horario de invierno (noviembre-marzo): 09:30 EST = 14:30 hora española (o 15:30 según cambio de hora)
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Literal
import pytz


def analyze_session(candles: List[Dict]) -> Dict:
    """
    Analiza una sesión de trading y determina la decisión del bot.
    
    Args:
        candles: Lista de velas OHLCV en formato:
            [
                {
                    "timestamp": datetime o string ISO,
                    "open": float,
                    "high": float,
                    "low": float,
                    "close": float,
                    "volume": float
                },
                ...
            ]
    
    Returns:
        Dict con la decisión del bot:
        {
            "session_date": str,
            "ny_open_time": str,
            "direction_detected": "up" | "down" | "none",
            "entry_type": "LONG" | "SHORT" | "NO_ENTRY",
            "support_zone": float | None,
            "resistance_zone": float | None,
            "entry_price": float | None,
            "entry_minute": int | None,
            "entry_timestamp": str | None,
            "analysis_details": {...}
        }
    """
    if not candles:
        return {
            "session_date": None,
            "ny_open_time": None,
            "direction_detected": "none",
            "entry_type": "NO_ENTRY",
            "support_zone": None,
            "resistance_zone": None,
            "entry_price": None,
            "entry_minute": None,
            "entry_timestamp": None,
            "analysis_details": {"error": "No hay velas disponibles"}
        }
    
    # Timezone: España (Europe/Madrid)
    spain_tz = pytz.timezone("Europe/Madrid")
    
    # Normalizar candles y encontrar la primera vela
    # Asumimos que los timestamps sin timezone están en hora local española
    normalized_candles = []
    for candle in candles:
        if isinstance(candle.get("timestamp"), str):
            try:
                # Intentar parsear como ISO
                ts = datetime.fromisoformat(candle["timestamp"].replace('Z', '+00:00'))
            except ValueError:
                # Si falla, parsear como formato simple YYYY-MM-DD HH:MM:SS
                ts = datetime.strptime(candle["timestamp"], "%Y-%m-%d %H:%M:%S")
        else:
            ts = candle["timestamp"]
        
        # Si no tiene timezone, asumimos que está en hora española
        if ts.tzinfo is None:
            ts = spain_tz.localize(ts)
        
        # Convertir todo a UTC para trabajar internamente
        ts = ts.astimezone(pytz.UTC)
        
        normalized_candles.append({
            "timestamp": ts,
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
            "volume": float(candle.get("volume", 0)),
        })
    
    # Ordenar por timestamp
    normalized_candles.sort(key=lambda x: x["timestamp"])
    
    if not normalized_candles:
        return {
            "session_date": None,
            "ny_open_time": None,
            "direction_detected": "none",
            "entry_type": "NO_ENTRY",
            "support_zone": None,
            "resistance_zone": None,
            "entry_price": None,
            "entry_minute": None,
            "entry_timestamp": None,
            "analysis_details": {"error": "No se pudieron normalizar las velas"}
        }
    
    # Obtener fecha de la primera vela
    first_candle_time = normalized_candles[0]["timestamp"]
    session_date = first_candle_time.date()
    
    # Calcular apertura NY usando la zona horaria de Nueva York directamente
    # Esto maneja automáticamente el cambio de hora (DST)
    # Antes del cambio (octubre): NY 09:30 = España 14:30
    # Después del cambio (noviembre): NY 09:30 = España 15:30
    ny_tz = pytz.timezone("America/New_York")
    spain_time = first_candle_time.astimezone(spain_tz)
    
    # Apertura NY: 09:30 hora de Nueva York (maneja DST automáticamente)
    ny_open_ny = ny_tz.localize(
        datetime.combine(spain_time.date(), datetime.min.time().replace(hour=9, minute=30))
    )
    ny_open_utc = ny_open_ny.astimezone(pytz.UTC)
    ny_open_spain = ny_open_utc.astimezone(spain_tz)
    
    # Debug: mostrar timestamps importantes
    # print(f"DEBUG: Sesión: {session_date}")
    # print(f"DEBUG: NY Open (NY): {ny_open_ny.strftime('%Y-%m-%d %H:%M %Z')}")
    # print(f"DEBUG: NY Open (España): {ny_open_spain.strftime('%Y-%m-%d %H:%M %Z')} = UTC: {ny_open_utc.strftime('%Y-%m-%d %H:%M %Z')}")
    
    # Ventana de observación: primeros 10 minutos después de la apertura NY
    observation_end = ny_open_utc + timedelta(minutes=10)
    
    # Obtener velas en la ventana de observación
    # Usar un margen de ±2 minutos para asegurar que encontramos velas (puede haber lag)
    observation_start = ny_open_utc - timedelta(minutes=2)
    observation_candles = [
        c for c in normalized_candles
        if observation_start <= c["timestamp"] <= observation_end
    ]
    
    # Si no encontramos velas, ampliar la búsqueda
    if len(observation_candles) < 2:
        # Buscar velas en un rango más amplio (±5 minutos)
        observation_start = ny_open_utc - timedelta(minutes=5)
        observation_end = ny_open_utc + timedelta(minutes=15)
        observation_candles = [
            c for c in normalized_candles
            if observation_start <= c["timestamp"] <= observation_end
        ]
    
    if len(observation_candles) < 2:
        return {
            "session_date": str(session_date),
            "ny_open_time": ny_open_utc.isoformat(),
            "direction_detected": "none",
            "entry_type": "NO_ENTRY",
            "support_zone": None,
            "resistance_zone": None,
            "entry_price": None,
            "entry_minute": None,
            "entry_timestamp": None,
            "analysis_details": {
                "error": f"Velas insuficientes en ventana de observación. Encontradas: {len(observation_candles)}"
            }
        }
    
    # Encontrar la vela más cercana a la apertura NY
    open_candle = None
    min_diff = float('inf')
    for candle in observation_candles:
        diff = abs((candle["timestamp"] - ny_open_utc).total_seconds())
        if diff < min_diff:
            min_diff = diff
            open_candle = candle
    
    if open_candle is None:
        open_candle = observation_candles[0]
    
    # Detectar dirección en los primeros minutos
    price_at_open = open_candle["close"]
    price_after_5min = None
    price_after_10min = None
    
    # Buscar velas después de la apertura
    candles_after_open = [
        c for c in observation_candles
        if c["timestamp"] >= ny_open_utc
    ]
    
    if candles_after_open:
        for candle in candles_after_open:
            minutes_from_open = (candle["timestamp"] - ny_open_utc).total_seconds() / 60
            
            # Precio a los 5 minutos
            if 4 <= minutes_from_open <= 6 and price_after_5min is None:
                price_after_5min = candle["close"]
            
            # Precio a los 10 minutos
            if 9 <= minutes_from_open <= 11:
                price_after_10min = candle["close"]
                break
        
        # Si no tenemos precio a los 5 min, usar el último disponible en la ventana
        if price_after_5min is None and candles_after_open:
            price_after_5min = candles_after_open[-1]["close"]
        
        if price_after_10min is None:
            price_after_10min = candles_after_open[-1]["close"] if candles_after_open else price_at_open
    else:
        # Si no hay velas después de la apertura, usar las disponibles
        price_after_5min = observation_candles[-1]["close"]
        price_after_10min = observation_candles[-1]["close"]
    
    # Determinar dirección basada en el movimiento en los primeros minutos
    # Usar el cambio después de 5 minutos, pero si es muy pequeño, usar hasta 10 minutos
    price_change_pct = ((price_after_5min - price_at_open) / price_at_open) * 100
    
    # Si el cambio es muy pequeño, intentar con el de 10 minutos
    if abs(price_change_pct) < 0.05:
        price_change_pct = ((price_after_10min - price_at_open) / price_at_open) * 100
    
    # Umbrales ajustados basados en análisis: necesitamos movimientos más claros
    if price_change_pct < -0.08:  # Bajó más de 0.08% (movimiento más claro)
        direction = "down"
    elif price_change_pct > 0.08:  # Subió más de 0.08% (movimiento más claro)
        direction = "up"
    else:
        direction = "none"  # Lateral - evitar entradas en movimientos ambiguos
    
    # Obtener velas previas para encontrar soporte/resistencia
    # Buscar en las últimas 2 horas antes de la apertura
    pre_open_start = ny_open_utc - timedelta(hours=2)
    pre_open_candles = [
        c for c in normalized_candles
        if pre_open_start <= c["timestamp"] < ny_open_utc
    ]
    
    analysis_details = {
        "price_at_open": price_at_open,
        "price_after_5min": price_after_5min,
        "price_after_10min": price_after_10min,
        "price_change_pct": price_change_pct,
        "observation_candles_count": len(observation_candles),
    }
    
    # Calcular tendencia diaria para filtrar entradas
    # Analizar precio de apertura vs precio actual de la sesión
    daily_trend = "neutral"
    daily_change_pct = 0.0
    current_price = None
    
    if normalized_candles:
        # Comparar precio de apertura del día con precio actual
        first_price = float(normalized_candles[0]["open"])
        current_price = float(normalized_candles[-1]["close"])
        daily_change_pct = ((current_price - first_price) / first_price) * 100
        
        if daily_change_pct > 0.5:  # Subida significativa del día
            daily_trend = "bullish"
        elif daily_change_pct < -0.5:  # Bajada significativa del día
            daily_trend = "bearish"
    
    entry_type = "NO_ENTRY"
    support_zone = None
    resistance_zone = None
    entry_price = None
    entry_minute = None
    entry_timestamp = None
    
    if direction == "down":
        # Precio bajó → buscar soporte cercano para LONG
        # FILTRO: Solo considerar LONG si la tendencia diaria NO es muy bajista
        if daily_trend == "bearish" and daily_change_pct < -1.5:
            # Tendencia bajista muy fuerte, evitar LONG
            analysis_details["support_search"] = {
                "support_zone": None,
                "current_price": current_price,
                "reason_no_entry": f"Tendencia diaria bajista muy fuerte ({daily_change_pct:.2f}%), no operar LONG"
            }
        elif pre_open_candles:
            # Encontrar mínimo reciente (soporte)
            recent_lows = [c["low"] for c in pre_open_candles[-30:]]  # Últimas 30 velas
            if recent_lows:
                support_zone = min(recent_lows)
                # También buscar un soporte más cercano si el precio ya está cerca
                current_price = observation_candles[-1]["close"]
                
                # Buscar entrada LONG cuando precio rebote desde el soporte
                # Revisar velas después de la ventana de observación
                post_observation_candles = [
                    c for c in normalized_candles
                    if observation_end < c["timestamp"] <= observation_end + timedelta(minutes=30)
                ]
                
                # Buscar rebote: precio toca cerca del soporte y luego sube
                tolerance = support_zone * 0.001  # 0.1% de tolerancia
                
                for candle in post_observation_candles:
                    # Si el precio toca el soporte y luego rebota
                    if candle["low"] <= support_zone + tolerance:
                        # Verificar que la siguiente vela confirma el rebote (sube)
                        candle_idx = normalized_candles.index(candle)
                        # Necesitamos al menos 2 velas de confirmación para más robustez
                        if candle_idx + 2 < len(normalized_candles):
                            next_candle = normalized_candles[candle_idx + 1]
                            second_candle = normalized_candles[candle_idx + 2]
                            
                            # Validación estricta: precio debe subir consistentemente
                            price_rising = (next_candle["close"] > candle["close"] and 
                                          second_candle["close"] > next_candle["close"])
                            above_support = next_candle["close"] > support_zone
                            
                            if price_rising and above_support:
                                # REBOTE CONFIRMADO - Entrada LONG
                                entry_type = "LONG"
                                entry_price = next_candle["close"]
                                entry_timestamp = next_candle["timestamp"]
                                minutes_from_ny_open = (next_candle["timestamp"] - ny_open_utc).total_seconds() / 60
                                entry_minute = int(minutes_from_ny_open)
                                break
                
                analysis_details["support_search"] = {
                    "support_zone": support_zone,
                    "current_price": current_price,
                    "distance_to_support": current_price - support_zone,
                    "searched_candles": len(post_observation_candles)
                }
                
    elif direction == "up":
        # Precio subió → buscar resistencia cercana para SHORT
        # FILTRO: Solo considerar SHORT si la tendencia diaria NO es muy alcista
        if daily_trend == "bullish" and daily_change_pct > 1.5:
            # Tendencia alcista muy fuerte, evitar SHORT
            analysis_details["resistance_search"] = {
                "resistance_zone": None,
                "current_price": current_price,
                "reason_no_entry": f"Tendencia diaria alcista muy fuerte ({daily_change_pct:.2f}%), no operar SHORT"
            }
        elif pre_open_candles:
            # Encontrar máximo reciente (resistencia)
            recent_highs = [c["high"] for c in pre_open_candles[-30:]]  # Últimas 30 velas
            if recent_highs:
                resistance_zone = max(recent_highs)
                current_price = observation_candles[-1]["close"]
                
                # Buscar entrada SHORT cuando precio rechace desde la resistencia
                # Buscar en las próximas 30-45 minutos después de la ventana de observación
                post_observation_start = observation_end
                post_observation_end = observation_end + timedelta(minutes=45)
                post_observation_candles = [
                    c for c in normalized_candles
                    if post_observation_start < c["timestamp"] <= post_observation_end
                ]
                
                # Buscar rechazo: precio toca cerca de la resistencia y luego baja
                # Ajustado: tolerancia más estricta y validación más robusta
                tolerance = resistance_zone * 0.0015  # 0.15% de tolerancia (más estricto)
                
                for candle in post_observation_candles:
                    # CRITERIO 1: Precio toca resistencia y rechaza inmediatamente
                    if candle["high"] >= resistance_zone - tolerance:
                        candle_idx = normalized_candles.index(candle)
                        # Necesitamos al menos 2 velas de confirmación
                        if candle_idx + 2 < len(normalized_candles):
                            next_candle = normalized_candles[candle_idx + 1]
                            second_candle = normalized_candles[candle_idx + 2]
                            
                            # Validación estricta: precio debe bajar consistentemente
                            price_declining = (next_candle["close"] < candle["close"] and 
                                              second_candle["close"] < next_candle["close"])
                            below_resistance = next_candle["close"] < resistance_zone
                            
                            if price_declining and below_resistance:
                                # RECHAZO CONFIRMADO - Entrada SHORT
                                entry_type = "SHORT"
                                entry_price = next_candle["close"]
                                entry_timestamp = next_candle["timestamp"]
                                minutes_from_ny_open = (next_candle["timestamp"] - ny_open_utc).total_seconds() / 60
                                entry_minute = int(minutes_from_ny_open)
                                break
                    
                    # CRITERIO 2: Precio supera resistencia brevemente pero rechaza fuerte
                    if candle["high"] > resistance_zone * 1.002:  # Superó resistencia por más de 0.2%
                        # Pero cerró por debajo o muy cerca
                        if candle["close"] <= resistance_zone * 0.998:  # Cerró al menos 0.2% por debajo
                            candle_idx = normalized_candles.index(candle)
                            if candle_idx + 1 < len(normalized_candles):
                                next_candle = normalized_candles[candle_idx + 1]
                                # Confirmar que sigue bajando
                                if next_candle["close"] < candle["close"] and next_candle["close"] < resistance_zone:
                                    # RECHAZO CONFIRMADO - Entrada SHORT
                                    entry_type = "SHORT"
                                    entry_price = next_candle["close"]
                                    entry_timestamp = next_candle["timestamp"]
                                    minutes_from_ny_open = (next_candle["timestamp"] - ny_open_utc).total_seconds() / 60
                                    entry_minute = int(minutes_from_ny_open)
                                    break
                
                # Información adicional para debugging
                rejection_found = entry_type == "SHORT"
                
                # FILTRO ADICIONAL: Evitar SHORT en tendencias alcistas fuertes
                if rejection_found and daily_trend == "bullish":
                    # Verificar si la tendencia alcista es muy fuerte (>1%)
                    strong_bullish = daily_change_pct > 1.0
                    if strong_bullish:
                        entry_type = "NO_ENTRY"
                        rejection_found = False
                        analysis_details["resistance_search"] = {
                            "resistance_zone": resistance_zone,
                            "current_price": current_price,
                            "distance_to_resistance": resistance_zone - current_price,
                            "rejection_found": False,
                            "reason_no_entry": f"Tendencia diaria alcista muy fuerte ({daily_change_pct:.2f}%), evitar SHORT"
                        }
                    else:
                        analysis_details["resistance_search"] = {
                            "resistance_zone": resistance_zone,
                            "current_price": current_price,
                            "distance_to_resistance": resistance_zone - current_price,
                            "rejection_found": rejection_found,
                        }
                else:
                    analysis_details["resistance_search"] = {
                        "resistance_zone": resistance_zone,
                        "current_price": current_price,
                        "distance_to_resistance": resistance_zone - current_price,
                        "rejection_found": rejection_found,
                    }
                
                if not rejection_found and "reason_no_entry" not in analysis_details.get("resistance_search", {}):
                    analysis_details["resistance_search"]["reason_no_entry"] = "Precio no rechazó desde la resistencia o siguió subiendo"
    
    return {
        "session_date": str(session_date),
        "ny_open_time": ny_open_utc.isoformat(),
        "direction_detected": direction,
        "entry_type": entry_type,
        "support_zone": support_zone,
        "resistance_zone": resistance_zone,
        "entry_price": entry_price,
        "entry_minute": entry_minute,
        "entry_timestamp": entry_timestamp.isoformat() if entry_timestamp else None,
        "analysis_details": analysis_details
    }


def format_decision_log(decision: Dict) -> str:
    """
    Formatea la decisión en un log legible.
    
    Args:
        decision: Dict retornado por analyze_session()
    
    Returns:
        String con el log formateado
    """
    log_lines = []
    log_lines.append("=" * 80)
    log_lines.append(f"ANÁLISIS DE SESIÓN: {decision['session_date']}")
    log_lines.append("=" * 80)
    ny_open_str = decision['ny_open_time']
    if ny_open_str:
        try:
            ny_open_dt = datetime.fromisoformat(ny_open_str.replace('Z', '+00:00'))
            spain_tz = pytz.timezone("Europe/Madrid")
            ny_open_spain = ny_open_dt.astimezone(spain_tz)
            hora_spain = ny_open_spain.strftime('%H:%M')
            log_lines.append(f"Apertura NY ({hora_spain} hora española): {decision['ny_open_time']}")
        except:
            log_lines.append(f"Apertura NY: {decision['ny_open_time']}")
    else:
        log_lines.append(f"Apertura NY: {decision['ny_open_time']}")
    log_lines.append("")
    
    # Dirección detectada
    direction = decision['direction_detected']
    if direction == "down":
        log_lines.append("📉 DIRECCIÓN DETECTADA: Precio BAJÓ en los primeros minutos")
        log_lines.append(f"   - Precio a apertura: ${decision['analysis_details']['price_at_open']:,.2f}")
        log_lines.append(f"   - Precio después de 5min: ${decision['analysis_details']['price_after_5min']:,.2f}")
        log_lines.append(f"   - Cambio: {decision['analysis_details']['price_change_pct']:.2f}%")
    elif direction == "up":
        log_lines.append("📈 DIRECCIÓN DETECTADA: Precio SUBIÓ en los primeros minutos")
        log_lines.append(f"   - Precio a apertura: ${decision['analysis_details']['price_at_open']:,.2f}")
        log_lines.append(f"   - Precio después de 5min: ${decision['analysis_details']['price_after_5min']:,.2f}")
        log_lines.append(f"   - Cambio: {decision['analysis_details']['price_change_pct']:.2f}%")
    else:
        log_lines.append("➡️  DIRECCIÓN DETECTADA: Movimiento LATERAL (sin dirección clara)")
    
    log_lines.append("")
    
    # Zonas de entrada
    if decision['support_zone']:
        log_lines.append(f"🎯 ZONA DE SOPORTE identificada: ${decision['support_zone']:,.2f}")
    
    if decision['resistance_zone']:
        log_lines.append(f"🎯 ZONA DE RESISTENCIA identificada: ${decision['resistance_zone']:,.2f}")
    
    log_lines.append("")
    
    # Decisión de entrada
    entry_type = decision['entry_type']
    if entry_type == "LONG":
        log_lines.append(f"✅ DECISIÓN: ENTRADA LONG detectada")
        log_lines.append(f"   - Precio de entrada: ${decision['entry_price']:,.2f}")
        log_lines.append(f"   - Minuto de entrada: {decision['entry_minute']} minutos después de la apertura NY")
        if decision['entry_timestamp']:
            try:
                from datetime import datetime as dt
                import pytz
                entry_ts = dt.fromisoformat(decision['entry_timestamp'].replace('Z', '+00:00'))
                spain_tz = pytz.timezone("Europe/Madrid")
                entry_spain = entry_ts.astimezone(spain_tz)
                log_lines.append(f"   - Timestamp (UTC): {decision['entry_timestamp']}")
                log_lines.append(f"   - Hora española: {entry_spain.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                log_lines.append(f"   - Timestamp: {decision['entry_timestamp']}")
        else:
            log_lines.append(f"   - Timestamp: No disponible")
        log_lines.append(f"   - Zona de soporte: ${decision['support_zone']:,.2f}")
    elif entry_type == "SHORT":
        log_lines.append(f"✅ DECISIÓN: ENTRADA SHORT detectada")
        log_lines.append(f"   - Precio de entrada: ${decision['entry_price']:,.2f}")
        log_lines.append(f"   - Minuto de entrada: {decision['entry_minute']} minutos después de la apertura NY")
        if decision['entry_timestamp']:
            # Convertir timestamp a hora española para mostrar
            try:
                from datetime import datetime as dt
                import pytz
                entry_ts = dt.fromisoformat(decision['entry_timestamp'].replace('Z', '+00:00'))
                spain_tz = pytz.timezone("Europe/Madrid")
                entry_spain = entry_ts.astimezone(spain_tz)
                log_lines.append(f"   - Timestamp (UTC): {decision['entry_timestamp']}")
                log_lines.append(f"   - Hora española: {entry_spain.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                log_lines.append(f"   - Timestamp: {decision['entry_timestamp']}")
        else:
            log_lines.append(f"   - Timestamp: No disponible")
        log_lines.append(f"   - Zona de resistencia: ${decision['resistance_zone']:,.2f}")
    else:
        log_lines.append("⏸️  DECISIÓN: NO HAY ENTRADA")
        if 'error' in decision['analysis_details']:
            log_lines.append(f"   Razón: {decision['analysis_details']['error']}")
        else:
            log_lines.append("   Razón: No se detectó rebote/rechazo válido o movimiento lateral")
    
    log_lines.append("=" * 80)
    
    return "\n".join(log_lines)

