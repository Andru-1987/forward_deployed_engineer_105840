"""Motor LLM base de la Mesa de Ayuda IT (Preentrega 2).

Recibe el pedido de un empleado, lo valida, se lo pasa a un modelo real (OpenAI, Anthropic,
Google o Groq) y devuelve una ficha validada con Pydantic, junto con tokens, costo y latencia.

Correlo con:  uv run python src/motor.py
Otro proveedor: uv run python src/motor.py --proveedor google
"""

import argparse
import json
import logging
import time

from pydantic import ValidationError

from configuracion import CONFIG, RAIZ
from contratos import Entrada, Salida
from proveedores import (
    PROVEEDORES,
    clasificar_error,
    datos_proveedor,
    falta_clave,
    llamar_modelo,
    proveedor_activo,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
log = logging.getLogger("motor")


# --- 1. Prompt: vive en un archivo aparte, no dentro de la función ----------
def armar_prompt_sistema() -> str:
    plantilla = (RAIZ / CONFIG["prompt"]["archivo"]).read_text(encoding="utf-8")
    esquema = json.dumps(Salida.model_json_schema(), ensure_ascii=False, indent=2)
    return plantilla.replace("{esquema_json}", esquema)


# --- 2. Medición y errores ---------------------------------------------------
def calcular_costo(tokens_entrada: int, tokens_salida: int, proveedor: str) -> float:
    """Usa la tarifa paga del modelo. En un plan gratuito es lo que costaría pagando."""
    datos = datos_proveedor(proveedor)
    costo = (
        tokens_entrada / 1_000_000 * datos["precio_entrada"]
        + tokens_salida / 1_000_000 * datos["precio_salida"]
    )
    return round(costo, 6)


def describir_errores(error: ValidationError) -> list[dict]:
    """Convierte un ValidationError en una lista simple: qué campo y por qué."""
    return [
        {
            "campo": ".".join(str(parte) for parte in e["loc"]) or "(respuesta completa)",
            "problema": e["msg"],
        }
        for e in error.errors()
    ]


def extraer_json(texto: str) -> str:
    """Si el modelo envuelve el JSON en ```json ... ```, nos quedamos con el objeto."""
    inicio, fin = texto.find("{"), texto.rfind("}")
    return texto[inicio:fin + 1] if inicio != -1 and fin > inicio else texto


def armar_resultado(ok, etapa, proveedor, intentos, tokens_entrada, tokens_salida,
                    inicio, **datos):
    """Toda respuesta del motor, exitosa o no, lleva la misma medición."""
    conocido = proveedor in PROVEEDORES
    return {
        "ok": ok,
        "etapa": etapa,
        **datos,
        "intentos": intentos,
        "tokens_entrada": tokens_entrada,
        "tokens_salida": tokens_salida,
        "costo_usd": calcular_costo(tokens_entrada, tokens_salida, proveedor) if conocido else 0,
        "latencia_ms": int((time.perf_counter() - inicio) * 1000),
        "proveedor": proveedor,
        "modelo": datos_proveedor(proveedor)["modelo"] if conocido else None,
        "plan": datos_proveedor(proveedor)["plan"] if conocido else None,
        "version_prompt": CONFIG["prompt"]["version"],
    }


# --- 3. El motor -------------------------------------------------------------
def procesar(datos: dict, proveedor: str | None = None, llamar=None) -> dict:
    """llamar sirve para las pruebas: les pasamos un modelo simulado y no se usa ninguna API."""
    inicio = time.perf_counter()
    proveedor = proveedor_activo(proveedor)
    tokens_entrada = tokens_salida = 0
    intentos = 0

    # Etapa 1: validar la entrada ANTES de gastar tokens.
    try:
        entrada = Entrada(**datos)
    except ValidationError as error:
        log.warning("Entrada inválida: %s", describir_errores(error))
        return armar_resultado(False, "VALIDACION_ENTRADA", proveedor, 0, 0, 0, inicio,
                               errores=describir_errores(error))

    # Etapa 2: revisar que el proveedor exista y que su clave esté en .env.
    if proveedor not in PROVEEDORES:
        return armar_resultado(False, "CONFIGURACION", proveedor, 0, 0, 0, inicio,
                               errores=[{"campo": "proveedor", "problema":
                                         f"usá uno de estos: {', '.join(PROVEEDORES)}"}])
    if llamar is None:
        variable = falta_clave(proveedor)
        if variable:
            return armar_resultado(False, "CONFIGURACION", proveedor, 0, 0, 0, inicio,
                                   errores=[{"campo": variable,
                                             "problema": "falta la clave en el archivo .env"}])
        llamar = llamar_modelo

    sistema = armar_prompt_sistema()
    mensajes = [{"role": "user", "content": entrada.model_dump_json()}]

    # Etapa 3: llamar al modelo y validar. Si falla la validación, un reintento.
    max_intentos = 1 + CONFIG["motor"]["max_reintentos_validacion"]
    errores: list[dict] = []
    for intentos in range(1, max_intentos + 1):
        try:
            texto, t_in, t_out = llamar(sistema, mensajes, proveedor)
        except Exception as error:
            # Atrapamos cualquier error, pero SOLO alrededor de la llamada al proveedor
            # y sin esconderlo: lo clasificamos y guardamos su tipo y su mensaje.
            etapa, problema = clasificar_error(error)
            log.error("Intento %d: error de API (%s): %s", intentos, etapa, problema)
            return armar_resultado(False, etapa, proveedor, intentos, tokens_entrada,
                                   tokens_salida, inicio,
                                   errores=[{"campo": "api", "problema": problema}])

        tokens_entrada += t_in
        tokens_salida += t_out

        try:
            salida = Salida.model_validate_json(extraer_json(texto))
            return armar_resultado(True, "OK", proveedor, intentos, tokens_entrada,
                                   tokens_salida, inicio, salida=salida.model_dump(mode="json"))
        except ValidationError as error:
            errores = describir_errores(error)
            for e in errores:
                log.warning("Intento %d: falló el campo '%s': %s",
                            intentos, e["campo"], e["problema"])
            # Para el reintento, le mostramos al modelo su respuesta y qué corregir.
            mensajes.append({"role": "assistant", "content": texto})
            mensajes.append({"role": "user", "content":
                             "Tu respuesta no cumple el esquema. Corregí estos errores y "
                             "devolvé solo el JSON: " + json.dumps(errores, ensure_ascii=False)})

    # Si llegamos acá, falló la validación en todos los intentos.
    return armar_resultado(False, "VALIDACION_SALIDA", proveedor, intentos, tokens_entrada,
                           tokens_salida, inicio, errores=errores)


# --- 4. Prueba rápida: una ejecución exitosa y una con error -----------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba rápida del motor")
    parser.add_argument("--proveedor", choices=PROVEEDORES, help="por defecto, el de config.toml")
    proveedor = parser.parse_args().proveedor

    print("== Ejecución 1: pedido válido ==")
    ok = procesar({"legajo": "EMP-0142",
                   "mensaje": "Desde esta mañana no puedo entrar al sistema de sueldos: "
                              "me dice usuario bloqueado."}, proveedor)
    print(json.dumps(ok, ensure_ascii=False, indent=2))

    print("\n== Ejecución 2: entrada inválida (no gasta tokens) ==")
    error = procesar({"legajo": "142", "mensaje": "no anda"}, proveedor)
    print(json.dumps(error, ensure_ascii=False, indent=2))
