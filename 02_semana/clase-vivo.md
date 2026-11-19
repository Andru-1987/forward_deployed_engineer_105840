**Módulo confirmado:** Semana 2 — LLMs en producción.

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



### 2.1 Estructura del Proyecto, Secretos y Configuración

```text
fintech-soporte-blueprint/
├── .env                  # EXCLUSIVO para secretos (ignorado por Git)
├── .env.example          # Plantilla vacía de credenciales (GROQ_API_KEY=)
├── .gitignore            # Excluye .env, .venv/ y __pycache__/
├── config.toml           # Parámetros del modelo, tarifas, reintentos y umbrales de negocio
├── pyproject.toml        # Dependencias gestionadas con uv (groq, pydantic, python-dotenv)
├── requirements.txt      # Exportado con uv para compatibilidad estándar
├── prompts/
│   └── triaje_v1.txt     # System prompt aislado de la lógica de ejecución
└── src/
    └── motor.py          # Carga de config.toml, validación Pydantic y ejecución en Groq

```

* **Comandos de inicialización con `uv` (Derivado):**

```bash
uv init --python 3.11 fintech-soporte-blueprint
cd fintech-soporte-blueprint
uv add groq pydantic python-dotenv
uv export --no-hashes --format requirements-txt -o requirements.txt

```

* **Archivo de secretos `.env.example` (Fuente + Derivado):**

```ini
# Solo nombres de variables; nunca subir valores reales al repositorio
GROQ_API_KEY=

```

* **Archivo de parámetros operativos `config.toml` (Derivado):**

```toml
[llm]
proveedor = "groq"
modelo = "llama-3.3-70b-versatile"
temperatura = 0.0
max_reintentos_validacion = 1
ruta_system_prompt = "prompts/triaje_v1.txt"

[tarifas_usd_por_millon]
# Tarifas diferenciadas por tipo de token para auditar el costo real
input = 0.59
output = 0.79

[reglas_negocio]
monto_maximo_reembolso_usd = 5000.0
umbral_confianza_hitl = 0.75

```

* **Plantilla de *prompt* aislada `prompts/triaje_v1.txt` (Derivado):**

```text
Eres el asistente de soporte de una Fintech. Solo puedes atender:
1. consulta_politica (citando fuente_politica).
2. estado_ticket (requiere ticket_id TKT-######).
3. reembolso_parcial (siempre requiere_aprobacion_humana=true).
Si la consulta es ajena a la Fintech, usa fuera_de_dominio.
Responde ÚNICAMENTE con un objeto JSON válido que cumpla este esquema:
{schema}

```

### 2.2 Entregable 1: Schema Pydantic de Salida y Motor (`src/motor.py`)

* **Derivado** (aplicando `BaseModel`, `Enum`, `Field`, `@model_validator`, extracción de `loc`/`msg` en `ValidationError` y medición de tokens/latencia del Módulo 2):



