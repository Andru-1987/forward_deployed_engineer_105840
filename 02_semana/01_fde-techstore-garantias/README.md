# FDE TechStore Garantias: Mi motor LLM (Pre-Entrega 2)

## Que es
Nucleo en Python del asistente de triaje de garantias y devoluciones de TechStore (caso de la PE1).
Recibe un ticket, consulta un modelo real (Groq) y devuelve un dictamen **estructurado, validado y medido** en tokens, costo y latencia.

## Que soluciona
El analista N1 pierde 11 de 18 minutos por ticket leyendo politicas y verificando condiciones. El motor produce un dictamen preliminar
(`elegible_borrador`, `no_elegible`, `faltan_datos`, `requiere_revision_manual`), cita la clausula y marca cuando se necesita Supervisor N2.
Nunca aprueba pagos: solo propone. La decision final sigue siendo humana.

## Flujo

```text
dict crudo -> Entrada (Pydantic)  --invalida--> error VALIDACION_ENTRADA (0 tokens, 0 USD)
           -> prompt (plantilla en prompts/ + umbral de config.toml)
           -> Groq (JSON mode)    --429/red--> error INFRAESTRUCTURA_API
           -> Salida (Pydantic + regla del umbral supervisor)
                |-- invalida -> UN reintento con campo (loc) y motivo (msg) -> si falla: VALIDACION_SALIDA
           -> {ok, salida, tokens, costo_usd, latencia_ms}
```

## Estructura

```bash
.env.example      solo nombres de variables (copiar a .env; no se versiona)
config.toml       modelo, tarifas, reintentos, umbral de supervisor, meta del KPI
prompts/          plantilla del system prompt, aislada del codigo
src/config.py     config.toml + secretos, validados al arrancar
src/schemas.py    contratos Entrada / Salida
src/motor.py      el motor: validacion, llamada, reintento, telemetria
src/casos.py      las 5 consultas de medicion y su estado esperado
src/medicion.py   promedios y accuracy vs meta
tests/            tests offline (cliente falso, sin API key)
main.py           unico entrypoint
```

## Como correrlo (desde un clon limpio)

```bash
uv sync                                  # entorno exacto desde uv.lock
uv run pytest                            # tests offline
cp .env.example .env                     # completar GROQ_API_KEY
uv run python main.py                    # 5 consultas reales + resumen vs KPI
```

Compatibilidad con la rubrica (`pip`): `requirements.txt` esta exportado. Si agregas dependencias, re-exportar **antes** de etiquetar:

```bash
uv export --no-hashes --format requirements-txt -o requirements.txt
git tag pe2
```

## Reglas de validacion
- `Entrada`: `ticket_id` con patron `TCK-####`, mensaje de al menos 15 caracteres, dias >= 0, monto > 0, rol como `Enum`.
- `Salida`: reintegro sobre el umbral exige `requiere_aprobacion_supervisor=True`; solo un caso `elegible_borrador` puede sugerir dinero.
- El umbral (50 USD) vive en `config.toml`, no en el codigo ni solo en el prompt.

## Medicion
`main.py` imprime tokens, costo y latencia promedio de las 5 consultas (incluye una confusa y una fuera de tema)
y la accuracy del estado frente a la meta del KPI tecnico de PE1 (>= 95%). Con 5 casos cada error pesa 20 puntos: tomar el resultado como indicio, no como conclusion.

## Nota sobre el prompt
Agregue al final de la regla 4 "Esta regla tiene prioridad sobre la regla 2": sin eso, una consulta fuera de tema sin adjuntos cumple las reglas 2 y 4 a la vez.
