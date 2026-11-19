import json
from types import SimpleNamespace

import pytest

from src.config import cargar_config


@pytest.fixture(scope="session")
def config():
    return cargar_config()


class ClienteFalso:
    """Imita groq.Groq: devuelve respuestas guionadas, sin red ni API key."""

    def __init__(self, respuestas: list[str]):
        self._respuestas = list(respuestas)
        self.llamadas: list[list[dict]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.llamadas.append(kwargs["messages"])
        contenido = self._respuestas.pop(0)
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=200),
            choices=[SimpleNamespace(message=SimpleNamespace(content=contenido))],
        )


def salida(**cambios) -> str:
    base = {
        "intencion": "reembolso_parcial",
        "fuente_politica": None,
        "ticket_id": "TKT-482910",
        "monto_reembolso_usd": 150.0,
        "requiere_aprobacion_humana": True,
        "respuesta_usuario": "Registramos tu pedido de reembolso para revision.",
        "confianza": 0.9,
    }
    return json.dumps({**base, **cambios})
