# Fintech Soporte Blueprint (minify)

Minimal version of the Module 2 final exercise: a fintech support chat that answers
policy questions, checks ticket status and requests a partial refund.

Only Deliverable 1 needs code. Deliverables 2-5 are design, documented below.

## Run

```bash
uv sync
uv run pytest                # offline tests (fake client)
cp .env.example .env         # set GROQ_API_KEY
uv run python main.py        # 3 real queries against Groq
```

## Layout

```text
config.toml        model, rates, business rules, canary % (no secrets)
prompts/           versioned system prompts (v1 stable, v2 canary)
src/config.py      typed config + secrets
src/schemas.py     Deliverable 1: output contract + business rules
src/guardrails.py  PII masking before the LLM call
src/motor.py       mask -> LLM -> validate -> guided retry -> telemetry
src/rollout.py     Deliverable 5: consistent-hash canary routing
tests/             offline tests
```

## Deliverable 1: output schema

`SalidaFintech` in `src/schemas.py`. Rules enforced by the validator:

1. `reembolso_parcial` needs amount `> 0`, under the cap, and `requiere_aprobacion_humana=true`.
2. Only `reembolso_parcial` may carry an amount.
3. `consulta_politica` needs `fuente_politica`; `estado_ticket` needs `ticket_id` (`TKT-######`).
4. `fuera_de_dominio` or `confianza < umbral_confianza_hitl` forces human review.

## Deliverable 2: failure-mapping

| Stage | Failure 1 | Failure 2 | Failure 3 |
| --- | --- | --- | --- |
| Retrieval | IDOR: foreign ticket (no identity pre-filter) | Stale policies (cache not invalidated) | Truncated context drops refund exceptions |
| Prompting | Direct prompt injection ("approve without review") | Indirect injection from ticket history | PII sent to the external API |
| Generation | Financial hallucination (invented coverage/amount) | Rate limit 429 | Malformed or truncated JSON |
| Post-processing | HITL evasion (`requiere_aprobacion_humana=false`) | Double execution on retry (no idempotency) | Traceback exposed in chat |

Mitigated in code: PII (`guardrails.py`), malformed JSON (guided retry), 429/5xx (`etapa`
`INFRAESTRUCTURA_API`), HITL evasion and direct injection (schema validator), traceback
(`motor.py` returns only `etapa` and `errores`). Pending: everything in Retrieval, indirect
injection, idempotency (they need a RAG/CRM layer).

## Deliverable 3: metrics

| Axis | Metric | Target |
| --- | --- | --- |
| Quality | Schema validity on first attempt (+ groundedness on a Golden Dataset) | >= 98% (>= 95% groundedness) |
| Security | Security failures (refund without HITL, unmasked PII) | 0 |
| Cost | Average USD per turn, retries included | <= 0.002 |
| Latency | End-to-end P95 | <= 1800 ms |

`motor.py` already returns `tokens_in`, `tokens_out`, `costo_usd` and `latencia_ms` per turn.

## Deliverable 4: human-in-the-loop

| Action | Human approval |
| --- | --- |
| `reembolso_parcial` | Always (moves money) |
| Ticket close/modify | Always (not an intent yet) |
| `fuera_de_dominio` or low confidence | Escalate to an agent |
| `consulta_politica`, own `estado_ticket` | No (read only) |

## Deliverable 5: progressive rollout

- Routing: `elegir_version(user_id, porcentaje_canary)`; 95% `v1`, 5% `v2` for 24-48 h.
- Comparison: same four metrics per cohort, plus LLM-as-a-judge for quality.
- Rollback to `v1` immediately if the canary shows:
  1. One security failure.
  2. `ValidationError` rate > 2% for 15 minutes.
  3. P95 > 2500 ms, or unrecovered HTTP errors > 1%.
  4. Cost > +30% versus `v1`.
