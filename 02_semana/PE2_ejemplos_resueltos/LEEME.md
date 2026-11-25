# Preentrega 2 · Dos ejemplos resueltos

Cada carpeta es un repositorio completo que cumple la estructura que pide la PE2:

| Ejemplo | Caso | Qué devuelve | Proveedor por defecto |
|---|---|---|---|
| `fde-tiendasur` | Atención al cliente de una tienda online (el ejemplo de la consigna) | categoría, respuesta sugerida, si requiere humano y confianza | Groq |
| `fde-mesa-ayuda` | Mesa de ayuda de IT interna | tipo, prioridad, resumen, pasos sugeridos, si escala a N2 y confianza | Google |

Los dos tienen la misma arquitectura y funcionan con **cuatro proveedores**: si entendés uno,
entendés el otro.

| Proveedor | Modelo | Plan | Variable en `.env` |
|---|---|---|---|
| Groq | `openai/gpt-oss-20b` | gratis, con límites | `GROQ_API_KEY` |
| Google | `gemini-3.1-flash-lite` | gratis, con límites | `GEMINI_API_KEY` |
| OpenAI | `gpt-6-luna` | pago (prepago desde 5 USD) | `OPENAI_API_KEY` |
| Anthropic | `claude-haiku-5-5` | pago (prepago desde 5 USD) | `ANTHROPIC_API_KEY` |

Alcanza con una clave para empezar. Con Groq o Google podés hacer la PE2 sin pagar.
Elegís el proveedor en `config.toml` o al correr: `uv run python src/motor.py --proveedor groq`.

## Cómo usarlos para tu PE2

1. **Copiá la estructura** de uno de los dos a tu repositorio `fde-<tu-caso>`.
2. **Reescribí `src/contratos.py`** con los campos de **tu** historia de usuario de la PE1:
   qué entra (`Entrada`) y qué tiene que salir (`Salida`), con al menos 3 reglas de validación.
3. **Adaptá `prompts/sistema_v1.txt`**: rol, reglas de tu negocio y el marcador `{esquema_json}`.
4. **Completá `config.toml`**: el proveedor que vas a usar, sus precios publicados y las metas de tu KPI.
   `src/proveedores.py` no se toca.
5. **Cambiá las 5 consultas de `src/medir.py`** por consultas reales de tu caso:
   dos típicas, un caso límite, una confusa y una fuera de tema.
6. Corré `uv run pytest`, `uv run python src/motor.py` y `uv run python src/medir.py`.
   Si tenés más de una clave, `uv run python src/medir.py --todos` compara proveedores.
7. Exportá `requirements.txt`, hacé commit, `git tag pe2` y `git push origin pe2`.

## Qué copiar al PDF (FDE_PE2_Apellido_Nombre.pdf, 2 páginas)

| Sección del PDF | De dónde sale |
|---|---|
| Contrato de datos | `src/contratos.py` (o la tabla del README) |
| Ejecución exitosa | la salida de `uv run python src/motor.py`, ejecución 1 |
| Ejecución con error | la ejecución 2 de `motor.py` y la salida de `uv run python src/demo_reintento.py` |
| Tabla de medición con promedios | `resultados/medicion_<proveedor>.md`, que genera `src/medir.py` |
| Decisiones y trade-offs | modelo y proveedor elegidos (mejor si los comparaste con `--todos`), prompt y qué pasa cuando falla la validación |
| Estructura del repositorio | una captura del repo en GitHub con la etiqueta `pe2` |

## Cuidados con los planes gratuitos

- No mandes datos personales reales: en el plan gratuito de Google, los prompts pueden usarse
  para mejorar sus productos.
- Tienen límites por minuto y por día. Si aparece `API_LIMITE`, esperá un minuto.
- El costo se calcula con la tarifa del plan pago: es lo que costaría en producción.

Los modelos y precios de `config.toml` son los publicados en noviembre de 2026.
Verificalos en la página de precios de cada proveedor antes de medir.
