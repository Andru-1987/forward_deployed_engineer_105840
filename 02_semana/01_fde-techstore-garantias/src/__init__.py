"""API publica del paquete: lo unico que `main.py` necesita importar."""

from src.casos import CASOS
from src.config import Secrets, cargar_config
from src.medicion import resumir
from src.motor import procesar_ticket

__all__ = ["CASOS", "Secrets", "cargar_config", "procesar_ticket", "resumir"]
