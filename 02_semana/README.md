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



### 2.1 Estructura del Repositorio, Secretos y Configuración

```text
fde-techstore-garantias/
├── .env                  # EXCLUSIVO para secretos (ignorado por Git)
├── .env.example          # Solo nombres de variables (GROQ_API_KEY=), sin valores reales
├── .gitignore            # Excluye .env, .venv/ y __pycache__/
├── .python-version       # Versión fijada de Python (3.11) gestionada por uv
├── config.toml           # Parámetros de modelo Groq, tarifas, reintentos y umbrales de negocio
├── pyproject.toml        # Definición del proyecto y dependencias principales
├── uv.lock               # Lockfile determinístico generado por uv
├── requirements.txt      # Exportado desde uv para cumplir estrictamente con la consigna PE2
├── README.md             # Comandos reproducibles con uv desde un clon limpio
├── prompts/
│   └── triaje_v1.txt     # Plantilla de system prompt aislada del código
└── src/
    └── motor.py          # Carga de config.toml, contratos Pydantic, Groq y telemetría

```

* **Configuración del proyecto (`pyproject.toml` — Derivado):**

```toml
[project]
name = "fde-techstore-garantias"
version = "0.1.0"
description = "Motor LLM base con Groq, validación Pydantic y config.toml para triaje de garantías de TechStore (PE2)"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "groq>=0.11.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
]

```

* **Archivo de secretos (`.env.example` — Fuente + Derivado):**

```ini
# Renombrar a .env y completar localmente; nunca subir credenciales a Git
GROQ_API_KEY=

```

* **Archivo de parámetros operativos (`config.toml` — Derivado):**

```toml
[llm]
proveedor = "groq"
modelo = "llama-3.3-70b-versatile"
temperatura = 0.0
max_reintentos_validacion = 1
ruta_system_prompt = "prompts/triaje_v1.txt"

[tarifas_usd_por_millon]
# Tarifas diferenciadas por tipo de token para calcular el costo real según usage
input = 0.59
output = 0.79

[reglas_negocio]
# Umbral definido en Historia de Usuario 2 de PE1 para exigir Supervisor N2
umbral_aprobacion_supervisor_usd = 50.0

```

* **Comandos reproducibles con `uv` (para documentar en `README.md` — Derivado):**

```bash
# 1. Inicializar el proyecto con Python 3.11+ (requisito base y soporte nativo de tomllib)
uv init --python 3.11

# 2. Instalar las dependencias estrictas del motor
uv add groq pydantic python-dotenv

# 3. Exportar requirements.txt para compatibilidad con la rúbrica de Pre-Entrega 2
uv export --no-hashes --format requirements-txt -o requirements.txt

# 4. Configurar variables de entorno locales (solo secretos)
cp .env.example .env

# 5. Ejecutar el motor dentro del entorno aislado sin activación manual
uv run python src/motor.py

# 6. Etiquetar el repositorio una vez verificada la ejecución
git tag pe2

```

### 2.2 Plantilla de Prompt Separada (`prompts/triaje_v1.txt`)

```text
Eres el asistente interno de triaje post-venta de TechStore.
Tu función es evaluar reclamos de garantía y devolución para generar un borrador en el CRM (nunca apruebas pagos definitivos).

REGLAS DE NEGOCIO OBLIGATORIAS:
1. Plazo estándar de devolución: hasta 30 días desde la entrega. Pasado ese plazo, requiere evaluación de garantía por marca.
2. Si `tiene_factura_y_foto` es False, debes clasificar como `faltan_datos`, fijar `monto_reintegro_sugerido` en 0.0 y redactar un mensaje solicitando exclusivamente los documentos faltantes.
3. Si `monto_reintegro_sugerido` supera los {umbral_supervisor} USD, `requiere_aprobacion_supervisor` debe ser True.
4. Si la consulta es ambigua, contradictoria o fuera de tema, clasifica como `requiere_revision_manual` y fija `monto_reintegro_sugerido` en 0.0. Nunca inventes cláusulas ni coberturas.

Responde ÚNICAMENTE con un objeto JSON válido que respete este esquema:
{schema_json}

```

