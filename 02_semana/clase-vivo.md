**Módulo confirmado:** Semana 2 — LLMs en producción.

- [Implementacion en codigo de python](./fintech-soporte-blueprint/)

## 1. Consigna del Ejercicio Final: Blueprint de Arquitectura Resiliente

* **Fuente + Derivado:** Ejercicio integrador de cierre de la clase en vivo del Módulo 2 (20 minutos) diseñado para articular LLMOps, *failure-mapping*, *guardrails*, validación con Pydantic, costos, latencia y despliegue progresivo.

* **Escenario:** Chat de soporte de una *fintech* capaz de responder preguntas de políticas, consultar el estado de un ticket y solicitar un reembolso parcial.
* **Entregable obligatorio:**
1. Definir el *schema* Pydantic de salida.
2. Identificar tres fallos por etapa del *pipeline* (Recuperación, Prompting, Generación y Post-procesado).
3. Definir una métrica de calidad, una de seguridad, una de costo y una de latencia.
4. Especificar qué acciones requieren aprobación humana (*Human-in-the-Loop*).
5. Diseñar un *rollout* progresivo: 5% de tráfico con la versión nueva, comparación contra la versión actual y criterio de *rollback*.
---

## 2. Solución de Referencia (con `uv`, Groq y `config.toml`)

* **No consta en las fuentes:** El gestor `uv`, el proveedor `Groq` y el archivo `config.toml` con `tomllib` no aparecen mencionados en el material del curso; las fuentes especifican entornos virtuales estándar (`requirements.txt`), los proveedores OpenAI o Anthropic, el aislamiento de credenciales en `.env` y la separación de plantillas de *prompts*.


* **Derivado:** Se implementa la arquitectura aplicando los principios de contratos estrictos (`Pydantic`), telemetría de `usage`, reintento único guiado y aislamiento de secretos del Módulo 2, trasladando los parámetros operativos a `config.toml` para desacoplar la configuración del código.

> El código de esta solución ya está implementado en `fintech-soporte-blueprint/`. Esta sección documenta solo las decisiones técnicas.

### 2.1 Estructura del Proyecto, Secretos y Configuración

* **Estructura del proyecto (Derivado):** proyecto `fintech-soporte-blueprint/` con estos elementos:
  * `.env`: exclusivo para secretos; ignorado por Git.
  * `.env.example`: plantilla sin valores; solo el nombre `GROQ_API_KEY`.
  * `.gitignore`: excluye `.env`, `.venv/` y `__pycache__/`.
  * `config.toml`: parámetros del modelo, tarifas, reintentos y umbrales de negocio.
  * `pyproject.toml`: dependencias gestionadas con `uv` (`groq`, `pydantic`, `python-dotenv`).
  * `requirements.txt`: exportado con `uv` para compatibilidad estándar.
  * `prompts/triaje_v1.txt`: *system prompt* aislado de la lógica de ejecución.
  * `src/motor.py`: carga de `config.toml`, validación Pydantic y ejecución en Groq.

* **Inicialización con `uv` (Derivado):** crear el proyecto fijando Python 3.11, agregar las tres dependencias (`groq`, `pydantic`, `python-dotenv`) y exportar el lock a `requirements.txt` sin hashes, para mantener compatibilidad con el flujo estándar del curso.

* **Secretos `.env.example` (Fuente + Derivado):** solo nombres de variables; nunca se suben valores reales al repositorio.

* **Parámetros operativos `config.toml` (Derivado):** tres secciones.
  * `[llm]`: proveedor, modelo (`llama-3.3-70b-versatile`), temperatura `0.0`, máximo de reintentos de validación (`1`) y ruta del *system prompt*.
  * `[tarifas_usd_por_millon]`: tarifas diferenciadas por tipo de token (input `0.59`, output `0.79`) para auditar el costo real.
  * `[reglas_negocio]`: monto máximo de reembolso (`5000.0` USD) y umbral de confianza para HITL (`0.75`).

* **Plantilla de *prompt* `prompts/triaje_v1.txt` (Derivado):** define el rol de asistente de soporte de una Fintech y restringe la atención a tres intenciones:
  1. `consulta_politica`: debe citar `fuente_politica`.
  2. `estado_ticket`: requiere `ticket_id` con formato `TKT-######`.
  3. `reembolso_parcial`: siempre `requiere_aprobacion_humana=true`.

  Toda consulta ajena a la Fintech usa `fuera_de_dominio`. El modelo responde únicamente con un objeto JSON que cumpla el esquema inyectado en el marcador `{schema}`.

### 2.2 Entregable 1: Schema Pydantic de Salida y Motor (`src/motor.py`)

