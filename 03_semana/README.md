# Semana 3 — RAG sobre datos reales (con permisos)

> Una idea guía todo el módulo: **un LLM es tan bueno como el contexto que recibe.** Si conectas un modelo a los documentos sin diseñar cómo se recuperan, el modelo trabaja a ciegas.

---

## 1. Objetivos

Al terminar el módulo vas a poder:

1. **Fragmentar** (chunking) documentos sin separar las reglas de sus excepciones.
2. **Ingestar** documentos en ChromaDB con metadatos de origen y de permisos (ACL).
3. **Buscar de forma híbrida**: semántica (embeddings) + léxica (BM25), fusionadas con RRF.
4. **Proteger datos** filtrando por rol *antes* de buscar (pre-filtering).
5. **Medir** la recuperación con métricas Top-k sobre un set de preguntas de prueba.

---

## 2. El flujo en 3 etapas

```
[Documentos] -> INGESTA -> [ChromaDB + metadatos/ACL]
                                   |
[Consulta + rol] -> RECUPERACIÓN (filtro por rol -> vectorial || BM25 -> RRF)
                                   |
                   GENERACIÓN (motor Pydantic de la PE2 -> respuesta + fuentes | requiere_humano)
                                   |
                   Semana 4: el agente usa este buscador como herramienta
```

| Etapa | Qué hace | Riesgo si se hace mal |
|---|---|---|
| Ingesta | Limpia, fragmenta con solapamiento y guarda embeddings + metadatos | No se pueden auditar citas ni actualizar vectores |
| Recuperación | Filtra por rol, busca en paralelo (vectorial + BM25) y fusiona con RRF | Fugas de datos o resultados irrelevantes |
| Generación | Responde solo con la evidencia recuperada y cita las fuentes | Alucinación de políticas que no existen |

---

## 3. Conceptos clave

### 3.1 Chunking estratégico
- **Qué es:** dividir documentos en fragmentos respetando su estructura lógica.
- **Por qué importa:** un corte arbitrario puede separar una regla de su excepción (ej.: un protocolo sin sus contraindicaciones).
- **Punto de partida:** Recursive Character Chunking con **10% de solapamiento**. Pasar a Semantic Chunking solo si los documentos tienen estructura irregular y la latencia lo permite.
- **Tamaño:** muy grande = un vector mezcla muchos temas (ruido). Muy chico = frases sin contexto.

### 3.2 Embeddings
- **Qué es:** vectores donde la cercanía refleja similitud de significado.
- **Por qué importa:** encuentran respuestas aunque el usuario use sinónimos.
- **Cómo elegir modelo:** dimensiones (`text-embedding-3-small` = 1536, `3-large` = 3072), soporte multilingüe (`multilingual-e5`, Cohere) y entrenamiento para retrieval (bi-encoders).

### 3.3 Búsqueda híbrida + RRF
- **Qué es:** combinar búsqueda vectorial (concepto) con BM25 (palabra exacta).
- **Por qué importa:** los embeddings confunden identificadores parecidos: `ERR_9921_X` vs `ERR_9912_X`. BM25 los distingue.
- **RRF:** fusiona rankings sin normalizar puntajes:

  `Score_RRF(d) = Σ 1 / (k + rank(d))`, con `k = 60`.

### 3.4 Metadatos y ACL con pre-filtering
- **Qué es:** cada fragmento lleva `documento`, `seccion`, `hash` y roles autorizados, usados como un `WHERE` antes de buscar.
- **Por qué importa:** filtrar *después* de recuperar puede filtrar datos al prompt y, además, dejar al usuario sin resultados si los top-k eran de áreas restringidas.

### 3.5 Grounding y escalamiento
- **Qué es:** el modelo responde solo con los fragmentos recuperados y cita la fuente. Si no hay evidencia, devuelve `requiere_humano = true`.
- **Por qué importa:** evita que el LLM complete huecos con su memoria e invente procedimientos.

---

## 4. Demo: Mini-RAG híbrido con permisos

```bash
pip install chromadb rank_bm25
```

