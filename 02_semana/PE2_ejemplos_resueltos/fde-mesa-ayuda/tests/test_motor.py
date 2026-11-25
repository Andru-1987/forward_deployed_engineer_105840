"""Pruebas sin API key: corren con  uv run pytest"""

import pytest
from pydantic import ValidationError

from contratos import Entrada, Salida
from modelo_simulado import ModeloSimulado
from motor import extraer_json, procesar
from proveedores import PROVEEDORES, a_formato_google, clasificar_error, datos_proveedor

BIEN = ('{"tipo": "accesos", "prioridad": "media", "resumen": "Usuario bloqueado en el '
        'sistema de sueldos", "pasos_sugeridos": ["Verificar el bloqueo en el directorio", '
        '"Desbloquear y pedir cambio de clave"], "escalar_a_n2": false, "confianza": 0.85}')
SIN_ESCALAR = ('{"tipo": "red", "prioridad": "alta", "resumen": "Se cayó el wifi del piso 3", '
               '"pasos_sugeridos": ["Reiniciar el access point"], "escalar_a_n2": false, '
               '"confianza": 0.8}')
PEDIDO = {"legajo": "EMP-0142", "mensaje": "No puedo entrar al sistema de sueldos, dice bloqueado."}


# --- Contrato ----------------------------------------------------------------
def test_entrada_rechaza_legajo_con_formato_incorrecto():
    with pytest.raises(ValidationError):
        Entrada(legajo="142", mensaje="No puedo entrar al sistema de sueldos.")


def test_salida_rechaza_lista_de_pasos_vacia():
    with pytest.raises(ValidationError):
        Salida(tipo="software", prioridad="baja", resumen="Excel se cierra solo",
               pasos_sugeridos=[], escalar_a_n2=False, confianza=0.9)


def test_regla_de_negocio_prioridad_alta_exige_escalar():
    with pytest.raises(ValidationError) as info:
        Salida.model_validate_json(SIN_ESCALAR)
    assert "escalar_a_n2" in str(info.value)


def test_extraer_json_quita_bloques_de_codigo():
    assert extraer_json('```json\n{"a": 1}\n```') == '{"a": 1}'


# --- Motor ---------------------------------------------------------------------
@pytest.mark.parametrize("proveedor", PROVEEDORES)
def test_ok_en_el_primer_intento_con_cada_proveedor(proveedor):
    r = procesar(PEDIDO, proveedor, llamar=ModeloSimulado([BIEN]))
    assert r["ok"] and r["intentos"] == 1 and r["salida"]["tipo"] == "accesos"
    assert r["modelo"] == datos_proveedor(proveedor)["modelo"]


def test_acepta_json_envuelto_en_bloque_de_codigo():
    r = procesar(PEDIDO, "anthropic", llamar=ModeloSimulado(["```json\n" + BIEN + "\n```"]))
    assert r["ok"]


def test_reintenta_una_vez_y_se_corrige():
    corregida = SIN_ESCALAR.replace('"escalar_a_n2": false', '"escalar_a_n2": true')
    modelo = ModeloSimulado([SIN_ESCALAR, corregida], tokens_entrada=1100)
    r = procesar(PEDIDO, "google", llamar=modelo)
    assert r["ok"] and r["intentos"] == 2 and r["tokens_entrada"] == 2200


def test_si_falla_dos_veces_devuelve_error_estructurado():
    r = procesar(PEDIDO, "google", llamar=ModeloSimulado([SIN_ESCALAR, SIN_ESCALAR]))
    assert not r["ok"] and r["etapa"] == "VALIDACION_SALIDA"
    assert r["errores"][0]["campo"] == "(respuesta completa)"


def test_entrada_invalida_no_llama_al_modelo():
    modelo = ModeloSimulado([BIEN])
    r = procesar({"legajo": "EMP-0142", "mensaje": "no anda"}, "google", llamar=modelo)
    assert r["etapa"] == "VALIDACION_ENTRADA" and modelo.llamadas == 0


def test_falta_la_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = procesar(PEDIDO, "google")
    assert r["etapa"] == "CONFIGURACION" and r["errores"][0]["campo"] == "GEMINI_API_KEY"


# --- Errores de API ------------------------------------------------------------
class ErrorFalso(Exception):
    def __init__(self, status_code=None):
        super().__init__("error de prueba")
        self.status_code = status_code


@pytest.mark.parametrize("error, etapa", [
    (ErrorFalso(401), "CONFIGURACION"),
    (ErrorFalso(429), "API_LIMITE"),
    (ConnectionError("sin red"), "API_CONEXION"),
    (ErrorFalso(500), "API_ERROR"),
])
def test_clasificar_errores_de_api(error, etapa):
    assert clasificar_error(error)[0] == etapa


def test_error_de_api_devuelve_error_estructurado():
    def modelo_limitado(sistema, mensajes, proveedor):
        raise ErrorFalso(429)

    r = procesar(PEDIDO, "groq", llamar=modelo_limitado)
    assert not r["ok"] and r["etapa"] == "API_LIMITE"


def test_formato_google_renombra_al_asistente():
    salida = a_formato_google([{"role": "assistant", "content": "{}"}])
    assert salida == [{"role": "model", "parts": [{"text": "{}"}]}]
