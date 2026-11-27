# Mini-RAG híbrido con permisos (Semana 3 / PE3)

Caso: **FibraSur Telecom** (ficticio). Asistente interno para soporte, RRHH y dirección sobre 6 documentos con ACL.

## Cómo levantar la app

Requisitos: Python >= 3.11 y [uv](https://docs.astral.sh/uv/).

### 1. Instalar dependencias

```bash
uv sync
```

### 2. Configurar secretos

Crear `.env` en la raíz del proyecto (no se versiona):

```bash
COHERE_API_KEY=...   # embeddings (ingesta y consulta)
GROQ_API_KEY=...     # generación
```

Sin `COHERE_API_KEY` no hay ingesta ni consulta (ambas necesitan embeddings). Sin `GROQ_API_KEY` la recuperación funciona y la generación deriva a humano.

### 3. Levantar la UI (Streamlit)

```bash
uv run streamlit run app.py
```

Abre en <http://localhost:8501>. Otro puerto: `uv run streamlit run app.py --server.port 8502`.

Pasos en la UI: **1. Ingesta** (cargar `docs_cliente/`), **2. Inferencia** (elegir usuario y consultar), **3. Cola humana** (aprobar o editar respuestas derivadas).

### 4. Ingesta por CLI (alternativa a la UI)

Un solo comando (contrato PE3):

```bash
uv run python -m rag.ingesta docs_cliente --tamano 600 --solapamiento 60
```

Los tres argumentos son opcionales. Por defecto toman `docs_cliente`, `chunking.tamano` y `chunking.solapamiento` de `config.toml`. Imprime los fragmentos y roles por documento, y guarda el índice en `./chroma_db`.

### 5. Evaluación y tests (CLI)

```bash
uv run python evaluar.py   # golden set x 2 chunkings x 3 modos; necesita COHERE_API_KEY
uv run pytest -q           # offline, usa un embedder falso
```

## Configuración

| Qué | Dónde | Ejemplos |
|---|---|---|
| Parámetros (no secretos) | `config.toml` | roles, usuarios, chunking, k, rutas, modelos |
| Secretos | `.env` (no se versiona) | `COHERE_API_KEY`, `GROQ_API_KEY` |

`rag/config.py` lee ambos y los valida con Pydantic. El resto del código importa `cfg` (TOML) y `secretos` (.env).
Un TOML roto o un usuario con rol inexistente falla al arrancar, no en medio de una consulta.

## Modelos

| Etapa | Modelo | Nota |
|---|---|---|
| Generación | Groq: `openai/gpt-oss-120b` (default), `openai/gpt-oss-20b`, `qwen/qwen3.6-27b` | La UI lista los modelos vivos de la cuenta con `models.list()`. `llama-3.3-70b-versatile` fue dado de baja en agosto 2026. |
| Embedding | Cohere `embed-multilingual-light-v3.0` (384 dims) | El más liviano de Cohere, multilingüe. Se usa igual en ingesta y consulta (`input_type` `search_document` / `search_query`). Los tests usan un embedder falso offline (`tests/hash_embedder.py`). |

## Estructura

```
docs_cliente/          6 documentos con frontmatter (titulo, roles, version)
config.toml            parámetros: roles, usuario->rol, modelos, chunking, rutas
pyproject.toml         dependencias (uv)
rag/config.py          carga y valida config.toml + .env
rag/embeddings.py      CohereEmbedder (documentos y consultas)
rag/ingesta.py         limpieza -> secciones markdown -> recursive chunking + overlap -> embeddings -> Chroma
rag/recuperacion.py    usuario->rol -> where -> vectorial || BM25 (índice cacheado por rol) -> RRF
rag/generacion.py      Entrada/Salida Pydantic, prompt con grounding, verificación de fugas, post-validación de fuentes
rag/hitl.py            cola de casos (requiere_humano) y log de aprobaciones (JSONL)
app.py                 UI: 1. Ingesta  2. Inferencia  3. Cola humana
evaluar.py             golden set x 2 chunkings x 3 modos -> tabla Top-k
tests/test_permisos.py tests por rol, prompt sin datos restringidos, grounding
```

## ACL de ejemplo

| Documento | soporte | rrhh | admin |
|---|---|---|---|
| manual_router_fs3000 | x | | x |
| protocolo_escalamiento_soporte | x | | x |
| politica_vacaciones | x | x | x |
| politica_teletrabajo | x | x | x |
| bandas_salariales_2025 | | x | x |
| presupuesto_2025 | | | x |

Documento sin `roles` en el frontmatter: solo lo ve `admin` (deny by default).

## Controles de seguridad (en capas)

1. **Pre-filter**: `where={"rol_<rol>": True}` en la búsqueda vectorial y en el corpus del BM25.
2. **Verificación del prompt**: `verificar_aislamiento()` revisa el prompt armado y corta si aparece un fragmento prohibido.
3. **Grounding**: las fuentes que devuelve el LLM se validan contra lo recuperado; sin fuentes válidas se fuerza `requiere_humano`.
4. **HITL**: lo derivado va a la cola; lo respondido pasa por aprobación/edición de un operador y queda auditado.

## Pruebas

```bash
uv run pytest -q
uv run python evaluar.py        # usa Cohere: necesita COHERE_API_KEY
```

Consultas para mostrar en el PDF:
- `ERR_9921_X` vs `ERR_9912_X` / `ERR_9921_Y`: comparar columnas vectorial y BM25 en el paso 2.
- "cliente SLA Oro con ERR_9921_X a las 11": la respuesta tiene que incluir la excepción. Con chunks de 250 sin solapamiento la excepción queda en otro fragmento.
- "80 clientes del nodo sin servicio": la excepción de corte masivo cambia la acción (NOC, no Nivel 2).
- `ana.soporte` pregunta por Alpha-X: no hay evidencia permitida -> `requiere_humano`.
- "horario del comedor": sin respuesta en la base -> `requiere_humano`.
