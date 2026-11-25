# fde-tiendasur · Motor LLM base (Preentrega 2)

Ejemplo resuelto de la Preentrega 2 del curso Forward Deployed Engineer.
El motor recibe la consulta de un cliente de TiendaSur, se la pasa a un modelo real y devuelve
una respuesta **validada con Pydantic**, junto con **tokens, costo en USD y latencia en ms**.

Podés elegir entre **cuatro proveedores** sin tocar el motor:

| Proveedor | Modelo del ejemplo | Plan | Clave en `.env` | Dónde se crea la clave |
|---|---|---|---|---|
| Groq | `openai/gpt-oss-20b` | gratis, con límites de uso | `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
| Google | `gemini-3.1-flash-lite` | gratis, con límites de uso | `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| OpenAI | `gpt-6-luna` | pago (prepago desde 5 USD) | `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Anthropic | `claude-haiku-5-5` | pago (prepago desde 5 USD) | `ANTHROPIC_API_KEY` | [platform.claude.com](https://platform.claude.com) |

Viene configurado con **Groq**, que no pide tarjeta. Modelos y precios son los publicados en
noviembre de 2026: verificalos en la página de cada proveedor antes de medir.

> Es un ejemplo para estudiar. Tu PE2 tiene que salir de **tu** historia de usuario de la PE1.

## Historia de usuario (PE1)

Como agente de atención de TiendaSur, quiero que cada consulta llegue clasificada y con una
respuesta sugerida, para contestar más rápido y derivar a una persona solo los casos que lo necesitan.

## Contrato de datos (`src/contratos.py`)

| Clase | Campo | Regla de validación |
|---|---|---|
| Entrada | `consulta` | texto de 10 a 1000 caracteres |
| Entrada | `id_pedido` | opcional, formato `PED-12345` (patrón) |
| Salida | `categoria` | solo `estado_pedido`, `cambio`, `devolucion` u `otra` (Enum) |
| Salida | `respuesta_sugerida` | texto de 20 a 600 caracteres |
| Salida | `requiere_humano` | verdadero o falso |
| Salida | `confianza` | número entre 0 y 1 (rango) |
| Salida | regla de negocio | si la categoría es `otra` o la confianza es menor a 0.6, `requiere_humano` tiene que ser `true` |
| Salida | campos extra | prohibidos: el modelo no puede inventar campos |

## Estructura

```
fde-tiendasur/
├── README.md               este archivo
├── requirements.txt        dependencias (exportadas con uv)
├── pyproject.toml / uv.lock
├── .env.example            nombres de las claves, sin valores
├── .gitignore              incluye .env
├── config.toml             proveedor activo, modelos, precios, reintentos y metas del KPI
├── prompts/sistema_v1.txt  el prompt, separado del código
├── src/
│   ├── contratos.py        Entrada y Salida (Pydantic)
│   ├── motor.py            validar → llamar al modelo → validar → medir
│   ├── proveedores.py      cómo hablar con OpenAI, Anthropic, Google y Groq
│   ├── configuracion.py    lee .env y config.toml
│   ├── medir.py            corre las 5 consultas y arma la tabla
│   ├── demo_reintento.py   muestra el reintento sin API key
│   └── modelo_simulado.py  modelo falso para pruebas
└── tests/test_motor.py     pruebas que corren sin API key
```

## Cómo correrlo desde un clon limpio

Necesitás [uv](https://docs.astral.sh/uv/) instalado y **al menos una** clave de la tabla de arriba.

```bash
git clone https://github.com/<usuario>/fde-tiendasur.git
cd fde-tiendasur
uv sync                       # crea .venv e instala todo desde uv.lock
cp .env.example .env          # en Windows: copy .env.example .env
# Abrí .env y completá solo las claves que tengas, por ejemplo: GROQ_API_KEY=gsk_...
```

| Para | Comando |
|---|---|
| Ver una ejecución exitosa y una con error | `uv run python src/motor.py` |
| Lo mismo con otro proveedor | `uv run python src/motor.py --proveedor google` |
| Medir las 5 consultas (genera `resultados/medicion_<proveedor>.md`) | `uv run python src/medir.py` |
| Comparar todos los proveedores con clave (genera `resultados/comparacion.md`) | `uv run python src/medir.py --todos` |
| Ver el reintento y el error estructurado sin gastar | `uv run python src/demo_reintento.py` |
| Correr las pruebas sin API key | `uv run pytest` |

Para cambiar el proveedor por defecto, editá `proveedor = "groq"` en `config.toml`, o agregá
`PROVEEDOR=google` en tu `.env`.

¿Sin uv? `python -m venv .venv`, activalo e instalá con `pip install -r requirements.txt`.
Después corré los mismos scripts con `python` en lugar de `uv run python`.

## Sobre los planes gratuitos

- **No mandes datos personales reales.** En el plan gratuito de Google, tus prompts pueden
  usarse para mejorar sus productos.
- **Tienen límites por minuto y por día.** Si los superás, el motor devuelve `API_LIMITE`:
  esperá un minuto y volvé a correr.
- **El costo igual se calcula.** El motor usa la tarifa del plan pago de ese modelo, así tu tabla
  muestra cuánto costaría en producción. Eso es lo que tenés que comparar con tu KPI.

## Cómo funciona el motor

1. **Valida la entrada** con `Entrada`. Si falla, devuelve `VALIDACION_ENTRADA` sin gastar tokens.
2. **Revisa el proveedor y su clave**. Si falta, devuelve `CONFIGURACION` con el nombre de la variable.
3. **Arma el prompt** desde `prompts/sistema_v1.txt` e inyecta el esquema JSON de `Salida`.
4. **Llama al modelo** con `llamar_modelo()` de `proveedores.py`, pidiendo JSON, y **valida** con `Salida`.
5. Si la salida es inválida, **registra qué campo falló**, le muestra los errores al modelo y
   **reintenta una vez**. Si vuelve a fallar, devuelve `VALIDACION_SALIDA` con la lista de errores.
6. Traduce los **errores de la API** de cualquier proveedor a cuatro etapas: clave inválida
   (`CONFIGURACION`), límite o crédito agotado (`API_LIMITE`), sin conexión o timeout
   (`API_CONEXION`) y cualquier otro (`API_ERROR`).
7. Toda respuesta, exitosa o no, trae `tokens_entrada`, `tokens_salida`, `costo_usd`,
   `latencia_ms`, `proveedor`, `modelo` y `plan`.

## Qué cambia entre proveedores (`src/proveedores.py`)

| | OpenAI | Groq | Anthropic | Google |
|---|---|---|---|---|
| Llamada | `chat.completions.create` | igual que OpenAI | `messages.create` | `models.generate_content` |
| Prompt de sistema | primer mensaje `system` | igual que OpenAI | parámetro `system=` | `system_instruction` |
| Pedir JSON | `response_format` | igual que OpenAI | lo pide el prompt; `extraer_json()` limpia | `response_mime_type` |
| Rol del asistente | `assistant` | `assistant` | `assistant` | `model` |
| Tokens | `prompt_tokens` / `completion_tokens` | igual que OpenAI | `input_tokens` / `output_tokens` | `prompt_token_count` / `candidates_token_count` + `thoughts_token_count` |

El resto del motor no cambia: por eso podés comparar proveedores con la misma medición.

## Decisiones y trade-offs (ejemplo para la media página del PDF)

- **Modelo:** comparamos los cuatro proveedores con `medir.py --todos`. Para clasificar y redactar
  2 o 3 oraciones alcanza con un modelo chico; elegimos el que cumple la meta de latencia con el menor
  costo estimado. Si la precisión no alcanza, probamos un modelo más grande.
- **Prompt de sistema:** define el rol, 6 reglas numeradas (entre ellas no inventar datos
  ni prometer reintegros) y exige responder solo con el JSON del esquema.
- **Cuando la salida no valida:** el sistema registra el campo que falló, reintenta una vez
  con los errores a la vista del modelo y, si vuelve a fallar, devuelve un error estructurado.
  La consulta queda para que la atienda una persona.
