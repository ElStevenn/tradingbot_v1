"""
Logger simplificado para el bot en vivo.
Escribe eventos en formato JSONL.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class Logger:
    """Logger para eventos del bot en vivo."""
    
    def __init__(self, log_path: str = "bot_log.jsonl"):
        """
        Inicializa el logger.
        
        Args:
            log_path: Ruta al archivo de log
        """
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = open(self.log_path, 'a', encoding='utf-8')
    
    def _write(self, event_type: str, data: Dict[str, Any]):
        """Escribe un evento al log."""
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            **data
        }
        self.log_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.log_file.flush()
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Registra un evento general."""
        self._write(event_type, data)
    
    def log_error(self, message: str, error: Exception = None):
        """Registra un error."""
        error_data = {
            "message": message,
        }
        if error:
            error_data["error_type"] = type(error).__name__
            error_data["error_details"] = str(error)
        self._write("error", error_data)
    
    def close(self):
        """Cierra el archivo de log."""
        if self.log_file:
            self.log_file.close()