### 2.3 Contratos Pydantic y Motor LLM Base (`src/motor.py`)

```python
import os
import time
import tomllib
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq, APIError, RateLimitError, APIConnectionError
from pydantic import BaseModel, Field, ValidationError, model_validator

# Carga exclusiva de secretos desde .env; la configuración operativa viene de config.toml
load_dotenv()


# --- 1. Esquemas Pydantic para validar config.toml al arrancar ---
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
    umbral_aprobacion_supervisor_usd: float = Field(gt=0.0)


class AppConfig(BaseModel):
    llm: LLMConfig
    tarifas_usd_por_millon: TarifasConfig
    reglas_negocio: ReglasNegocioConfig


def cargar_configuracion(ruta_toml: str = "config.toml") -> AppConfig:
    # tomllib requiere apertura en binario ('rb') y Pydantic asegura que los parámetros sean válidos
    ruta = Path(__file__).resolve().parent.parent / ruta_toml
    with ruta.open("rb") as f:
        return AppConfig.model_validate(tomllib.load(f))


CONFIG = cargar_configuracion()


# --- 2. Contratos de Entrada y Salida del Motor ---
class RolOperador(str, Enum):
    analista_n1 = "analista_n1"
    supervisor_n2 = "supervisor_n2"


class EstadoTriaje(str, Enum):
    elegible_borrador = "elegible_borrador"
    no_elegible = "no_elegible"
    faltan_datos = "faltan_datos"
    requiere_revision_manual = "requiere_revision_manual"


class Entrada(BaseModel):
    # Regla 1 (Patrón): Valida formato de ID de ticket del CRM antes de gastar tokens
    ticket_id: str = Field(..., pattern=r"^TCK-\d{4,6}$", description="ID anonimizado del ticket")
    # Regla 2 (Largo mínimo): Evita consumir tokens con mensajes vacíos o sin contexto
    mensaje_cliente: str = Field(..., min_length=15, description="Descripción del reclamo")
    # Regla 3 (Rango): Impide días negativos en el cálculo de vigencia de garantía
    dias_desde_entrega: int = Field(..., ge=0, description="Días transcurridos desde la recepción")
    monto_pagado_usd: float = Field(..., gt=0, description="Monto abonado en USD")
    tiene_factura_y_foto: bool = Field(..., description="Indica si adjuntó comprobante y foto")
    rol_ejecutor: RolOperador = Field(default=RolOperador.analista_n1)


class Salida(BaseModel):
    estado: EstadoTriaje
    clausula_citada: str = Field(..., min_length=5, description="Artículo citado o 'N/A'")
    monto_reintegro_sugerido: float = Field(..., ge=0.0)
    requiere_aprobacion_supervisor: bool
    respuesta_sugerida: str = Field(..., min_length=15)
    confianza: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validar_reglas_negocio(self) -> "Salida":
        # El umbral financiero se lee desde config.toml para evitar hardcodear reglas de negocio
        umbral = CONFIG.reglas_negocio.umbral_aprobacion_supervisor_usd
        if self.monto_reintegro_sugerido > umbral and not self.requiere_aprobacion_supervisor:
            raise ValueError(
                f"Todo reintegro mayor a {umbral} USD exige requiere_aprobacion_supervisor=True"
            )
        # Evita sugerir devolución monetaria cuando faltan documentos o el caso no aplica
        if self.estado in (EstadoTriaje.faltan_datos, EstadoTriaje.no_elegible) and self.monto_reintegro_sugerido > 0:
            raise ValueError(
                f"Si el estado es {self.estado.value}, monto_reintegro_sugerido debe ser 0.0"
            )
        return self


def cargar_plantilla_prompt() -> str:
    # Desacopla la plantilla de instrucciones del código usando la ruta definida en config.toml
    ruta = Path(__file__).resolve().parent.parent / CONFIG.llm.ruta_system_prompt
    return ruta.read_text(encoding="utf-8")


def calcular_costo_usd(tokens_entrada: int, tokens_salida: int) -> float:
    costo = (
        (tokens_entrada / 1_000_000) * CONFIG.tarifas_usd_por_millon.input
        + (tokens_salida / 1_000_000) * CONFIG.tarifas_usd_por_millon.output
    )
    return round(costo, 6)


def formatear_errores(err: ValidationError) -> list[dict]:
    # Extrae la ruta exacta (loc) y el motivo (msg) para trazabilidad y reintento guiado
    return [
        {
            "campo": " -> ".join(map(str, e["loc"])) or "(json_completo)",
            "tipo": e["type"],
            "mensaje": e["msg"],
        }
        for e in err.errors()
    ]


def procesar_ticket(datos_crudos: dict) -> dict:
    # Validación temprana de entrada para evitar llamadas inútiles a la API
    try:
        entrada = Entrada.model_validate(datos_crudos)
    except ValidationError as err_in:
        return {
            "ok": False,
            "etapa": "VALIDACION_ENTRADA",
            "errores": formatear_errores(err_in),
            "tokens": {"entrada": 0, "salida": 0},
            "costo_usd": 0.0,
            "latencia_ms": 0,
        }

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "etapa": "CONFIGURACION",
            "detalle": "Falta la variable de entorno GROQ_API_KEY en .env",
        }

    cliente = Groq(api_key=api_key)
    system_prompt = cargar_plantilla_prompt().format(
        schema_json=Salida.model_json_schema(),
        umbral_supervisor=CONFIG.reglas_negocio.umbral_aprobacion_supervisor_usd,
    )
    user_prompt = (
        f"Ticket: {entrada.ticket_id} | Días desde entrega: {entrada.dias_desde_entrega} | "
        f"Monto pagado: ${entrada.monto_pagado_usd} USD | Adjuntos completos: {entrada.tiene_factura_y_foto} | "
        f"Rol operador: {entrada.rol_ejecutor.value}\n"
        f"Mensaje del cliente: {entrada.mensaje_cliente}"
    )

    tokens_in_total, tokens_out_total, latencia_total = 0, 0, 0
    ultimos_errores = []
    total_intentos = 1 + CONFIG.llm.max_reintentos_validacion

    # Política acotada de reintentos configurada en config.toml con feedback de campos fallidos
    for intento in range(1, total_intentos + 1):
        inicio = time.perf_counter()
        try:
            respuesta = cliente.chat.completions.create(
                model=CONFIG.llm.modelo,
                temperature=CONFIG.llm.temperatura,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except (RateLimitError, APIConnectionError, APIError) as err_api:
            return {
                "ok": False,
                "etapa": "INFRAESTRUCTURA_API",
                "detalle": str(err_api),
                "intento": intento,
            }

        latencia_total += int((time.perf_counter() - inicio) * 1000)
        tokens_in_total += respuesta.usage.prompt_tokens
        tokens_out_total += respuesta.usage.completion_tokens
        contenido_json = respuesta.choices[0].message.content

        try:
            salida_valida = Salida.model_validate_json(contenido_json)
            return {
                "ok": True,
                "proveedor": CONFIG.llm.proveedor,
                "modelo": CONFIG.llm.modelo,
                "intento": intento,
                "salida": salida_valida.model_dump(),
                "tokens": {"entrada": tokens_in_total, "salida": tokens_out_total},
                "costo_usd": calcular_costo_usd(tokens_in_total, tokens_out_total),
                "latencia_ms": latencia_total,
            }
        except ValidationError as err_out:
            ultimos_errores = formatear_errores(err_out)
            print(f"[LOG] Intento {intento} inválido. Detalle: {ultimos_errores}")
            user_prompt += (
                f"\n\nCORRECCIÓN REQUERIDA: Tu JSON anterior incumplió estas reglas: "
                f"{ultimos_errores}. Corrígelas y responde solo con el JSON."
            )

    return {
        "ok": False,
        "etapa": "VALIDACION_SALIDA",
        "errores": ultimos_errores,
        "intento": total_intentos,
        "tokens": {"entrada": tokens_in_total, "salida": tokens_out_total},
        "costo_usd": calcular_costo_usd(tokens_in_total, tokens_out_total),
        "latencia_ms": latencia_total,
    }


if __name__ == "__main__":
    consultas_prueba = [
        # 1. Válida (< umbral configurado en config.toml)
        {
            "ticket_id": "TCK-1001",
            "mensaje_cliente": "Los auriculares dejaron de sonar del lado izquierdo a los 10 días de recibirlos.",
            "dias_desde_entrega": 10,
            "monto_pagado_usd": 35.0,
            "tiene_factura_y_foto": True,
            "rol_ejecutor": "analista_n1",
        },
        # 2. Válida (> umbral configurado -> requiere aprobación de Supervisor N2)
        {
            "ticket_id": "TCK-1002",
            "mensaje_cliente": "El monitor llegó con una línea de píxeles muertos en el centro de la pantalla.",
            "dias_desde_entrega": 15,
            "monto_pagado_usd": 240.0,
            "tiene_factura_y_foto": True,
            "rol_ejecutor": "analista_n1",
        },
        # 3. Válida (Faltan datos obligatorios)
        {
            "ticket_id": "TCK-1003",
            "mensaje_cliente": "Quiero devolver el teclado mecánico que compré la semana pasada, no me gustó.",
            "dias_desde_entrega": 7,
            "monto_pagado_usd": 80.0,
            "tiene_factura_y_foto": False,
            "rol_ejecutor": "analista_n1",
        },
        # 4. Confusa / Ambigua
        {
            "ticket_id": "TCK-1004",
            "mensaje_cliente": "El cargador a veces carga y a veces no, creo que lo compré hace 4 meses pero tiré la caja.",
            "dias_desde_entrega": 125,
            "monto_pagado_usd": 25.0,
            "tiene_factura_y_foto": False,
            "rol_ejecutor": "analista_n1",
        },
        # 5. Fuera de tema
        {
            "ticket_id": "TCK-1005",
            "mensaje_cliente": "Hola, me podrian pasar la receta para hacer pan casero o el horario del local?",
            "dias_desde_entrega": 0,
            "monto_pagado_usd": 10.0,
            "tiene_factura_y_foto": False,
            "rol_ejecutor": "analista_n1",
        },
    ]

    for idx, caso in enumerate(consultas_prueba, start=1):
        print(f"\n--- Ejecutando Consulta {idx} ({caso['ticket_id']}) ---")
        resultado = procesar_ticket(caso)
        print(resultado)

```

