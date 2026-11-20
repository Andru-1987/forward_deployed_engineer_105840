"""Contratos de datos: Entrada y Salida del motor (derivados de la historia de usuario de PE1).

Leccion FDE: el LLM es probabilistico, el CRM no. Estos contratos son la frontera:
lo que no los cumple no entra al sistema ni gasta tokens.
"""

from enum import Enum

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, model_validator

from src.config import ReglasNegocioConfig


class RolOperador(str, Enum):
    analista_n1 = "analista_n1"
    supervisor_n2 = "supervisor_n2"


class EstadoTriaje(str, Enum):
    elegible_borrador = "elegible_borrador"
    no_elegible = "no_elegible"
    faltan_datos = "faltan_datos"
    requiere_revision_manual = "requiere_revision_manual"


class Entrada(BaseModel):
    # Patron: valida el formato del ticket antes de gastar tokens.
    ticket_id: str = Field(pattern=r"^TCK-\d{4,6}$", description="ID anonimizado del ticket")
    # Largo minimo: evita pagar por mensajes vacios o sin contexto.
    mensaje_cliente: str = Field(min_length=15, description="Descripcion del reclamo")
    # Rango: no existen dias negativos de vigencia.
    dias_desde_entrega: int = Field(ge=0, description="Dias desde la recepcion")
    monto_pagado_usd: float = Field(gt=0, description="Monto abonado en USD")
    tiene_factura_y_foto: bool = Field(description="Adjunto comprobante y foto")
    rol_ejecutor: RolOperador = RolOperador.analista_n1


class Salida(BaseModel):
    estado: EstadoTriaje
    clausula_citada: str = Field(min_length=5, description="Articulo citado o 'N/A'")
    monto_reintegro_sugerido: float = Field(ge=0.0)
    requiere_aprobacion_supervisor: bool
    respuesta_sugerida: str = Field(min_length=15)
    confianza: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validar_reglas_negocio(self, info: ValidationInfo) -> "Salida":
        # El umbral llega por `context`: nada hardcodeado ni global, y es testeable.
        umbral = info.context["reglas"].umbral_aprobacion_supervisor_usd
        if self.monto_reintegro_sugerido > umbral and not self.requiere_aprobacion_supervisor:
            raise ValueError(f"Todo reintegro mayor a {umbral} USD exige requiere_aprobacion_supervisor=True")
        # Solo un caso elegible puede sugerir dinero (faltan datos, no aplica o revision manual: 0.0).
        if self.estado != EstadoTriaje.elegible_borrador and self.monto_reintegro_sugerido > 0:
            raise ValueError(f"Si el estado es {self.estado.value}, monto_reintegro_sugerido debe ser 0.0")
        return self


def validar_salida(contenido_json: str, reglas: ReglasNegocioConfig) -> Salida:
    """Unico punto para validar la salida: garantiza que el context siempre exista."""
    return Salida.model_validate_json(contenido_json, context={"reglas": reglas})


def formatear_errores(err: ValidationError) -> list[dict[str, str]]:
    """Ruta exacta (loc) y motivo (msg): sirven para el log y para guiar el reintento."""
    return [
        {"campo": " -> ".join(map(str, e["loc"])) or "(json_completo)", "tipo": e["type"], "mensaje": e["msg"]}
        for e in err.errors()
    ]
