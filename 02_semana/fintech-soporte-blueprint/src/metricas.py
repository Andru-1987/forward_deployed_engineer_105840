"""Entregable 3: las 4 metricas (calidad, seguridad, costo, latencia).

Leccion FDE: "funciona" no es una metrica. Sin numeros no hay forma de decidir
si la version nueva es mejor ni cuando hacer rollback.

- Calidad:   % de turnos que validan en el 1er intento (+ groundedness offline con Golden Dataset).
- Seguridad: cantidad de fallos de seguridad (reembolso sin HITL, fuga de PII). Meta: 0.
- Costo:     USD promedio por turno (incluye reintentos).
- Latencia:  P95 end-to-end en ms.
"""

import math
from dataclasses import dataclass
from typing import Any, Sequence

from src.config import ObjetivosConfig


@dataclass(frozen=True)
class RegistroTurno:
    version: str                 # "v1" (estable) o "v2" (canary)
    ok: bool
    primer_intento: bool         # valido sin necesitar reintento
    costo_usd: float
    latencia_ms: int
    error_validacion: bool       # agoto reintentos por ValidationError
    error_http: bool             # 429 / 5xx no recuperado
    fallo_seguridad: bool = False

    @classmethod
    def desde_resultado(cls, version: str, resultado: dict[str, Any]) -> "RegistroTurno":
        ok = resultado["ok"]
        tel = resultado["telemetria"]
        return cls(
            version=version,
            ok=ok,
            primer_intento=ok and resultado["intento"] == 1,
            costo_usd=tel["costo_usd"],
            latencia_ms=tel["latencia_ms"],
            error_validacion=resultado.get("etapa") == "VALIDACION_SALIDA",
            error_http=resultado.get("etapa") == "INFRAESTRUCTURA_API",
        )


def percentil(valores: Sequence[float], p: float) -> float:
    """Percentil por rango mas cercano. El promedio esconde la cola; P95 la muestra."""
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return ordenados[max(0, math.ceil(p / 100 * len(ordenados)) - 1)]


def resumir(registros: Sequence[RegistroTurno]) -> dict[str, float]:
    n = len(registros) or 1  # sin registros: todo en 0, sin dividir por cero

    def tasa(campo: str) -> float:
        return sum(getattr(r, campo) for r in registros) / n

    return {
        "n": len(registros),
        "validez_primer_intento": tasa("primer_intento"),
        "costo_promedio_usd": tasa("costo_usd"),
        "latencia_p95_ms": percentil([r.latencia_ms for r in registros], 95),
        "tasa_error_validacion": tasa("error_validacion"),
        "tasa_error_http": tasa("error_http"),
        "fallos_seguridad": sum(r.fallo_seguridad for r in registros),
    }


def incumplimientos(resumen: dict[str, float], objetivos: ObjetivosConfig) -> list[str]:
    """Lista legible de metas no cumplidas (vacia = todo en verde)."""
    fallas = []
    if resumen["validez_primer_intento"] < objetivos.validez_primer_intento_min:
        fallas.append("calidad: validez en primer intento bajo la meta")
    if resumen["fallos_seguridad"] > 0:
        fallas.append("seguridad: hay fallos de seguridad (meta: 0)")
    if resumen["costo_promedio_usd"] > objetivos.costo_promedio_max_usd:
        fallas.append("costo: promedio por turno sobre la meta")
    if resumen["latencia_p95_ms"] > objetivos.latencia_p95_max_ms:
        fallas.append("latencia: P95 sobre la meta")
    return fallas