```python
import re
import chromadb
from rank_bm25 import BM25Okapi

ROLES = ["soporte", "rrhh", "admin"]

DOCUMENTOS = [
    {"id": "manual_router", "seccion": "Soporte tecnico", "roles": ["soporte", "admin"],
     "texto": "Si el router muestra el error ERR_9921_X, reinicia el equipo y actualiza "
              "el firmware a la version 4.2. Si el error persiste, escala el caso a nivel 2."},
    {"id": "manual_errores", "seccion": "Soporte tecnico", "roles": ["soporte", "admin"],
     "texto": "El error ERR_9912_X indica una falla de autenticacion PPPoE: verifica usuario "
              "y contrasena del cliente. El error ERR_9921_Y aparece cuando el cable de fibra "
              "esta mal conectado."},
    {"id": "politica_vacaciones", "seccion": "Recursos Humanos", "roles": ["soporte", "rrhh", "admin"],
     "texto": "Cada empleado tiene 14 dias de vacaciones por ano. La solicitud se carga "
              "en el portal con 30 dias de anticipacion."},
    {"id": "presupuesto_2025", "seccion": "Finanzas", "roles": ["admin"],
     "texto": "El presupuesto 2025 asigna 1,2 millones al proyecto Alpha-X y congela "
              "las contrataciones del area de soporte."},
]


# --- Ingesta ---------------------------------------------------------------
def fragmentar(texto: str, tamano: int = 25, solapamiento: int = 5) -> list[str]:
    palabras = texto.split()
    paso = tamano - solapamiento
    return [" ".join(palabras[i:i + tamano])
            for i in range(0, max(len(palabras) - solapamiento, 1), paso)]


def ingestar(documentos: list[dict], tamano: int = 25, solapamiento: int = 5):
    coleccion = chromadb.Client().get_or_create_collection("mini_rag")
    ids, textos, metadatos = [], [], []
    for doc in documentos:
        for i, frag in enumerate(fragmentar(doc["texto"], tamano, solapamiento)):
            ids.append(f"{doc['id']}#{i}")
            textos.append(frag)
            meta = {"documento": doc["id"], "seccion": doc["seccion"]}
            for rol in ROLES:                       # un booleano por rol -> filtrable en Chroma
                meta[f"rol_{rol}"] = rol in doc["roles"]
            metadatos.append(meta)
    coleccion.add(ids=ids, documents=textos, metadatas=metadatos)
    return coleccion


# --- Recuperación (siempre filtrada por rol ANTES de buscar) ---------------
def tokenizar(texto: str) -> list[str]:
    return re.findall(r"\w+", texto.lower())


def buscar_vectorial(coleccion, consulta, rol, k=3):
    r = coleccion.query(query_texts=[consulta], n_results=k, where={f"rol_{rol}": True})
    return r["ids"][0]


def buscar_lexica(coleccion, consulta, rol, k=3):
    permitidos = coleccion.get(where={f"rol_{rol}": True})
    if not permitidos["ids"]:
        return []
    bm25 = BM25Okapi([tokenizar(t) for t in permitidos["documents"]])
    puntajes = bm25.get_scores(tokenizar(consulta))
    orden = sorted(range(len(puntajes)), key=lambda i: puntajes[i], reverse=True)
    return [permitidos["ids"][i] for i in orden[:k]]


def rrf(*rankings, k=60):
    puntajes = {}
    for ranking in rankings:
        for pos, frag_id in enumerate(ranking, start=1):
            puntajes[frag_id] = puntajes.get(frag_id, 0.0) + 1.0 / (k + pos)
    return sorted(puntajes, key=puntajes.get, reverse=True)


def buscar_hibrida(coleccion, consulta, rol, k=3):
    return rrf(buscar_vectorial(coleccion, consulta, rol, k),
               buscar_lexica(coleccion, consulta, rol, k))[:k]


# --- Verificación ----------------------------------------------------------
if __name__ == "__main__":
    col = ingestar(DOCUMENTOS)

    q = "Que hago con el error ERR_9921_X?"
    print("Vectorial:", buscar_vectorial(col, q, "soporte"))
    print("Lexica:   ", buscar_lexica(col, q, "soporte"))
    print("Hibrida:  ", buscar_hibrida(col, q, "soporte"))   # esperado: manual_router#0 primero

    q = "presupuesto del proyecto Alpha-X"
    print("Admin:    ", buscar_hibrida(col, q, "admin"))
    for rol in ["soporte", "rrhh"]:
        assert not any(f.startswith("presupuesto_2025") for f in buscar_hibrida(col, q, rol))
    print("OK: aislamiento de permisos verificado.")
```