* **Derivado** (aplicando `BaseModel`, `Enum`, `Field`, `@model_validator`, extracción de `loc`/`msg` en `ValidationError` y medición de tokens/latencia del Módulo 2):

**Carga de configuración**

* Los secretos se cargan solo desde `.env` (`load_dotenv`); la configuración operativa viene de TOML.
* Modelos Pydantic anidados validan `config.toml` al iniciar: `LLMConfig`, `TarifasConfig`, `ReglasNegocioConfig` y `AppConfig`.
* Restricciones de tipo en la config: `temperatura` entre 0 y 2, `max_reintentos_validacion` entre 0 y 3, tarifas `> 0`, umbral de confianza entre 0 y 1.
* `tomllib` exige abrir el archivo en binario (`rb`). La ruta se resuelve relativa al proyecto, no al directorio de ejecución.

**Schema de salida `SalidaFintech`**

| Campo | Tipo / restricción | Propósito |
| --- | --- | --- |
| `intencion` | `Enum` `IntencionSoporte` (`consulta_politica`, `estado_ticket`, `reembolso_parcial`, `fuera_de_dominio`) | Restringe las salidas posibles a los casos permitidos |
| `fuente_politica` | `Optional[str]` | Obliga a citar fuente documental para mitigar alucinaciones |
| `ticket_id` | `Optional[str]`, patrón `^TKT-\d{6}$` | Previene inyecciones o IDs malformados hacia el CRM |
| `monto_reembolso_usd` | `float`, `>= 0`, tope leído de `config.toml` | Límite dinámico de negocio |
| `requiere_aprobacion_humana` | `bool` | Marca el control HITL |
| `respuesta_usuario` | `str`, `min_length=15` | Evita respuestas vacías |
| `confianza` | `float`, entre 0 y 1 | Insumo para escalamiento |

**Reglas de negocio (`@model_validator(mode="after")`)**

1. **Dinero exige humano:** un `reembolso_parcial` requiere `monto_reembolso_usd > 0` y `requiere_aprobacion_humana=True`.
2. **Sin importes en consultas informativas:** solo `reembolso_parcial` admite monto mayor a 0.
3. **Baja confianza escala:** si `confianza < umbral_confianza_hitl`, `requiere_aprobacion_humana` debe ser `True`.

**Flujo de ejecución (`ejecutar_turno_fintech`)**

1. Verifica `GROQ_API_KEY`; si falta, devuelve error de etapa `CONFIGURACION`.
2. Carga el *system prompt* e inyecta el JSON Schema del modelo en `{schema}`.
3. Llama al modelo con temperatura de config y `response_format` JSON.
4. Captura `RateLimitError` y `APIError` y devuelve error de etapa `INFRAESTRUCTURA_API`, sin propagar la traza.
5. Mide latencia con `time.perf_counter` y lee `usage` (`prompt_tokens`, `completion_tokens`).
6. Valida la respuesta con `model_validate_json`. Si pasa, devuelve datos más telemetría: tokens de entrada y salida, costo en USD y latencia en ms.
7. Si falla `ValidationError`, extrae `loc` y `msg` de cada error y los reinyecta al prompt como corrección guiada. Se hace un único reintento (`1 + max_reintentos_validacion` intentos totales).
8. Agotados los intentos, devuelve error de etapa `VALIDACION_SALIDA` con la lista de errores.

**Costo:** `(tokens_in / 1M × tarifa_input) + (tokens_out / 1M × tarifa_output)`, redondeado a 6 decimales.

### 2.3 Entregable 2: Failure-Mapping (Tres Fallos por Etapa)

* **Derivado** (aplicando las 4 etapas del taller de *Failure-mapping* del Módulo 2):



| Etapa del Pipeline | Fallo 1 | Fallo 2 | Fallo 3 |
| --- | --- | --- | --- |
| **1. Recuperación (Contexto)** | **Fuga entre clientes (IDOR):** Recuperar el estado de un `ticket_id` ajeno por omitir el filtro de identidad previo (*pre-filtering*). | **Políticas caducas:** Recuperar comisiones o plazos viejos por no invalidar la caché o el índice tras una actualización. | **Contexto truncado:** Cortar un fragmento documental dejando fuera las excepciones legales de un reembolso. |
| **2. Prompting (Entrada)** | **Prompt Injection directa:** El usuario ordena ignorar reglas y aprobar un reembolso sin revisión humana. | **Prompt Injection indirecta:** El historial de un ticket contiene texto malicioso que secuestra la intención del modelo. | **Exposición de PII:** Enviar números de tarjeta, CBU o DNI reales en texto plano hacia la API externa. |
| **3. Generación (Groq)** | **Alucinación financiera:** Inventar una cobertura inexistente o calcular erróneamente el monto parcial. | **Rate Limit (`HTTP 429`):** Picos de tráfico saturan la cuota de tokens por minuto y generan fallos en cascada. | **JSON malformado o truncado:** Devolver el monto como texto libre o cortar el cierre del objeto JSON. |
| **4. Post-procesado (Salida)** | **Evasión de HITL:** Clasificar como `reembolso_parcial` marcando `requiere_aprobacion_humana: false`. | **Doble ejecución (No idempotencia):** Reintentar una petición lenta generando dos solicitudes de reembolso para el mismo ticket. | **Exposición de trazas:** Devolver el *traceback* técnico crudo de Python al chat ante un `ValidationError`. |

