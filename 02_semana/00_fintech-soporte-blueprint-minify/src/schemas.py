"""Deliverable 1: LLM output contract (Pydantic schema).

The LLM is probabilistic, the system cannot be: anything that breaks this
contract never reaches the core.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, model_validator

from src.config import ReglasNegocioConfig


class IntencionSoporte(str, Enum):
    consulta_politica = "consulta_politica"
    estado_ticket = "estado_ticket"
    reembolso_parcial = "reembolso_parcial"
    fuera_de_dominio = "fuera_de_dominio"


class SalidaFintech(BaseModel):
    intencion: IntencionSoporte
    fuente_politica: Optional[str] = Field(
        default=None, description="Policy section cited, or null if not applicable"
    )
    ticket_id: Optional[str] = Field(
        default=None, pattern=r"^TKT-\d{6}$", description="Ticket id, format TKT-123456"
    )
    monto_reembolso_usd: float = Field(default=0.0, ge=0.0)
    requiere_aprobacion_humana: bool
    respuesta_usuario: str = Field(..., min_length=15)
    confianza: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validar_reglas_fintech(self, info: ValidationInfo) -> "SalidaFintech":
        # Business rules arrive via `context`: no globals, testable with any threshold.
        reglas: ReglasNegocioConfig = info.context["reglas"]
        es_reembolso = self.intencion == IntencionSoporte.reembolso_parcial

        # Money: always a human, positive amount, under the cap.
        if es_reembolso:
            if self.monto_reembolso_usd <= 0:
                raise ValueError("reembolso_parcial exige monto_reembolso_usd > 0")
            if self.monto_reembolso_usd > reglas.monto_maximo_reembolso_usd:
                raise ValueError(f"monto supera el maximo de {reglas.monto_maximo_reembolso_usd} USD")
            if not self.requiere_aprobacion_humana:
                raise ValueError("reembolso_parcial debe marcar requiere_aprobacion_humana=true")
        elif self.monto_reembolso_usd > 0:
            raise ValueError("Solo reembolso_parcial admite monto_reembolso_usd > 0")

        if self.intencion == IntencionSoporte.consulta_politica and not self.fuente_politica:
            raise ValueError("consulta_politica exige fuente_politica")
        if self.intencion == IntencionSoporte.estado_ticket and not self.ticket_id:
            raise ValueError("estado_ticket exige ticket_id")

        # Out of domain or low confidence: no improvising, escalate to a human.
        necesita_humano = (
            self.intencion == IntencionSoporte.fuera_de_dominio
            or self.confianza < reglas.umbral_confianza_hitl
        )
        if necesita_humano and not self.requiere_aprobacion_humana:
            raise ValueError("fuera_de_dominio o confianza baja exigen revision humana")
        return self


def validar_salida(contenido_json: str, reglas: ReglasNegocioConfig) -> SalidaFintech:
    """Single validation entry point. Raises ValidationError (also on malformed JSON)."""
    return SalidaFintech.model_validate_json(contenido_json, context={"reglas": reglas})


def resumir_errores(error: ValidationError) -> list[dict[str, str]]:
    """loc + msg only: guides the retry without exposing the traceback."""
    return [
        {"campo": " -> ".join(map(str, e["loc"])) or "(objeto)", "motivo": e["msg"]}
        for e in error.errors()
    ]
