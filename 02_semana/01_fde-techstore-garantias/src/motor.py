"""Motor LLM base: validar entrada -> llamar a Groq -> validar salida -> (1 reintento) -> telemetria.

Leccion FDE: el motor nunca rompe ni devuelve un traceback. Devuelve siempre un dict
con `ok` y, si falla, la `etapa` exacta (VALIDACION_ENTRADA, INFRAESTRUCTURA_API,
VALIDACION_SALIDA). Tokens, costo y latencia se miden en TODOS los casos.
"""

import logging
import time
from typing import Any

from groq import APIError
from pydantic import ValidationError

from src.config import RAIZ, AppConfig
from src.schemas import Entrada, Salida, formatear_errores, validar_salida

log = logging.getLogger(__name__)


def calcular_costo_usd(config: AppConfig, tokens_in: int, tokens_out: int) -> float:
    t = config.tarifas_usd_por_millon
    return round(tokens_in / 1e6 * t.input + tokens_out / 1e6 * t.output, 6)


def procesar_ticket(datos_crudos: dict[str, Any], cliente: Any, config: AppConfig) -> dict[str, Any]:
    """`cliente` se inyecta (Groq real o falso en tests): el motor no crea dependencias."""
    tokens_in = tokens_out = 0
    inicio = time.perf_counter()

    def terminar(resultado: dict[str, Any]) -> dict[str, Any]:
        resultado["tokens"] = {"entrada": tokens_in, "salida": tokens_out}
        resultado["costo_usd"] = calcular_costo_usd(config, tokens_in, tokens_out)
        resultado["latencia_ms"] = int((time.perf_counter() - inicio) * 1000)
        return resultado

    # Validacion temprana: una entrada invalida no debe costar ni una llamada a la API.
    try:
        entrada = Entrada.model_validate(datos_crudos)
    except ValidationError as err:
        return terminar({"ok": False, "etapa": "VALIDACION_ENTRADA", "errores": formatear_errores(err)})

    # El prompt vive en un archivo aparte: se versiona y se revisa sin tocar codigo.
    plantilla = (RAIZ / config.llm.ruta_system_prompt).read_text(encoding="utf-8")
    system_prompt = plantilla.format(
        schema_json=Salida.model_json_schema(),
        umbral_supervisor=config.reglas_negocio.umbral_aprobacion_supervisor_usd,
    )
    user_prompt = (
        f"Ticket: {entrada.ticket_id} | Dias desde entrega: {entrada.dias_desde_entrega} | "
        f"Monto pagado: ${entrada.monto_pagado_usd} USD | Adjuntos completos: {entrada.tiene_factura_y_foto} | "
        f"Rol operador: {entrada.rol_ejecutor.value}\n"
        f"Mensaje del cliente: {entrada.mensaje_cliente}"
    )

    errores: list[dict[str, str]] = []
    for intento in range(1, 2 + config.llm.max_reintentos_validacion):
        try:
            resp = cliente.chat.completions.create(
                model=config.llm.modelo,
                temperature=config.llm.temperatura,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except APIError as err:  # cubre red, cuota (429) y errores 5xx de Groq
            return terminar(
                {"ok": False, "etapa": "INFRAESTRUCTURA_API", "detalle": str(err), "intento": intento}
            )

        tokens_in += resp.usage.prompt_tokens
        tokens_out += resp.usage.completion_tokens

        try:
            salida = validar_salida(resp.choices[0].message.content, config.reglas_negocio)
        except ValidationError as err:
            errores = formatear_errores(err)
            log.warning("Intento %d invalido. Campos fallidos: %s", intento, errores)
            # Reintento guiado: el modelo recibe QUE campo fallo y POR QUE.
            user_prompt += (
                f"\n\nCORRECCION REQUERIDA: tu JSON anterior incumplio estas reglas: {errores}. "
                "Corrigelas y responde solo con el JSON."
            )
            continue

        return terminar({"ok": True, "modelo": config.llm.modelo, "intento": intento,
                         "salida": salida.model_dump(mode="json")})

    return terminar({"ok": False, "etapa": "VALIDACION_SALIDA", "errores": errores,
                     "intento": 1 + config.llm.max_reintentos_validacion})
