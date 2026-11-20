"""Guardrails de ENTRADA (etapa Prompting) y gate de SALIDA (etapa Post-procesado).

Leccion FDE: nunca confies en una sola barrera. El schema ya fuerza HITL en
reembolsos, pero aqui lo verificamos otra vez, de forma independiente, antes de
ejecutar cualquier accion (defensa en profundidad).
"""

import re
from enum import Enum

from src.config import ReglasNegocioConfig
from src.schemas import IntencionSoporte, SalidaFintech

# Orden importa: de lo mas largo a lo mas corto, para que un CBU (22 digitos)
# no sea tomado como tarjeta o DNI.
_PATRONES_PII = [
    ("CBU", re.compile(r"\b\d{22}\b")),
    ("TARJETA", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("DNI", re.compile(r"\b\d{7,8}\b")),
]


def enmascarar_pii(texto: str) -> str:
    """Fallo mitigado: 'Exposicion de PII' hacia la API externa del LLM."""
    for etiqueta, patron in _PATRONES_PII:
        texto = patron.sub(f"[{etiqueta}]", texto)
    return texto


class Accion(str, Enum):
    RESPONDER = "responder"                  # lectura pura, sin riesgo
    ENCOLAR_APROBACION = "encolar_aprobacion"  # un humano decide antes de actuar
    DERIVAR_A_HUMANO = "derivar_a_humano"    # el bot no debe contestar


def decidir_accion(salida: SalidaFintech, reglas: ReglasNegocioConfig) -> Accion:
    """Entregable 4: que requiere Human-in-the-Loop.

    - reembolso_parcial: 100% de los casos -> aprobacion de un operador financiero.
    - fuera_de_dominio o confianza baja: se deriva a un agente con el resumen.
    - consulta_politica y estado_ticket (propio): lectura pura, sin aprobacion.
    """
    if salida.intencion == IntencionSoporte.reembolso_parcial:
        return Accion.ENCOLAR_APROBACION
    if (
        salida.intencion == IntencionSoporte.fuera_de_dominio
        or salida.confianza < reglas.umbral_confianza_hitl
    ):
        return Accion.DERIVAR_A_HUMANO
    return Accion.RESPONDER
