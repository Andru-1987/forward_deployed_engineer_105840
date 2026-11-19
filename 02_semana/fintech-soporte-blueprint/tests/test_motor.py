from groq import RateLimitError
import httpx

from src.motor import ejecutar_turno
from tests.conftest import ClienteFalso, salida

PROMPT = "prompts/triaje_v1.txt"


def test_primer_intento_ok_con_telemetria(config):
    cliente = ClienteFalso([salida()])
    r = ejecutar_turno("reembolso de 150", cliente, config, PROMPT)
    assert r["ok"] and r["intento"] == 1
    # 1000*0.59/1e6 + 200*0.79/1e6
    assert r["telemetria"]["costo_usd"] == 0.000748


def test_reintento_guiado_suma_costo(config):
    cliente = ClienteFalso([salida(requiere_aprobacion_humana=False), salida()])
    r = ejecutar_turno("reembolso de 150", cliente, config, PROMPT)
    assert r["ok"] and r["intento"] == 2
    assert "ERROR DE VALIDACION" in cliente.llamadas[1][1]["content"]
    assert r["telemetria"]["tokens_in"] == 2000


def test_validacion_agotada_no_expone_traceback(config):
    malo = salida(requiere_aprobacion_humana=False)
    r = ejecutar_turno("x", ClienteFalso([malo, malo]), config, PROMPT)
    assert r["ok"] is False and r["etapa"] == "VALIDACION_SALIDA"
    assert "Traceback" not in str(r)


def test_pii_no_sale_hacia_el_proveedor(config):
    cliente = ClienteFalso([salida()])
    ejecutar_turno("mi DNI es 12345678", cliente, config, PROMPT)
    assert "12345678" not in cliente.llamadas[0][1]["content"]


def test_rate_limit_se_controla(config):
    class Limitado:
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    resp = httpx.Response(429, request=httpx.Request("POST", "http://x"))
                    raise RateLimitError("limite", response=resp, body=None)

    r = ejecutar_turno("x", Limitado, config, PROMPT)
    assert (r["ok"], r["etapa"], r["detalle"]) == (False, "INFRAESTRUCTURA_API", "RateLimitError")
    assert r["telemetria"]["costo_usd"] == 0.0


def test_accion_hitl_en_el_resultado(config):
    r = ejecutar_turno("reembolso de 150", ClienteFalso([salida()]), config, PROMPT)
    assert r["accion"] == "encolar_aprobacion"
