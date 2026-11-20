**Módulo confirmado:** Semana 2 — LLMs en producción (Pre-Entrega 2: Motor LLM Base y Validación Estructurada).

## 1. Consigna Oficial: Pre-Entrega 2 ("Mi motor LLM")

* **Fuente:** Actividad evaluable del Módulo 2 destinada a construir el núcleo del sistema en Python (`src/motor.py`), conectando una consulta del caso de uso (definido en la PE1) con un modelo de lenguaje real para devolver una respuesta estructurada, validada y auditada en costo y latencia.
* **Estructura del repositorio (`fde-<tu-caso>`):** Incluir `README.md` (ejecutable desde un clon limpio), `requirements.txt`, `.env.example` (solo nombres de variables, sin valores), `.gitignore` (excluyendo `.env`) y `src/motor.py`, etiquetando el hito con `git tag pe2`.
* **Contratos de datos con Pydantic:** Definir las clases `Entrada` y `Salida` a partir de la historia de usuario de PE1 con al menos 3 reglas de validación significativas (`Enum`, rangos numéricos, patrones regex o largo mínimo).
* **Llamada real y plantilla desacoplada:** Invocar a un modelo real (OpenAI o Anthropic) leyendo la clave desde variable de entorno, manteniendo el *prompt* aislado en una plantilla separada (nunca embebido en la función) y validando la respuesta contra `Salida`.
* **Medición real sobre 5 consultas:** Ejecutar 5 consultas reales del caso (incluyendo una confusa y una fuera de tema), registrando tokens del campo `usage`, costo en USD según tarifas publicadas y latencia en milisegundos, calculando promedios y comparándolos contra la meta del KPI técnico de PE1.
* **Manejo de errores y resiliencia:** Registrar exactamente *qué campo* falló ante una salida inválida, ejecutar un único reintento y, si vuelve a fallar, devolver un error estructurado sin romper el sistema, capturando además errores de red o cuota de la API.

---

## 2. Solución de Referencia (Caso *TechStore* con `uv`, Groq y `config.toml`)

* **No consta en las fuentes:** El gestor de paquetes `uv`, el proveedor `Groq` y el uso de un archivo `config.toml` con `tomllib` no aparecen mencionados en el material del curso; las fuentes especifican entornos virtuales estándar (`venv`), `pip`, `requirements.txt`, los proveedores OpenAI o Anthropic, el aislamiento de credenciales en `.env` y la separación de plantillas de *prompts*.
* **Derivado:** Se adapta la arquitectura de la Pre-Entrega 2 para *TechStore* utilizando `uv` para el entorno determinístico (exportando `requirements.txt` mediante `uv export` para cumplir la rúbrica), `Groq` como proveedor de inferencia, y `config.toml` (validado al iniciar mediante `Pydantic`) para los parámetros operativos y reglas de negocio, dejando `.env` exclusivamente para `GROQ_API_KEY`.

> El código de esta solución ya está implementado en `fde-techstore-garantias/`. Esta sección documenta solo las decisiones técnicas.

### 2.1 Estructura del Repositorio, Secretos y Configuración

* **Estructura (`fde-techstore-garantias/`):**
  * `.env`: exclusivo para secretos; ignorado por Git.
  * `.env.example`: solo nombres de variables (`GROQ_API_KEY`), sin valores reales.
  * `.gitignore`: excluye `.env`, `.venv/` y `__pycache__/`.
  * `.python-version`: versión fijada de Python (3.11), gestionada por `uv`.
  * `config.toml`: parámetros del modelo Groq, tarifas, reintentos y umbrales de negocio.
  * `pyproject.toml`: definición del proyecto y dependencias principales.
  * `uv.lock`: *lockfile* determinístico generado por `uv`.
  * `requirements.txt`: exportado desde `uv` para cumplir estrictamente con la consigna PE2.
  * `README.md`: comandos reproducibles con `uv` desde un clon limpio.
  * `prompts/triaje_v1.txt`: plantilla de *system prompt* aislada del código.
  * `src/motor.py`: carga de `config.toml`, contratos Pydantic, Groq y telemetría.

