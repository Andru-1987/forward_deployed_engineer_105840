import pytest
from pydantic import ValidationError

from src.schemas import validar_salida
from tests.conftest import salida


def test_reembolso_valido(config):
    assert validar_salida(salida(), config.reglas_negocio).monto_reembolso_usd == 150.0


@pytest.mark.parametrize(
    "cambios",
    [
        {"requiere_aprobacion_humana": False},          # evasion de HITL
        {"monto_reembolso_usd": 0},                     # reembolso sin monto
        {"monto_reembolso_usd": 999999},                # sobre el tope
        {"ticket_id": "TKT-1; DROP TABLE"},             # ID malformado / inyeccion
        {"intencion": "estado_ticket", "ticket_id": None, "monto_reembolso_usd": 0},
        {"intencion": "consulta_politica", "monto_reembolso_usd": 0},  # sin fuente
        {"intencion": "estado_ticket", "monto_reembolso_usd": 10},     # monto en lectura
        {"intencion": "fuera_de_dominio", "monto_reembolso_usd": 0,
         "requiere_aprobacion_humana": False},
        {"confianza": 0.3, "requiere_aprobacion_humana": False},
    ],
)
def test_salidas_invalidas(config, cambios):
    with pytest.raises(ValidationError):
        validar_salida(salida(**cambios), config.reglas_negocio)


def test_json_truncado(config):
    with pytest.raises(ValidationError):
        validar_salida('{"intencion": "reembolso_par', config.reglas_negocio)