### 2.4 Entregable 3: Métricas Clave

* **Derivado** (conectando telemetría de `usage`, guardrails y criterios cuantitativos del curso):


1. **Calidad — Tasa de Validez de Esquema y Fidelidad:** $\ge 98\%$ de respuestas aprobando Pydantic en el primer intento y $\ge 95\%$ de fidelidad a las políticas vigentes (*groundedness*) evaluada sobre un *Golden Dataset*.
2. **Seguridad — Tasa de Bloqueo de Ataques y Fuga Cero de PII:** $\ge 99\%$ de intentos de *prompt injection* o reembolsos sin supervisión bloqueados, y **0%** de logs o *prompts* con datos personales sin enmascarar.
3. **Costo — Costo Promedio por Consulta Resuelta:** $\le \$0.002\text{ USD}$ por turno calculado mediante `tokens_in` y `tokens_out` (incluyendo reintentos y descontando *cache hits* en Redis).
4. **Latencia — Latencia P95 de Extremo a Extremo:** $\le 1.800\text{ ms}$ en el percentil 95 desde la entrada del usuario hasta la respuesta validada, monitoreando también el tiempo hasta el primer token (*TTFT*).



### 2.5 Entregable 4: Acciones que Requieren Aprobación Humana (*Human-in-the-Loop*)

* **Fuente + Derivado** (aplicando el principio de control humano sobre acciones de escritura críticas o con impacto financiero):


* **Solicitud de reembolso parcial (`reembolso_parcial`) — 100% de los casos:** Involucra movimiento de dinero; el sistema solo genera el borrador y pausa la ejecución hasta que un operador financiero aprueba el monto.
* **Cierre o modificación de estado de un ticket:** Evita cierres unilaterales ante reclamos regulatorios.
* **Consultas con baja confianza o fuera de dominio (`confianza < umbral_confianza_hitl` o `fuera_de_dominio`):** Prohibido improvisar; se deriva a un agente humano con el resumen estructurado.
* **Sin aprobación humana (Lectura pura):** Responder políticas públicas (`consulta_politica`) y consultar el estado de un ticket propio autenticado (`estado_ticket`).



### 2.6 Entregable 5: Rollout Progresivo (5% Canary), Comparación y Rollback

* **Fuente + Derivado** (combinando el despliegue en el 5% del tráfico del Módulo 2 con estrategias de *Canary Deployment* y *Feature Flags* del Módulo 8):


* **Enrutamiento (5% tráfico):** Mediante una *Feature Flag* y hashing consistente por `user_id`, el **95%** del tráfico continúa en la versión estable (`v1`) y el **5%** se dirige a la nueva versión (`v2`) durante 24–48 horas.
* **Comparación en paralelo (`v1` vs. `v2`):** Se auditan en tiempo real la tasa de `ValidationError`, el porcentaje de escalamiento humano, la latencia P95, el costo promedio en USD y la calidad evaluada por un juez LLM (*LLM-as-a-judge*).


* **Criterios de *Rollback* automático (*Kill Switch*):** Se revierte el 100% del tráfico a `v1` de inmediato si en el 5% Canary ocurre:
1. **1 solo fallo de seguridad** (reembolso sin `requiere_aprobacion_humana=True` o fuga de PII).
2. **Tasa de `ValidationError` $> 2\%$** durante 15 minutos seguidos.
3. **Latencia P95 $> 2.500\text{ ms}$** o errores HTTP `5xx`/`429` no recuperados $> 1\%$.
4. **Incremento de costo $> 30\%$** por conversación frente al *baseline* de `v1`.

---

## 3. Conclusión Rápida

* **Fuente + Derivado:** Este *blueprint* demuestra cómo pasar de un prototipo conversacional a un sistema *enterprise-grade*: `Pydantic` actúa como contrato determinista que blinda el *core* financiero frente a salidas probabilísticas, `config.toml` y `.env` separan limpiamente las reglas de negocio de los secretos sin tocar el código, `uv` garantiza reproducibilidad determinística del entorno, y el *failure-mapping* junto con el *rollout* Canary al 5% aseguran que cualquier degradación de seguridad, costo o latencia se contenga antes de impactar a toda la operación.