* **`pyproject.toml` (Derivado):** requiere Python `>=3.11` y declara tres dependencias: `groq>=0.11.0`, `pydantic>=2.0.0` y `python-dotenv>=1.0.0`.

* **Secretos `.env.example` (Fuente + Derivado):** se renombra a `.env` y se completa localmente con `GROQ_API_KEY`; nunca se suben credenciales a Git.

* **Parámetros operativos `config.toml` (Derivado):** tres secciones.
  * `[llm]`: proveedor (`groq`), modelo (`llama-3.3-70b-versatile`), temperatura `0.0`, máximo de reintentos de validación (`1`) y ruta del *system prompt*.
  * `[tarifas_usd_por_millon]`: tarifas diferenciadas por tipo de token (input `0.59`, output `0.79`) para calcular el costo real según `usage`.
  * `[reglas_negocio]`: `umbral_aprobacion_supervisor_usd = 50.0`, definido en la Historia de Usuario 2 de PE1 para exigir Supervisor N2.

* **Flujo reproducible con `uv` (para documentar en `README.md` — Derivado):**
  1. Inicializar el proyecto con Python 3.11+ (requisito base y soporte nativo de `tomllib`).
  2. Agregar las dependencias estrictas del motor.
  3. Exportar `requirements.txt` sin hashes para compatibilidad con la rúbrica de PE2.
  4. Copiar `.env.example` a `.env` (solo secretos).
  5. Ejecutar `src/motor.py` con `uv run`, dentro del entorno aislado y sin activación manual.
  6. Etiquetar el repositorio con `git tag pe2` una vez verificada la ejecución.

### 2.2 Plantilla de Prompt Separada (`prompts/triaje_v1.txt`)

* **Rol (Derivado):** asistente interno de triaje post-venta de TechStore. Evalúa reclamos de garantía y devolución para generar un borrador en el CRM; nunca aprueba pagos definitivos.
* **Reglas de negocio obligatorias:**
  1. **Plazo estándar:** devolución hasta 30 días desde la entrega. Pasado ese plazo, requiere evaluación de garantía por marca.
  2. **Faltan documentos:** si `tiene_factura_y_foto` es `False`, clasificar como `faltan_datos`, fijar `monto_reintegro_sugerido` en `0.0` y pedir exclusivamente los documentos faltantes.
  3. **Umbral financiero:** si `monto_reintegro_sugerido` supera `{umbral_supervisor}` USD, `requiere_aprobacion_supervisor` debe ser `True`.
  4. **Ambigüedad:** si la consulta es ambigua, contradictoria o fuera de tema, clasificar como `requiere_revision_manual` y fijar el monto en `0.0`. Nunca inventar cláusulas ni coberturas.
* **Formato de salida:** únicamente un objeto JSON válido que respete el esquema inyectado en el marcador `{schema_json}`.
* **Marcadores dinámicos:** `{umbral_supervisor}` se completa desde `config.toml` y `{schema_json}` desde `Salida.model_json_schema()`; así ninguna regla numérica queda hardcodeada en el texto.

### 2.3 Contratos Pydantic y Motor LLM Base (`src/motor.py`)

**Carga de configuración**

* Los secretos se cargan solo desde `.env` (`load_dotenv`); la configuración operativa viene de `config.toml`.
* Modelos Pydantic anidados validan el TOML al arrancar: `LLMConfig`, `TarifasConfig`, `ReglasNegocioConfig` y `AppConfig`.
* Restricciones: `temperatura` entre 0 y 2, `max_reintentos_validacion` entre 0 y 3, tarifas y umbral `> 0`.
* `tomllib` exige abrir el archivo en binario (`rb`). La ruta se resuelve relativa al proyecto, no al directorio de ejecución.