**Qué demuestra:**
- **Códigos casi idénticos:** los embeddings pueden mezclar los tres errores; BM25 encuentra `ERR_9921_X` exacto y RRF lo sube al primer puesto.
- **Datos confidenciales:** `where={"rol_soporte": True}` excluye `presupuesto_2025` antes de calcular cualquier puntaje, así que nunca llega ni a resultados ni al prompt.

    ---

## 5. Puntos de verificación

| Pregunta | Respuesta esperada |
|---|---|
| Cláusulas de 400 palabras con excepciones al pie, cortadas cada 150 sin solapamiento: ¿qué pasa? | La excepción queda en otro chunk y puede no recuperarse junto con la regla. |
| ¿Por qué no alcanza con decir en el system prompt "no muestres finanzas a soporte"? | Si el fragmento entra al contexto, puede filtrarse (prompt injection o error). La seguridad va en la capa de recuperación. |
| El RAG recupera los 3 fragmentos correctos pero el LLM dice "no tengo información". ¿Dónde falla? | En la generación o en un prompt demasiado restrictivo, no en el retrieval. |

---

## 6. Errores frecuentes

| Error | Consecuencia |
|---|---|
| Chunks muy grandes | Ruido semántico, peor precisión |
| Chunks muy chicos | Frases sin contexto para razonar |
| Post-filtering de permisos | Riesgo de fuga y cero resultados para usuarios autorizados |
| No guardar `documento`/`seccion`/`hash` | Sin auditoría de citas ni invalidación de vectores |
| Confiar solo en embeddings | Fallan con SKU, códigos, fechas y versiones exactas |
| Cambiar chunking sin re-ingestar | Fragmentos duplicados que falsean el Top-k |
| No prohibir el conocimiento general en el prompt | El LLM inventa cuando no hay evidencia |

---

## 7. Pre-Entrega 3: "Mi RAG con permisos"

**Objetivo:** pipeline RAG sobre los documentos de la PE1, conectado al motor Pydantic de la PE2.

### Contrato de funciones
| Función | Debe |
|---|---|
| `ingestar()` | Leer la carpeta (ej. `docs_cliente/`), limpiar, fragmentar y guardar en ChromaDB con `documento`, `seccion` y roles. Un solo comando. |
| `buscar(consulta, usuario, k)` | Mapear usuario→rol, buscar híbrido con `where` en ambas búsquedas, fusionar con RRF y devolver `documento`, `fragmento_id`, `texto`, `puntaje`. |
| `responder(entrada)` | Recibir la `Entrada` de la PE2, recuperar según rol, generar la `Salida` solo con evidencia + `fuentes`, o `requiere_humano = true`. |

### Pruebas
- **Golden set de 10 preguntas** con documento esperado: 6 normales, 2 sin respuesta, 2 sobre documentos restringidos.
- **Top-k con 2 configuraciones de chunking** (ej. chicos vs. medianos con 10% de overlap), re-creando la colección en cada corrida.
- **Tests de permisos:** al menos uno por rol, y uno que pruebe que un usuario sin permiso no recibe el documento restringido **ni en `buscar()` ni en el prompt del LLM**.

### PDF `FDE_PE3_Apellido_Nombre.pdf` (2-3 páginas)
1. Salida real de la ingesta + ejemplo de metadatos de un fragmento.
2. Resultado de los tests de permisos.
3. 2 consultas donde la híbrida acierta y la vectorial falla.
4. Una respuesta con fuentes y un caso con `requiere_humano = true`.
5. Las 10 preguntas + tabla Top-k comparando las 2 configuraciones.
6. Decisiones y trade-offs (media página): tamaño de chunk elegido y cuándo migrar de ChromaDB a Pinecone.

### Rúbrica
| Criterio | Peso |
|---|---|
| Permisos antes de buscar + tests por rol | 25% |
| Búsqueda híbrida con evidencia | 20% |
| Ingesta y metadatos | 15% |
| Respuesta con fuentes / `requiere_humano` | 15% |
| Golden set y medición Top-k | 15% |
| Decisiones y trade-offs | 10% |

---

## 8. Mirada de Forward Deployed Engineer: por qué esto importa

