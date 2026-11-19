"""API publica del paquete: lo unico que `main.py` necesita importar."""

from src.config import Secrets, cargar_config
from src.metricas import RegistroTurno, resumir
from src.motor import ejecutar_turno
from src.rollout import elegir_version

__all__ = ["RegistroTurno", "Secrets", "cargar_config", "ejecutar_turno", "elegir_version", "resumir"]
