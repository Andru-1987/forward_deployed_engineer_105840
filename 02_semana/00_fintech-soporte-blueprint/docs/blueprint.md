# Blueprint: entregables 2 a 5

## Failure-mapping: 3 fallos por etapa

| Etapa | Fallo 1 | Fallo 2 | Fallo 3 |
| --- | --- | --- | --- |
| Recuperacion | Fuga entre clientes (IDOR): ticket ajeno por falta de filtro de identidad | Politicas caducas: cache/indice sin invalidar | Contexto truncado: se pierden excepciones de un reembolso |
| Prompting | Prompt injection directa ("aprueba sin revision") | Prompt injection indirecta desde el historial del ticket | Exposicion de PII hacia la API externa |
| Generacion | Alucinacion financiera (cobertura o monto inventado) | Rate limit HTTP 429 en picos | JSON malformado o truncado |
| Post-procesado | Evasion de HITL (`requiere_aprobacion_humana=false`) | Doble ejecucion por reintento (no idempotencia) | Traceback tecnico expuesto al chat |

### Estado de mitigacion en este codigo

| Fallo | Estado | Donde |
| --- | --- | --- |
| PII hacia la API | Implementado | `guardrails.enmascarar_pii` |
| Alucinacion de politicas | Parcial: exige `fuente_politica`; falta RAG | `schemas.py` |
| Monto fuera de tope / mal formado | Implementado | `schemas.py` |
| JSON malformado | Implementado: reintento guiado | `motor.py` |
| 429 / errores de API | Implementado: se captura y se reporta la etapa | `motor.py` |
| Evasion de HITL | Implementado dos veces: validator + gate | `schemas.py`, `guardrails.py` |
| Traceback al chat | Implementado: solo `etapa` y `errores` (campo, motivo) | `motor.py` |
| Injection directa | Mitigada por efecto: aunque el modelo obedezca, el schema rechaza reembolso sin HITL | `schemas.py` |
| IDOR, injection indirecta, cache, contexto truncado | Pendiente: requieren capa de recuperacion (RAG/CRM) | n/a |
| Doble ejecucion | Pendiente: requiere clave de idempotencia al escribir en el CRM | n/a |

## Metricas

| Eje | Metrica | Meta |
| --- | --- | --- |
| Calidad | Validez de schema en primer intento (+ groundedness en Golden Dataset) | >= 98% (>= 95% groundedness) |
| Seguridad | Fallos de seguridad (reembolso sin HITL, PII sin enmascarar) | 0 |
| Costo | USD promedio por turno, con reintentos | <= 0.002 |
| Latencia | P95 end-to-end | <= 1800 ms |

Las metas viven en `config.toml` (`[objetivos]`). La groundedness requiere un Golden Dataset y no se calcula en runtime.

## Human-in-the-Loop

| Accion | Aprobacion humana |
| --- | --- |
| `reembolso_parcial` | Siempre (mueve dinero) |
| Cierre o modificacion de estado de ticket | Siempre (aun no existe como intencion: se agrega con su propio gate) |
| `fuera_de_dominio` o `confianza < umbral_confianza_hitl` | Se deriva a un agente con resumen |
| `consulta_politica`, `estado_ticket` propio autenticado | No (lectura pura) |

## Rollout progresivo

- Enrutamiento: hash consistente por `user_id`; 95% `v1`, 5% `v2` durante 24-48 h (`rollout.elegir_version`).
- Comparacion: `metricas.resumir` sobre cada cohorte (validez, costo, P95, errores). El juez LLM (LLM-as-a-judge) no esta implementado.
- Rollback inmediato a `v1` (`rollout.evaluar_rollback`) si en el canary:
  1. Hay 1 fallo de seguridad.
  2. ValidationError > 2% (la ventana de 15 min la define quien llama).
  3. P95 > 2500 ms o errores HTTP > 1%.
  4. Costo > +30% frente a `v1`.
