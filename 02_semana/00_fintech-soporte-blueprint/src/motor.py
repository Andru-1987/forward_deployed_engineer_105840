"""Motor: un turno = enmascarar -> LLM -> validar -> (reintento) -> accion + telemetria.

Leccion FDE: el motor NUNCA devuelve un traceback ni texto crudo del modelo al
usuario. Devuelve siempre un dict con `ok` y, si falla, la `etapa` que fallo.
Eso es lo que permite diagnosticar en produccion (failure-mapping).
"""

import time
from typing import Any

from groq import APIError
from pydantic import ValidationError

from src.config import RAIZ, AppConfig
from src.guardrails import decidir_accion, enmascarar_pii
from src.schemas import SalidaFintech, resumir_errores, validar_salida


def calcular_costo_usd(config: AppConfig, tokens_in: int, tokens_out: int) -> float:
    # Input y output se cobran distinto: medirlos por separado audita el costo real.
    t = config.tarifas_usd_por_millon
    return round(tokens_in / 1e6 * t.input + tokens_out / 1e6 * t.output, 6)


def ejecutar_turno(
    consulta_usuario: str, cliente: Any, config: AppConfig, ruta_prompt: str
) -> dict[str, Any]:
    """`cliente` se inyecta (Groq real o falso en tests): el motor no crea dependencias."""
    # El prompt vive en un archivo: se versiona, se revisa y se compara (v1 vs v2).
    plantilla = (RAIZ / ruta_prompt).read_text(encoding="utf-8")
    prompt_sistema = plantilla.format(schema=SalidaFintech.model_json_schema())
    # Etapa Prompting: la PII se enmascara ANTES de salir hacia el proveedor.
    consulta_segura = enmascarar_pii(consulta_usuario)
    prompt_actual = consulta_segura
    tokens_in = tokens_out = 0
    inicio = time.perf_counter()

    def terminar(resultado: dict[str, Any]) -> dict[str, Any]:
        # Misma telemetria en exito y en fallo: las metricas necesitan ambos casos.
        resultado["telemetria"] = {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "costo_usd": calcular_costo_usd(config, tokens_in, tokens_out),
            "latencia_ms": int((time.perf_counter() - inicio) * 1000),
        }
        return resultado

    errores: list[dict[str, str]] = []
    for intento in range(1, 2 + config.llm.max_reintentos_validacion):
        try:
            resp = cliente.chat.completions.create(
                model=config.llm.modelo,
                temperature=config.llm.temperatura,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_actual},
                ],
            )
        except APIError as err:
            # Etapa Generacion: 429 / 5xx. El detalle es para logs, no para el cliente.
            return terminar(
                {"ok": False, "etapa": "INFRAESTRUCTURA_API", "detalle": type(err).__name__}
            )

        # Los reintentos tambien cuestan: se suman al costo del turno.
        tokens_in += resp.usage.prompt_tokens
        tokens_out += resp.usage.completion_tokens

        try:
            salida = validar_salida(resp.choices[0].message.content, config.reglas_negocio)
        except ValidationError as e:
            # Reintento guiado: le decimos al modelo QUE campo fallo y POR QUE.
            errores = resumir_errores(e)
            prompt_actual = (
                f"{consulta_segura}\n\n"
                f"ERROR DE VALIDACION EN TU RESPUESTA ANTERIOR: {errores}. "
                "Corrigelo y devuelve solo el JSON."
            )
            continue

        return terminar({
            "ok": True,
            "intento": intento,
            "datos": salida.model_dump(mode="json"),
            # Etapa Post-procesado: que hacer con esta salida (responder o llamar a un humano).
            "accion": decidir_accion(salida, config.reglas_negocio).value,
        })

    return terminar({"ok": False, "etapa": "VALIDACION_SALIDA", "errores": errores})
