from src.guardrails import Accion, decidir_accion, enmascarar_pii
from src.schemas import validar_salida
from tests.conftest import salida


def test_enmascara_pii_y_respeta_ticket():
    texto = "DNI 12345678, tarjeta 4111 1111 1111 1111, mail a@b.com, ticket TKT-482910"
    out = enmascarar_pii(texto)
    assert "12345678" not in out and "4111" not in out and "a@b.com" not in out
    assert "TKT-482910" in out


def test_cbu_no_se_confunde_con_tarjeta():
    assert enmascarar_pii("CBU 0170099220000067797370") == "CBU [CBU]"


def test_acciones(config):
    r = config.reglas_negocio
    reembolso = validar_salida(salida(), r)
    assert decidir_accion(reembolso, r) == Accion.ENCOLAR_APROBACION
    lectura = validar_salida(
        salida(intencion="estado_ticket", monto_reembolso_usd=0, requiere_aprobacion_humana=False), r)
    assert decidir_accion(lectura, r) == Accion.RESPONDER
    ajeno = validar_salida(
        salida(intencion="fuera_de_dominio", ticket_id=None, monto_reembolso_usd=0), r)
    assert decidir_accion(ajeno, r) == Accion.DERIVAR_A_HUMANO