Un FDE no entrega demos, entrega sistemas que funcionan **dentro del cliente**, con sus datos sucios, sus permisos y sus auditorías. Desde ese rol, esta semana es el punto donde el curso pasa de "prototipo" a "producto".

### 8.1 Conclusiones clave

1. **La seguridad es arquitectura, no prompt.** Lo primero que pregunta un cliente corporativo no es "qué tan inteligente es", sino "¿quién puede ver qué?". Si el dato restringido nunca entra al contexto, no hay prompt injection que lo saque. Por eso el pre-filtering pesa 25% de la nota: es lo que destraba (o bloquea) una puesta en producción.

2. **El vocabulario del cliente es exacto.** Códigos de error, SKU, números de contrato, nombres de clientes. Los embeddings solos fallan justo en lo que el usuario de negocio más consulta. La búsqueda híbrida no es una mejora opcional: es el mínimo para que el usuario confíe.

3. **"No sé" es una respuesta válida.** `requiere_humano = true` convierte el riesgo de alucinación en un flujo operativo (derivar a una persona). Para el cliente, un sistema que admite no saber es más valioso que uno que siempre responde.

4. **Sin medición no hay conversación con el cliente.** El golden set y el Top-k transforman "creo que anda mejor" en "pasamos de 6/10 a 9/10 con chunks de X palabras". Ese número es lo que justifica decisiones, presupuesto y el siguiente sprint.

5. **La trazabilidad es lo que permite operar a largo plazo.** `documento`, `seccion` y `hash` permiten citar, auditar y re-indexar cuando el cliente actualiza un archivo. Sin eso, el sistema se degrada en silencio.

6. **Las decisiones de infraestructura se toman por restricciones reales.** ChromaDB vs. Pinecone no es una preferencia: depende de volumen de vectores, concurrencia, SLA de latencia y si el cliente tiene equipo para operar infraestructura propia.

### 8.2 Cómo encaja en el recorrido de aprendizaje

| Semana | Pieza | Qué aporta |
|---|---|---|
| 1 | Caso del cliente y documentos | Contexto del negocio y del corpus |
| 2 | Motor estructurado (Pydantic) | Salidas validadas y predecibles |
| **3** | **RAG con permisos** | **Respuestas ancladas a datos reales y seguras** |
| 4 | Agente | Usa `buscar()` como herramienta, decide cuándo invocarla |

Cada semana es una capa que el agente final va a necesitar. Si la Semana 3 falla (fugas, respuestas inventadas, búsqueda imprecisa), el agente de la Semana 4 amplifica ese error porque actúa sobre él.

### 8.3 Lo que te llevas como herramienta reutilizable

- Un **patrón de ingesta** con metadatos de ACL aplicable a cualquier corpus.
- Una **función `buscar()` híbrida y segura** que se puede exponer como tool de un agente o servidor MCP.
- Un **método de evaluación** (golden set + Top-k) para comparar cualquier cambio futuro: chunking, modelo de embeddings o reranker.
- Un **criterio para escalar** infraestructura justificado con datos del cliente.

### 8.4 Observaciones técnicas sobre la demo (para producción)

- `chromadb.Client()` es en memoria: para la PE3 conviene `chromadb.PersistentClient(path=...)` y borrar la colección antes de re-ingestar al comparar configuraciones.
- Si un rol tiene menos fragmentos habilitados que `n_results`, Chroma devuelve menos resultados (puede emitir un aviso). Conviene contemplarlo en los tests.
- BM25 se reconstruye en cada consulta sobre el subconjunto permitido: correcto para el ejercicio, pero en corpus grandes conviene cachear un índice por rol.
- Para demostrar que el dato restringido "no llega al prompt", el test debe inspeccionar el prompt final armado, no solo la salida de `buscar()`.

---

## 9. Glosario

| Término | Definición |
|---|---|
| RAG | Inyectar contexto recuperado de fuentes privadas en el prompt antes de generar. |
| BM25 | Recuperación léxica basada en frecuencia de términos exactos y largo del documento. |
| RRF | Fusión de rankings sumando el inverso de la posición desplazada en cada lista. |
| Pre-filtering | Aplicar restricciones de metadatos (roles) dentro del motor, antes de calcular puntajes. |
| Grounding | Anclar la respuesta solo a la evidencia del contexto. |
| Golden set | Preguntas de prueba con respuesta/documento esperado para medir el sistema. |
