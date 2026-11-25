"""Pruebas sin API key: corren con  uv run pytest"""

import pytest
from pydantic import ValidationError

from contratos import Entrada, Salida
from modelo_simulado import ModeloSimulado
from motor import procesar
from proveedores import PROVEEDORES, a_formato_google, clasificar_error, datos_proveedor

BIEN = ('{"categoria": "cambio", "respuesta_sugerida": "Podés cambiar el talle '
        'desde Mis pedidos o en cualquier sucursal.", "requiere_humano": false, '
        '"confianza": 0.9}')
MAL = '{"categoria": "reclamo", "respuesta_sugerida": "Ok", "requiere_humano": false, "confianza": 1.4}'
CONSULTA = {"consulta": "Necesito cambiar el talle de una remera", "id_pedido": "PED-10577"}


# --- Contrato ----------------------------------------------------------------
def test_entrada_rechaza_id_con_formato_incorrecto():
    with pytest.raises(ValidationError):
        Entrada(consulta="Necesito cambiar el talle", id_pedido="10577")


def test_entrada_rechaza_consulta_demasiado_corta():
    with pytest.raises(ValidationError):
        Entrada(consulta="hola")


def test_salida_rechaza_categoria_inventada_y_confianza_fuera_de_rango():
    with pytest.raises(ValidationError) as info:
        Salida.model_validate_json(MAL)
    campos = {e["loc"][0] for e in info.value.errors()}
    assert {"categoria", "respuesta_sugerida", "confianza"} <= campos


def test_regla_de_negocio_otra_exige_humano():
    with pytest.raises(ValidationError):
        Salida(categoria="otra", respuesta_sugerida="Esta consulta no es sobre un pedido.",
               requiere_humano=False, confianza=0.9)


def test_salida_rechaza_campos_inventados():
    with pytest.raises(ValidationError):
        Salida(categoria="cambio", respuesta_sugerida="Podés cambiarlo en cualquier sucursal.",
               requiere_humano=False, confianza=0.9, descuento=10)


# --- Motor ---------------------------------------------------------------------
@pytest.mark.parametrize("proveedor", PROVEEDORES)
def test_ok_en_el_primer_intento_con_cada_proveedor(proveedor):
    r = procesar(CONSULTA, proveedor, llamar=ModeloSimulado([BIEN]))
    assert r["ok"] and r["intentos"] == 1 and r["proveedor"] == proveedor
    assert r["modelo"] == datos_proveedor(proveedor)["modelo"]
    assert r["costo_usd"] > 0


def test_reintenta_una_vez_y_se_corrige():
    modelo = ModeloSimulado([MAL, BIEN])
    r = procesar(CONSULTA, "groq", llamar=modelo)
    assert r["ok"] and r["intentos"] == 2 and modelo.llamadas == 2
    assert r["tokens_entrada"] == 1800  # suma los tokens de los dos intentos


def test_si_falla_dos_veces_devuelve_error_estructurado():
    r = procesar(CONSULTA, "groq", llamar=ModeloSimulado([MAL, MAL]))
    assert not r["ok"] and r["etapa"] == "VALIDACION_SALIDA"
    assert any(e["campo"] == "confianza" for e in r["errores"])


def test_acepta_json_envuelto_en_bloque_de_codigo():
    r = procesar(CONSULTA, "anthropic", llamar=ModeloSimulado(["```json\n" + BIEN + "\n```"]))
    assert r["ok"]


def test_entrada_invalida_no_llama_al_modelo():
    modelo = ModeloSimulado([BIEN])
    r = procesar({"consulta": "hola"}, "groq", llamar=modelo)
    assert r["etapa"] == "VALIDACION_ENTRADA" and modelo.llamadas == 0
    assert r["costo_usd"] == 0


def test_proveedor_desconocido_es_error_de_configuracion():
    r = procesar(CONSULTA, "mistral", llamar=ModeloSimulado([BIEN]))
    assert r["etapa"] == "CONFIGURACION"


def test_falta_la_clave(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = procesar(CONSULTA, "groq")
    assert r["etapa"] == "CONFIGURACION" and r["errores"][0]["campo"] == "GROQ_API_KEY"


# --- Errores de API ------------------------------------------------------------
class ErrorFalso(Exception):
    def __init__(self, status_code=None):
        super().__init__("error de prueba")
        self.status_code = status_code


@pytest.mark.parametrize("error, etapa", [
    (ErrorFalso(401), "CONFIGURACION"),
    (ErrorFalso(429), "API_LIMITE"),
    (ConnectionError("sin red"), "API_CONEXION"),
    (TimeoutError("tardó"), "API_CONEXION"),
    (ErrorFalso(500), "API_ERROR"),
])
def test_clasificar_errores_de_api(error, etapa):
    assert clasificar_error(error)[0] == etapa


def test_error_de_api_devuelve_error_estructurado():
    def modelo_sin_red(sistema, mensajes, proveedor):
        raise ConnectionError("sin red")

    r = procesar(CONSULTA, "google", llamar=modelo_sin_red)
    assert not r["ok"] and r["etapa"] == "API_CONEXION" and r["intentos"] == 1


# --- Adaptadores -----------------------------------------------------------------
def test_formato_google_renombra_al_asistente():
    mensajes = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "{}"}]
    assert a_formato_google(mensajes) == [
        {"role": "user", "parts": [{"text": "hola"}]},
        {"role": "model", "parts": [{"text": "{}"}]},
    ]
