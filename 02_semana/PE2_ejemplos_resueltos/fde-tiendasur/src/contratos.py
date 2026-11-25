"""Contrato de datos de TiendaSur: qué entra al motor y qué tiene que salir.

Historia de usuario (PE1):
    Como agente de atención de TiendaSur, quiero que cada consulta llegue
    clasificada y con una respuesta sugerida, para contestar más rápido y
    derivar a una persona solo los casos que lo necesitan.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Entrada(BaseModel):
    """Lo que el cliente nos manda."""

    # Regla 1 (largo mínimo y máximo): no pagamos tokens por mensajes vacíos.
    consulta: str = Field(
        min_length=10,
        max_length=1000,
        description="Mensaje del cliente, tal como lo escribió",
    )
    # Regla 2 (formato con patrón): los pedidos tienen el formato PED-12345.
    # Es opcional porque no todas las consultas mencionan un pedido.
    id_pedido: str | None = Field(
        default=None,
        pattern=r"^PED-\d{5}$",
        description="Número de pedido, por ejemplo PED-10234",
    )
    # # Regla 3 (contenido real): rechaza mensajes hechos solo de espacios o símbolos.
    # # (que pasarían min_length=10) y limpia espacios al inicio y al final.
    # @field_validator("consulta")
    # @classmethod
    # def validar_contenido_real(cls, valor: str) -> str:
    #     texto = valor.strip()
    #     if len(texto) < 10:
    #         raise ValueError(
    #             "la consulta debe tener al menos 10 caracteres reales sin contar espacios"
    #         )
    #     if not any(caracter.isalpha() for caracter in texto):
    #         raise ValueError(
    #             "la consulta debe incluir texto legible, no solo números o símbolos"
    #         )
    #     return texto


class Categoria(str, Enum):
    """Regla 3 (valores permitidos): el modelo no puede inventar categorías."""

    estado_pedido = "estado_pedido"
    cambio = "cambio"
    devolucion = "devolucion"
    otra = "otra"


class Salida(BaseModel):
    """Lo que el motor le devuelve al agente de atención."""

    # extra="forbid": si el modelo agrega campos que no pedimos, la salida es inválida.
    model_config = ConfigDict(extra="forbid")

    categoria: Categoria = Field(description="Tema principal de la consulta")
    respuesta_sugerida: str = Field(
        min_length=20,
        max_length=600,
        description="Respuesta amable y breve, en español, para el cliente",
    )
    requiere_humano: bool = Field(
        description="True si una persona tiene que revisar el caso"
    )
    # Regla 4 (rango): la confianza va de 0 a 1.
    confianza: float = Field(
        ge=0,
        le=1,
        description="Qué tan seguro está el modelo, de 0 a 1",
    )

    # Regla 5 (regla de negocio que cruza campos).
    @model_validator(mode="after")
    def revisar_derivacion(self) -> "Salida":
        if self.categoria == Categoria.otra and not self.requiere_humano:
            raise ValueError("si la categoria es 'otra', requiere_humano debe ser true")
        if self.confianza < 0.6 and not self.requiere_humano:
            raise ValueError("si la confianza es menor a 0.6, requiere_humano debe ser true")
        return self
