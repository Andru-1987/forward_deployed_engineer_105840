# Fintech Soporte Blueprint (Semana 2: LLMs en produccion)

## Que es
Codigo de referencia de la clase en vivo del Modulo 2. Un chat de soporte de una fintech que puede:
responder politicas, consultar el estado de un ticket y solicitar un reembolso parcial.

## Que soluciona
Un LLM solo no es un sistema de produccion. Este proyecto muestra las capas que lo vuelven confiable:

| Problema en produccion | Capa que lo resuelve | Archivo |
| --- | --- | --- |
| Salida libre e impredecible | Contrato Pydantic + reglas de negocio | `src/schemas.py` |
| Fuga de datos personales al proveedor | Enmascarado de PII antes de llamar al LLM | `src/guardrails.py` |
| El modelo se equivoca o corta el JSON | Validacion + reintento unico guiado | `src/motor.py` |
| Dinero movido sin control | Gate Human-in-the-Loop independiente | `src/guardrails.py` |
| Costos y latencia fuera de control | Telemetria y 4 metricas con meta | `src/metricas.py` |
| Version nueva rompe todo | Canary 5% + criterios de rollback | `src/rollout.py` |
| Cambiar un umbral requiere deploy | Parametros en TOML, secretos en `.env` | `src/config.py` |

## Flujo de un turno

```text
usuario -> elegir_version(user_id)  ........ rollout.py (95% v1 / 5% v2)
        -> enmascarar_pii()  ............... guardrails.py (Prompting)
        -> LLM (Groq, JSON mode)  .......... motor.py     (Generacion)
        -> validar_salida() (Pydantic)  .... schemas.py
              |-- invalida -> reintento con el error (1 vez) -> si falla: etapa VALIDACION_SALIDA
        -> decidir_accion()  ............... guardrails.py (Post-procesado)
              |-- RESPONDER            lectura pura
              |-- ENCOLAR_APROBACION   reembolso: un operador aprueba
              |-- DERIVAR_A_HUMANO     fuera de dominio / baja confianza
        -> RegistroTurno -> resumir()  ..... metricas.py -> evaluar_rollback()
```

## Estructura

```text
config.toml      parametros, tarifas, metas y umbrales de rollback (sin secretos)
.env.example     plantilla de secretos (copiar a .env, no se versiona)
prompts/         system prompts versionados (v1 estable, v2 canary)
src/             config, schemas, guardrails, motor, metricas, rollout
tests/           tests sin red ni API key (cliente falso)
docs/blueprint.md  failure-mapping, metricas, HITL y rollout explicados
main.py          unico entrypoint: arma dependencias y corre 3 ejemplos
```

## Como correrlo

```bash
uv sync                      # instala dependencias
uv run pytest                # tests offline
cp .env.example .env         # completar GROQ_API_KEY
uv run python main.py        # 3 consultas reales contra Groq
```

## Primeros pasos hacia el caso de la Pre-Entrega 1 (TechStore: garantias y devoluciones)
Este blueprint es el esqueleto; el caso real cambia el dominio, no la arquitectura:

| Blueprint (fintech) | PE1 (TechStore) |
| --- | --- |
| `reembolso_parcial` siempre con HITL | Borrador de Nota de Credito; aprueba Analista N1 (< 50 USD) o Supervisor N2 |
| `consulta_politica` cita `fuente_politica` | Dictamen de elegibilidad cita clausula del PDF de garantias |
| `monto_maximo_reembolso_usd` en `config.toml` | Umbral de 50 USD por rol en `config.toml` |
| `fuera_de_dominio` / baja confianza -> humano | "Requiere revision manual" si no consta en el documento |
| `enmascarar_pii` (DNI, tarjeta, email) | Anonimizacion de DNI, nombre y correo antes del LLM |
| Metrica de calidad (validez/groundedness) | Accuracy >= 95% del dictamen y calculo del monto |

Siguiente paso natural: agregar recuperacion (RAG) sobre los PDFs de politicas y un Golden Dataset de 50 tickets para medir calidad.