**Enums**

* `RolOperador`: `analista_n1`, `supervisor_n2`.
* `EstadoTriaje`: `elegible_borrador`, `no_elegible`, `faltan_datos`, `requiere_revision_manual`.

**Contrato `Entrada`**

| Campo | Tipo / restricción | Regla que cubre |
| --- | --- | --- |
| `ticket_id` | `str`, patrón `^TCK-\d{4,6}$` | **Patrón:** valida el formato del ID de CRM antes de gastar tokens |
| `mensaje_cliente` | `str`, `min_length=15` | **Largo mínimo:** evita consumir tokens con mensajes vacíos o sin contexto |
| `dias_desde_entrega` | `int`, `>= 0` | **Rango:** impide días negativos en el cálculo de vigencia |
| `monto_pagado_usd` | `float`, `> 0` | Monto abonado en USD |
| `tiene_factura_y_foto` | `bool` | Indica si adjuntó comprobante y foto |
| `rol_ejecutor` | `RolOperador`, por defecto `analista_n1` | **Enum:** restringe el rol del operador |

**Contrato `Salida`**

| Campo | Tipo / restricción |
| --- | --- |
| `estado` | `EstadoTriaje` |
| `clausula_citada` | `str`, `min_length=5` (artículo citado o `N/A`) |
| `monto_reintegro_sugerido` | `float`, `>= 0` |
| `requiere_aprobacion_supervisor` | `bool` |
| `respuesta_sugerida` | `str`, `min_length=15` |
| `confianza` | `float`, entre 0 y 1 |

**Reglas de negocio (`@model_validator(mode="after")` en `Salida`)**

1. Todo reintegro mayor al umbral de `config.toml` exige `requiere_aprobacion_supervisor=True`. El umbral se lee de la config, no se hardcodea.
2. Si el estado es `faltan_datos` o `no_elegible`, `monto_reintegro_sugerido` debe ser `0.0`.

**Flujo de ejecución (`procesar_ticket`)**

1. **Validación temprana de entrada:** si `Entrada` falla, devuelve error de etapa `VALIDACION_ENTRADA` con tokens, costo y latencia en cero, sin llamar a la API.
2. Verifica `GROQ_API_KEY`; si falta, devuelve error de etapa `CONFIGURACION`.
3. Arma el *system prompt* desde la plantilla (inyecta esquema y umbral) y un *user prompt* con los datos del ticket.
4. Bucle de `1 + max_reintentos_validacion` intentos contra Groq con temperatura de config y `response_format` JSON.
5. Captura `RateLimitError`, `APIConnectionError` y `APIError` y devuelve error de etapa `INFRAESTRUCTURA_API`.
6. Acumula `prompt_tokens`, `completion_tokens` y latencia (`time.perf_counter`) a través de los intentos.
7. Si `Salida.model_validate_json` pasa, devuelve salida más telemetría: tokens, costo en USD y latencia en ms.
8. Si falla `ValidationError`, `formatear_errores` extrae `campo` (desde `loc`), `tipo` y `mensaje`. Registra un log y reinyecta esos errores en el prompt del siguiente intento (reintento guiado).
9. Agotados los intentos, devuelve error de etapa `VALIDACION_SALIDA` con los errores, intentos y telemetría acumulada.

**Costo:** `(tokens_in / 1M × tarifa_input) + (tokens_out / 1M × tarifa_output)`, redondeado a 6 decimales.

**Las 5 consultas de prueba (`__main__`)**

| # | Ticket | Caso | Qué ejercita |
| --- | --- | --- | --- |
| 1 | `TCK-1001` | Válida, monto menor al umbral (35 USD) | Flujo feliz sin supervisor |
| 2 | `TCK-1002` | Válida, monto mayor al umbral (240 USD) | Exige aprobación de Supervisor N2 |
| 3 | `TCK-1003` | Faltan factura y foto | Estado `faltan_datos`, monto `0.0` |
| 4 | `TCK-1004` | Confusa / ambigua | Estado `requiere_revision_manual` |
| 5 | `TCK-1005` | Fuera de tema (receta de pan) | Estado `requiere_revision_manual` |

