import httpx
from groq import RateLimitError

from src.motor import procesar_ticket
from tests.conftest import ENTRADA_OK, ClienteFalso, salida


def test_exito_con_telemetria(config):
    r = procesar_ticket(ENTRADA_OK, ClienteFalso([salida()]), config)
    assert r["ok"] and r["intento"] == 1
    assert r["tokens"] == {"entrada": 1000, "salida": 200}
    assert r["costo_usd"] == 0.000748  # 1000*0.59/1e6 + 200*0.79/1e6


def test_reintento_guiado_con_campo_fallido(config):
    malo = salida(monto_reintegro_sugerido=240.0)  # sobre umbral sin supervisor
    cliente = ClienteFalso([malo, salida()])
    r = procesar_ticket(ENTRADA_OK, cliente, config)
    assert r["ok"] and r["intento"] == 2
    assert "CORRECCION REQUERIDA" in cliente.llamadas[1][1]["content"]
    assert r["tokens"]["entrada"] == 2000


def test_error_estructurado_tras_un_unico_reintento(config):
    malo = salida(monto_reintegro_sugerido=240.0)
    cliente = ClienteFalso([malo, malo])
    r = procesar_ticket(ENTRADA_OK, cliente, config)
    assert (r["ok"], r["etapa"], r["intento"]) == (False, "VALIDACION_SALIDA", 2)
    assert r["errores"][0]["campo"] == "(json_completo)" and len(cliente.llamadas) == 2


def test_entrada_invalida_no_llama_a_la_api(config):
    cliente = ClienteFalso([])
    r = procesar_ticket({**ENTRADA_OK, "ticket_id": "mal"}, cliente, config)
    assert r["etapa"] == "VALIDACION_ENTRADA" and r["costo_usd"] == 0.0 and cliente.llamadas == []


def test_error_de_cuota_no_rompe(config):
    class Limitado:
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    resp = httpx.Response(429, request=httpx.Request("POST", "http://x"))
                    raise RateLimitError("limite", response=resp, body=None)

    r = procesar_ticket(ENTRADA_OK, Limitado, config)
    assert (r["ok"], r["etapa"]) == (False, "INFRAESTRUCTURA_API")
