import pytest
from pydantic import ValidationError

from src.schemas import Entrada, validar_salida
from tests.conftest import ENTRADA_OK, salida


@pytest.mark.parametrize("cambio", [
    {"ticket_id": "XXX-1"}, {"mensaje_cliente": "corto"},
    {"dias_desde_entrega": -1}, {"monto_pagado_usd": 0}, {"rol_ejecutor": "gerente"},
])
def test_entrada_invalida(cambio):
    with pytest.raises(ValidationError):
        Entrada.model_validate({**ENTRADA_OK, **cambio})


def test_salida_valida(config):
    assert validar_salida(salida(), config.reglas_negocio).estado.value == "elegible_borrador"


@pytest.mark.parametrize("cambios", [
    {"monto_reintegro_sugerido": 240.0},                      # sobre umbral sin supervisor
    {"estado": "faltan_datos", "monto_reintegro_sugerido": 10.0},
    {"estado": "requiere_revision_manual", "monto_reintegro_sugerido": 10.0},
    {"estado": "inventado"}, {"confianza": 1.5},
])
def test_salida_invalida(config, cambios):
    with pytest.raises(ValidationError):
        validar_salida(salida(**cambios), config.reglas_negocio)


def test_sobre_umbral_con_supervisor_es_valido(config):
    assert validar_salida(salida(monto_reintegro_sugerido=240.0, requiere_aprobacion_supervisor=True),
                          config.reglas_negocio)