### 2.4 Criterios de Verificación y Casos Límite

* **Criterios de aceptación (Derivado — basado en la rúbrica de PE2):**
1. **Reproducibilidad desde clon limpio:** Clonar el repositorio en un directorio vacío y comprobar que `uv sync` instala las versiones exactas de `uv.lock` y `uv run python src/motor.py` valida `config.toml` y ejecuta las 5 consultas contra Groq sin errores.
2. **Compatibilidad de evaluación:** Verificar que `requirements.txt` está sincronizado mediante `uv export` para que cualquier entorno que instale con `pip install -r requirements.txt` funcione sin fallos.
3. **Evidencia de error controlado:** Forzar un incumplimiento de regla (ej. monto $> \text{umbral\_aprobacion\_supervisor\_usd}$ con `requiere_aprobacion_supervisor=False`) para capturar en terminal el registro de `loc`/`msg`, el reintento guiado y el JSON de error estructurado exigido en el PDF.

* **Casos límite y errores comunes (Derivado — aplicando los anti-patterns de Semana 2 a *TechStore*):**
1. **Desincronización entre `uv.lock` y `requirements.txt`**
* *Síntoma:* El proyecto corre con `uv run`, pero falla en la revisión docente al usar `pip install -r requirements.txt`.
* *Causa:* Agregar paquetes con `uv add` y olvidar re-exportar `requirements.txt` antes del commit etiquetado como `pe2`.
* *Corrección:* Ejecutar `uv export --no-hashes --format requirements-txt -o requirements.txt` como paso obligatorio previo al `git tag pe2`.

2. **Parámetros corruptos o faltantes en `config.toml`**
* *Síntoma:* El motor falla a mitad de ejecución con un `KeyError` o calcula costos negativos si alguien edita mal el archivo TOML.
* *Causa:* Leer el diccionario de configuración sin validar tipos ni rangos al arrancar la aplicación.
* *Corrección:* Validar el contenido de `tomllib.load()` mediante `AppConfig.model_validate()` al importar el módulo, aplicando el principio de validación temprana de `Pydantic`.

3. **Evasión del umbral de aprobación de Supervisor N2**
* *Síntoma:* El modelo sugiere un reintegro superior al umbral configurado pero devuelve `requiere_aprobacion_supervisor=False`.
* *Causa:* Confiar únicamente en que el *system prompt* mencione la regla financiera.
* *Corrección:* Enforzar la regla mediante `@model_validator(mode="after")` en `Salida` leyendo `CONFIG.reglas_negocio.umbral_aprobacion_supervisor_usd`.

4. **Reintento ciego sin retroalimentación de campo (`loc`)**
* *Síntoma:* El segundo intento vuelve a fallar la validación duplicando el gasto de tokens.
* *Causa:* Reinvocar la API de Groq con el mismo mensaje original sin extraer `loc` y `msg` de `ValidationError.errors()`.
* *Corrección:* Serializar la ubicación exacta del error e inyectarla en el prompt del segundo intento para guiar la autocorrección.

---

## 3. Conclusión Rápida

* **Fuente + Derivado:** Esta implementación resuelve el núcleo de la Pre-Entrega 2 sobre el caso *TechStore* conectando la naturaleza probabilística del LLM (ejecutado vía Groq) con las reglas deterministas del CRM mediante contratos estrictos en `Pydantic`, auditoría real de `usage` (tokens, costo en USD y latencia en ms) y reintento único guiado por campo fallido, mientras que `config.toml` desacopla los parámetros operativos y umbrales de negocio de los secretos en `.env` y `uv` garantiza reproducibilidad determinística del entorno sin perder compatibilidad con `requirements.txt`.
