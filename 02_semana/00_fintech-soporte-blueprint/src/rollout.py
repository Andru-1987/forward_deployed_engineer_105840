"""Entregable 5: rollout progresivo (canary 5%), comparacion y rollback.

Leccion FDE: nunca se lanza una version nueva al 100%. Se expone a un grupo
chico, se compara contra la version estable con los mismos numeros y se define
ANTES del lanzamiento cuando se vuelve atras.
"""

import hashlib
from typing import Sequence

from src.config import UmbralesRollbackConfig
from src.metricas import RegistroTurno, resumir


def elegir_version(user_id: str, porcentaje_canary: int) -> str:
    """Hash consistente: el mismo usuario siempre cae en la misma version.

    Si fuera aleatorio por request, un usuario veria respuestas distintas en la
    misma conversacion y no podriamos comparar cohortes limpias.
    """
    digest = hashlib.sha256(user_id.encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 100
    return "v2" if bucket < porcentaje_canary else "v1"


def evaluar_rollback(
    registros: Sequence[RegistroTurno], umbrales: UmbralesRollbackConfig
) -> list[str]:
    """Devuelve los motivos de rollback (lista vacia = el canary sigue).

    Recibe TODOS los registros de la ventana (ej. ultimos 15 min) y compara v2 vs v1.
    """
    canary = [r for r in registros if r.version == "v2"]
    base = [r for r in registros if r.version == "v1"]
    if not canary:
        return []
    c, b = resumir(canary), resumir(base)

    motivos = []
    if c["fallos_seguridad"] >= 1:  # un solo fallo de seguridad basta
        motivos.append("seguridad: al menos 1 fallo (reembolso sin HITL o fuga de PII)")
    if c["tasa_error_validacion"] > umbrales.tasa_validation_error_max:
        motivos.append("calidad: tasa de ValidationError sobre el umbral")
    if c["latencia_p95_ms"] > umbrales.latencia_p95_max_ms:
        motivos.append("latencia: P95 sobre el umbral")
    if c["tasa_error_http"] > umbrales.tasa_error_http_max:
        motivos.append("infraestructura: errores HTTP no recuperados sobre el umbral")
    if b["costo_promedio_usd"] > 0:
        incremento = c["costo_promedio_usd"] / b["costo_promedio_usd"] - 1
        if incremento > umbrales.incremento_costo_max:
            motivos.append(f"costo: +{incremento:.0%} frente a v1")
    return motivos
