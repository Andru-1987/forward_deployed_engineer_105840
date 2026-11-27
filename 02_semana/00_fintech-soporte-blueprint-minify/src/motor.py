"""One turn = mask PII -> LLM -> validate -> (guided retry) -> result + telemetry.

Never returns a traceback or raw model text: always a dict with `ok` and, on
failure, the pipeline `etapa` that failed.
"""

import time
from typing import Any

from groq import APIError
from pydantic import ValidationError

from src.config import RAIZ, AppConfig
from src.guardrails import enmascarar_pii
from src.schemas import SalidaFintech, resumir_errores, validar_salida


def calcular_costo_usd(config: AppConfig, tokens_in: int, tokens_out: int) -> float:
    t = config.tarifas_usd_por_millon
    return round(tokens_in / 1e6 * t.input + tokens_out / 1e6 * t.output, 6)


def ejecutar_turno(
    consulta_usuario: str, cliente: Any, config: AppConfig, ruta_prompt: str
) -> dict[str, Any]:
    """`cliente` is injected (real Groq or a fake in tests)."""
    plantilla = (RAIZ / ruta_prompt).read_text(encoding="utf-8")
    prompt_sistema = plantilla.format(schema=SalidaFintech.model_json_schema())
    consulta_segura = enmascarar_pii(consulta_usuario)
    prompt_actual = consulta_segura
    tokens_in = tokens_out = 0
    errores: list[dict[str, str]] = []
    inicio = time.perf_counter()

    def terminar(resultado: dict[str, Any]) -> dict[str, Any]:
        resultado["telemetria"] = {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "costo_usd": calcular_costo_usd(config, tokens_in, tokens_out),
            "latencia_ms": int((time.perf_counter() - inicio) * 1000),
        }
        return resultado

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
        except APIError as err:  # 429 / 5xx: detail for logs, not for the customer
            return terminar(
                {"ok": False, "etapa": "INFRAESTRUCTURA_API", "detalle": type(err).__name__}
            )

        tokens_in += resp.usage.prompt_tokens  # retries cost too
        tokens_out += resp.usage.completion_tokens

        try:
            salida = validar_salida(resp.choices[0].message.content, config.reglas_negocio)
        except ValidationError as e:
            errores = resumir_errores(e)
            prompt_actual = (
                f"{consulta_segura}\n\n"
                f"ERROR DE VALIDACION EN TU RESPUESTA ANTERIOR: {errores}. "
                "Corrigelo y devuelve solo el JSON."
            )
            continue

        return terminar({"ok": True, "intento": intento, "datos": salida.model_dump(mode="json")})

    return terminar({"ok": False, "etapa": "VALIDACION_SALIDA", "errores": errores})