### 2.4 Criterios de Verificación y Casos Límite

* **Criterios de aceptación (Derivado — basado en la rúbrica de PE2):**
1. **Reproducibilidad desde clon limpio:** Clonar el repositorio en un directorio vacío y comprobar que `uv sync` instala las versiones exactas de `uv.lock` y `uv run python src/motor.py` valida `config.toml` y ejecuta las 5 consultas contra Groq sin errores.
2. **Compatibilidad de evaluación:** Verificar que `requirements.txt` está sincronizado mediante `uv export` para que cualquier entorno que instale con `pip install -r requirements.txt` funcione sin fallos.
3. **Evidencia de error controlado:** Forzar un incumplimiento de regla (ej. monto $> \text{umbral\_aprobacion\_supervisor\_usd}$ con `requiere_aprobacion_supervisor=False`) para capturar en terminal el registro de `loc`/`msg`, el reintento guiado y el JSON de error estructurado exigido en el PDF.




* **Casos límite y errores comunes (Derivado — aplicando los anti-patterns de Semana 2 a *TechStore*):**
1. **Desincronización entre `uv.lock` y `requirements.txt**`
* *Síntoma:* El proyecto corre con `uv run`, pero falla en la revisión docente al usar `pip install -r requirements.txt`.
* *Causa:* Agregar paquetes con `uv add` y olvidar re-exportar `requirements.txt` antes del commit etiquetado como `pe2`.
* *Corrección:* Ejecutar `uv export --no-hashes --format requirements-txt -o requirements.txt` como paso obligatorio previo al `git tag pe2`.




2. **Parámetros corruptos o faltantes en `config.toml**`
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
