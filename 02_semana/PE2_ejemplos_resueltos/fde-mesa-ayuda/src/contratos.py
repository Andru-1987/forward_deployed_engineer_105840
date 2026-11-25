"""Contrato de datos de la Mesa de Ayuda IT: qué entra al motor y qué tiene que salir.

Historia de usuario (PE1):
    Como técnico de la mesa de ayuda, quiero que cada pedido de un empleado llegue
    clasificado, con prioridad y con los primeros pasos sugeridos, para resolver
    rápido lo simple y pasar a soporte N2 solo lo urgente o lo que no está claro.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Entrada(BaseModel):
    """Lo que manda el empleado."""

    # Regla 1 (formato con patrón): el legajo tiene el formato EMP-1234.
    legajo: str = Field(pattern=r"^EMP-\d{4}$", description="Legajo del empleado, por ejemplo EMP-0142")
    # Regla 2 (largo mínimo): con menos de 15 caracteres no hay contexto para ayudar.
    mensaje: str = Field(min_length=15, max_length=1500, description="Pedido del empleado")


class TipoIncidente(str, Enum):
    """Regla 3 (valores permitidos): solo estos tipos existen en la mesa de ayuda."""

    hardware = "hardware"
    software = "software"
    accesos = "accesos"
    red = "red"
    fuera_de_alcance = "fuera_de_alcance"


class Prioridad(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"


class Salida(BaseModel):
    """Lo que el motor le devuelve al técnico."""

    model_config = ConfigDict(extra="forbid")  # no se aceptan campos inventados

    tipo: TipoIncidente = Field(description="Tipo de incidente")
    prioridad: Prioridad = Field(description="alta si impide trabajar a una o más personas")
    resumen: str = Field(min_length=10, max_length=120, description="Resumen en una oración")
    # Regla 4 (largo de una lista): entre 1 y 4 pasos concretos.
    pasos_sugeridos: list[str] = Field(
        min_length=1, max_length=4, description="Primeros pasos que puede probar el técnico"
    )
    escalar_a_n2: bool = Field(description="True si tiene que intervenir soporte N2")
    # Regla 5 (rango): la confianza va de 0 a 1.
    confianza: float = Field(ge=0, le=1, description="Qué tan seguro está el modelo, de 0 a 1")

    # Regla 6 (regla de negocio que cruza campos).
    @model_validator(mode="after")
    def revisar_escalamiento(self) -> "Salida":
        if self.prioridad == Prioridad.alta and not self.escalar_a_n2:
            raise ValueError("si la prioridad es 'alta', escalar_a_n2 debe ser true")
        if self.confianza < 0.5 and not self.escalar_a_n2:
            raise ValueError("si la confianza es menor a 0.5, escalar_a_n2 debe ser true")
        return self
