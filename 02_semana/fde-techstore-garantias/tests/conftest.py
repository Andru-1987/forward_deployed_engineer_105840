import json
from types import SimpleNamespace

import pytest

from src.config import cargar_config


@pytest.fixture(scope="session")
def config():
    return cargar_config()


class ClienteFalso:
    """Imita groq.Groq con respuestas guionadas: sin red ni API key."""

    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.llamadas.append(kwargs["messages"])
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=200),
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._respuestas.pop(0)))],
        )


def salida(**cambios) -> str:
    base = {"estado": "elegible_borrador", "clausula_citada": "Art. 3 Politica General",
            "monto_reintegro_sugerido": 35.0, "requiere_aprobacion_supervisor": False,
            "respuesta_sugerida": "Procedemos con el borrador de devolucion.", "confianza": 0.9}
    return json.dumps({**base, **cambios})


ENTRADA_OK = {"ticket_id": "TCK-1001", "mensaje_cliente": "Los auriculares dejaron de sonar a los 10 dias.",
              "dias_desde_entrega": 10, "monto_pagado_usd": 35.0, "tiene_factura_y_foto": True}