```python
import os
import time
import tomllib
from enum import Enum
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from groq import Groq, APIError, RateLimitError
from pydantic import BaseModel, Field, ValidationError, model_validator

# Carga exclusiva de secretos desde .env; la configuración operativa viene de TOML
load_dotenv()


class LLMConfig(BaseModel):
    proveedor: str
    modelo: str
    temperatura: float = Field(ge=0.0, le=2.0)
    max_reintentos_validacion: int = Field(ge=0, le=3)
    ruta_system_prompt: str


class TarifasConfig(BaseModel):
    input: float = Field(gt=0.0)
    output: float = Field(gt=0.0)


class ReglasNegocioConfig(BaseModel):
    monto_maximo_reembolso_usd: float = Field(gt=0.0)
    umbral_confianza_hitl: float = Field(ge=0.0, le=1.0)


class AppConfig(BaseModel):
    llm: LLMConfig
    tarifas_usd_por_millon: TarifasConfig
    reglas_negocio: ReglasNegocioConfig


def cargar_configuracion(ruta_toml: str = "config.toml") -> AppConfig:
    # tomllib requiere apertura en binario ('rb') y Pydantic valida los tipos al iniciar
    ruta = Path(__file__).resolve().parent.parent / ruta_toml
    with ruta.open("rb") as f:
        return AppConfig.model_validate(tomllib.load(f))


CONFIG = cargar_configuracion()


class IntencionSoporte(str, Enum):
    # Restringe las salidas posibles exclusivamente a los casos permitidos por la fintech
    consulta_politica = "consulta_politica"
    estado_ticket = "estado_ticket"
    reembolso_parcial = "reembolso_parcial"
    fuera_de_dominio = "fuera_de_dominio"


class SalidaFintech(BaseModel):
    intencion: IntencionSoporte
    # Obliga a citar fuente documental para mitigar alucinaciones en políticas
    fuente_politica: Optional[str] = Field(
        default=None,
        description="Sección del documento de políticas citado, o None si no aplica",
    )
    # Patrón estricto para prevenir inyecciones o IDs malformados hacia el CRM
    ticket_id: Optional[str] = Field(
        default=None,
        pattern=r"^TKT-\d{6}$",
        description="Identificador del ticket en formato TKT-123456",
    )
    # El límite máximo se lee dinámicamente desde config.toml
    monto_reembolso_usd: float = Field(
        default=0.0,
        ge=0.0,
        le=CONFIG.reglas_negocio.monto_maximo_reembolso_usd,
    )
    requiere_aprobacion_humana: bool
    respuesta_usuario: str = Field(..., min_length=15)
    confianza: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validar_reglas_fintech(self) -> "SalidaFintech":
        # Regla 1: Todo movimiento de dinero exige validación humana (Human-in-the-Loop)
        if self.intencion == IntencionSoporte.reembolso_parcial:
            if self.monto_reembolso_usd <= 0:
                raise ValueError("Un reembolso_parcial exige monto_reembolso_usd > 0")
            if not self.requiere_aprobacion_humana:
                raise ValueError("Todo reembolso_parcial debe marcar requiere_aprobacion_humana=True")

        # Regla 2: Impide disparar importes monetarios en consultas informativas
        if self.intencion != IntencionSoporte.reembolso_parcial and self.monto_reembolso_usd > 0:
            raise ValueError("Solo la intención reembolso_parcial admite monto_reembolso_usd > 0")

        # Regla 3: Escala automáticamente a humano si la confianza cae bajo el umbral configurado
        umbral = CONFIG.reglas_negocio.umbral_confianza_hitl
        if self.confianza < umbral and not self.requiere_aprobacion_humana:
            raise ValueError(f"Confianza menor a {umbral} requiere supervisión humana obligatoria")

        return self


def cargar_system_prompt() -> str:
    ruta_prompt = Path(__file__).resolve().parent.parent / CONFIG.llm.ruta_system_prompt
    plantilla = ruta_prompt.read_text(encoding="utf-8")
    return plantilla.format(schema=SalidaFintech.model_json_schema())


def calcular_costo_usd(tokens_in: int, tokens_out: int) -> float:
    costo_in = (tokens_in / 1_000_000) * CONFIG.tarifas_usd_por_millon.input
    costo_out = (tokens_out / 1_000_000) * CONFIG.tarifas_usd_por_millon.output
    return round(costo_in + costo_out, 6)


def ejecutar_turno_fintech(consulta_usuario: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"ok": False, "etapa": "CONFIGURACION", "detalle": "Falta GROQ_API_KEY en .env"}

    cliente = Groq(api_key=api_key)
    prompt_sistema = cargar_system_prompt()
    prompt_actual = consulta_usuario
    total_intentos = 1 + CONFIG.llm.max_reintentos_validacion
    errores = []

    for intento in range(1, total_intentos + 1):
        inicio = time.perf_counter()
        try:
            resp = cliente.chat.completions.create(
                model=CONFIG.llm.modelo,
                temperature=CONFIG.llm.temperatura,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_actual},
                ],
            )
        except (RateLimitError, APIError) as err_api:
            # Captura controlada de fallos de red o límites de cuota del proveedor
            return {"ok": False, "etapa": "INFRAESTRUCTURA_API", "detalle": str(err_api)}

        latencia_ms = int((time.perf_counter() - inicio) * 1000)
        tokens_in = resp.usage.prompt_tokens
        tokens_out = resp.usage.completion_tokens

        try:
            salida = SalidaFintech.model_validate_json(resp.choices[0].message.content)
            return {
                "ok": True,
                "modelo": CONFIG.llm.modelo,
                "intento": intento,
                "datos": salida.model_dump(),
                "telemetria": {
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "costo_usd": calcular_costo_usd(tokens_in, tokens_out),
                    "latencia_ms": latencia_ms,
                },
            }
        except ValidationError as e:
            # Extrae ubicación exacta (loc) y explicación (msg) para guiar el reintento
            errores = [
                {"campo": " -> ".join(map(str, err["loc"])), "motivo": err["msg"]}
                for err in e.errors()
            ]
            prompt_actual = (
                f"{consulta_usuario}\n\n"
                f"ERROR DE VALIDACIÓN EN TU RESPUESTA ANTERIOR: {errores}. "
                f"Corrígelo y devuelve solo el JSON."
            )

    return {"ok": False, "etapa": "VALIDACION_SALIDA", "errores": errores}


if __name__ == "__main__":
    print(
        ejecutar_turno_fintech(
            "Quiero pedir un reembolso parcial de 150 dolares por un cobro duplicado en el ticket TKT-482910."
        )
    )

```

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
