"""Offline tests: no network, no API key (fake client)."""

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.config import ReglasNegocioConfig, cargar_config
from src.guardrails import enmascarar_pii
from src.motor import ejecutar_turno
from src.rollout import elegir_version
from src.schemas import validar_salida

REGLAS = ReglasNegocioConfig(monto_maximo_reembolso_usd=5000.0, umbral_confianza_hitl=0.75)

REEMBOLSO = {
    "intencion": "reembolso_parcial",
    "monto_reembolso_usd": 150.0,
    "requiere_aprobacion_humana": True,
    "respuesta_usuario": "Tu solicitud de reembolso fue registrada.",
    "confianza": 0.95,
}


def test_reembolso_valido():
    assert validar_salida(json.dumps(REEMBOLSO), REGLAS).monto_reembolso_usd == 150.0


def test_reembolso_sin_humano_se_rechaza():
    with pytest.raises(ValidationError):
        validar_salida(json.dumps({**REEMBOLSO, "requiere_aprobacion_humana": False}), REGLAS)


def test_reembolso_sobre_tope_se_rechaza():
    with pytest.raises(ValidationError):
        validar_salida(json.dumps({**REEMBOLSO, "monto_reembolso_usd": 9999}), REGLAS)


def test_enmascara_pii():
    assert enmascarar_pii("DNI 12345678 mail a@b.com") == "DNI [DNI] mail [EMAIL]"


def test_canary_es_consistente():
    assert elegir_version("user-1", 5) == elegir_version("user-1", 5)
    assert elegir_version("user-1", 0) == "v1"
    assert elegir_version("user-1", 100) == "v2"


class ClienteFalso:
    """Returns the queued contents in order, one per call."""

    def __init__(self, contenidos):
        self.contenidos = list(contenidos)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **_):
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50),
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.contenidos.pop(0)))],
        )


def test_reintento_guiado_recupera():
    config = cargar_config()
    cliente = ClienteFalso(["{no es json", json.dumps(REEMBOLSO)])
    r = ejecutar_turno("reembolso", cliente, config, config.rollout.prompt_estable)
    assert r["ok"] and r["intento"] == 2
    assert r["telemetria"]["tokens_in"] == 200  # retry is billed


def test_agota_reintentos():
    config = cargar_config()
    cliente = ClienteFalso(["{x", "{y"])
    r = ejecutar_turno("hola", cliente, config, config.rollout.prompt_estable)
    assert not r["ok"] and r["etapa"] == "VALIDACION_SALIDA"
