# Semana 4 — Agentes y MCP

> Idea central: **ni determinismo rígido ni autonomía sin frenos.** El objetivo es una arquitectura donde el LLM decide, pero el grafo controla el flujo, limita los pasos y frena antes de escribir.

---

## 1. Objetivos

Al terminar el módulo vas a poder:

1. **Orquestar** un agente con estado en LangGraph (nodos, aristas, estado compartido y límite de pasos).
2. **Persistir** conversaciones con Checkpointers y `thread_id` para reanudar, auditar y tolerar fallos.
3. **Frenar acciones críticas** con Human-in-the-Loop (`interrupt` + `Command(resume=...)`).
4. **Construir y consumir un servidor MCP** con herramientas tipadas, separando la decisión del agente de los conectores al sistema del cliente.
5. **Integrar el RAG de la Semana 3** como una herramienta más del ciclo de razonamiento.

---

## 2. Arquitectura: mente, manos y freno

```
START -> decidir -> [ buscar | ejecutar | pedir_aprobacion | responder | limite ] -> ...
            ^                     |
            +---------------------+   (bucle acotado por MAX_PASOS)
```

| Pieza | Rol | Tecnología |
|---|---|---|
| **Mente** | Decide el próximo paso, mantiene el estado y corta al llegar a `MAX_PASOS` | LangGraph |
| **Sentidos y manos** | Buscan documentos (RAG con permisos) y leen/escriben en el sistema del cliente | `buscar_documentos` + servidor MCP |
| **Freno** | Persiste el estado, pausa antes de escribir y espera aprobación humana | Checkpointer + `interrupt` |

> En la Semana 5 el sistema simulado detrás del MCP se reemplaza por una API legacy con OAuth2 **sin cambiar el contrato del servidor**.

---

## 3. Conceptos clave

### 3.1 Grafo de estados (LangGraph)
- **Nodos:** funciones o llamadas al modelo.
- **Aristas (edges):** transiciones fijas o condicionales.
- **Estado compartido:** memoria tipada que recorre todo el flujo.
- **Por qué importa:** modela procesos reales con ciclos acotados, y permite validar con Pydantic cada bifurcación para que una salida inesperada del LLM no rompa el runtime.

```python
from typing import TypedDict
from langgraph.graph import END, START, StateGraph

class EstadoAgente(TypedDict):
    consulta: str
    pasos: int
    respuesta: str

def nodo_decidir(state: EstadoAgente) -> dict:
    return {"pasos": state["pasos"] + 1, "respuesta": "Consulta procesada"}

builder = StateGraph(EstadoAgente)
builder.add_node("decidir", nodo_decidir)
builder.add_edge(START, "decidir")
builder.add_edge("decidir", END)
grafo = builder.compile()
```

### 3.2 Persistencia, Checkpointers y Time Travel
- **Qué es:** LangGraph guarda una instantánea del estado después de cada nodo, indexada por `thread_id`.
- **Por qué importa:** la sesión sobrevive a fallas de red, reinicios o esperas de aprobación, y permite revisar el estado paso a paso para entender por qué el agente eligió una herramienta.

```python
from langgraph.checkpoint.memory import MemorySaver

app = builder.compile(checkpointer=MemorySaver())
config = {"configurable": {"thread_id": "cliente-42"}}
app.invoke({"consulta": "Estado pedido", "pasos": 0, "respuesta": ""}, config)
```

### 3.3 Human-in-the-Loop
- **Qué es:** `interrupt()` suspende el nodo, expone la acción propuesta y espera `Command(resume=...)`.
- **Por qué importa:** el agente puede **leer** libremente, pero nunca **escribir** (reembolsos, registros financieros, bases de datos) sin una autorización trazable.

```python
from langgraph.types import Command, interrupt

def nodo_pedir_aprobacion(state: dict) -> dict:
    decision = interrupt({"accion": "crear_devolucion", "pedido": "A-1043"})
    if decision == "aprobar":
        return {"respuesta": "Devolución ejecutada tras aprobación humana."}
    return {"respuesta": "Operación cancelada por falta de aprobación."}
```

### 3.4 Model Context Protocol (MCP)
- **Qué es:** estándar cliente-servidor para que una app de IA descubra y ejecute herramientas, recursos y prompts de sistemas externos.
- **Transportes:** `stdio` (procesos locales) o `SSE` (HTTP remoto).
- **Por qué importa:** evita integraciones ad-hoc frágiles, **mantiene las credenciales dentro del servidor** (el LLM nunca las ve) y expone esquemas JSON tipados.

| Paso | Mensaje | Qué pasa |
|---|---|---|
| 1 | `initialize` | Handshake de capacidades |
| 2 | `tools/list` | El servidor devuelve los esquemas tipados de sus herramientas |
| 3 | `tools/call` | El cliente invoca una herramienta con argumentos validados |

---

## 4. Demo: grafo con aprobación humana y límite de pasos

```bash
pip install langgraph
```

```python
from typing import TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

MAX_PASOS = 4


class EstadoAgente(TypedDict):
    consulta: str
    pasos: int
    info: str
    accion: dict | None
    respuesta: str
    historial: list[str]


# --- Decisión (en la PE4 la toma el LLM con salida validada) ----------------
def nodo_decidir(state: EstadoAgente) -> dict:
    paso = state["pasos"] + 1
    base = {"pasos": paso, "historial": state["historial"] + [f"decidir (paso {paso})"]}
    quiere_devolver = "devolver" in state["consulta"].lower()

    if paso >= MAX_PASOS:
        return {**base, "respuesta": f"No pude resolverlo en {MAX_PASOS} pasos. Lo derivo a una persona."}
    if quiere_devolver and not state["info"]:
        return {**base, "accion": {"tipo": "buscar"}}
    if quiere_devolver and state["info"] and state["accion"] is None:
        return {**base, "accion": {"tipo": "crear_devolucion", "parametros": {"pedido": "A-1043"}}}
    if state["accion"] and state["accion"].get("completada"):
        return {**base, "respuesta": f"Listo, cree la devolucion. {state['info']}"}
    return {**base, "accion": {"tipo": "buscar"}}


# --- Herramientas ------------------------------------------------------------
def nodo_buscar(state: EstadoAgente) -> dict:
    # En la PE4 aqui se invoca buscar_documentos() del RAG de la PE3
    info = "Las devoluciones se aceptan dentro de los 30 dias de la compra." \
        if "devolver" in state["consulta"].lower() else ""
    return {
        "info": info,
        "accion": None,  # CORRECCION: limpiar la accion consumida (ver seccion 8.4)
        "historial": state["historial"] + ["buscar"],
    }


def nodo_ejecutar(state: EstadoAgente) -> dict:
    # Pausa OBLIGATORIA antes de escribir
    decision = interrupt({"accion": state["accion"]["tipo"], "parametros": state["accion"]["parametros"]})
    if decision == "aprobar":
        return {"accion": {**state["accion"], "completada": True},
                "historial": state["historial"] + ["devolucion creada"]}
    return {"respuesta": f"No cree la devolucion porque no fue aprobada. {state['info']}",
            "historial": state["historial"] + ["devolucion rechazada"]}


def nodo_responder(state: EstadoAgente) -> dict:
    return {"historial": state["historial"] + ["responder"]}


# --- Enrutamiento y compilación ---------------------------------------------
def enrutar(state: EstadoAgente) -> str:
    if state.get("respuesta"):
        return "responder"
    accion = state.get("accion") or {}
    if accion.get("tipo") == "crear_devolucion" and not accion.get("completada"):
        return "ejecutar"
    return "buscar"


builder = StateGraph(EstadoAgente)
builder.add_node("decidir", nodo_decidir)
builder.add_node("buscar", nodo_buscar)
builder.add_node("ejecutar", nodo_ejecutar)
builder.add_node("responder", nodo_responder)

builder.add_edge(START, "decidir")
builder.add_conditional_edges("decidir", enrutar,
                              {"buscar": "buscar", "ejecutar": "ejecutar", "responder": "responder"})
builder.add_edge("buscar", "decidir")
builder.add_edge("ejecutar", "decidir")
builder.add_edge("responder", END)

app = builder.compile(checkpointer=MemorySaver())
print(app.get_graph().draw_mermaid())


# --- Verificación de los 3 caminos ------------------------------------------
def nueva_sesion(consulta: str) -> EstadoAgente:
    return {"consulta": consulta, "pasos": 0, "info": "", "accion": None, "respuesta": "", "historial": []}


if __name__ == "__main__":
    # 1. Aprobado
    cfg = {"configurable": {"thread_id": "cliente-42"}}
    pausa = app.invoke(nueva_sesion("Quiero devolver el pedido A-1043"), cfg)
    print("Pausa:", pausa["__interrupt__"][0].value)
    ok = app.invoke(Command(resume="aprobar"), cfg)
    print("Aprobado:", ok["respuesta"], ok["historial"])

    # 2. Rechazado
    cfg = {"configurable": {"thread_id": "cliente-43"}}
    app.invoke(nueva_sesion("Quiero devolver el pedido A-1043"), cfg)
    print("Rechazado:", app.invoke(Command(resume="rechazar"), cfg)["respuesta"])

    # 3. Límite de pasos
    cfg = {"configurable": {"thread_id": "cliente-44"}}
    print("Limite:", app.invoke(nueva_sesion("Hacen envios a Marte?"), cfg)["respuesta"])
```

**Qué demuestra:**
- **Aprobado (`cliente-42`):** `MemorySaver` guarda el estado al dispararse `interrupt()`. Al reanudar con el mismo `thread_id`, retoma desde ese punto sin repetir la búsqueda.
- **Rechazado (`cliente-43`):** no se modifica nada y se informa al usuario.
- **Límite (`cliente-44`):** sin información, `decidir` reintenta hasta `MAX_PASOS` y deriva con un mensaje claro.

---

## 5. Puntos de verificación

| Pregunta | Respuesta esperada |
|---|---|
| ¿Un servidor MCP más potente puede decidir cuándo terminar el bucle? | No. MCP expone herramientas; el control de flujo, los ciclos y el estado viven en el agente. |
| ¿Dónde van las credenciales de la base del cliente? | Dentro del servidor MCP o su entorno seguro. El LLM y el prompt nunca las ven. |
| ¿Qué pasa si reanudas con `Command(resume=...)` y otro `thread_id`? | El checkpointer no encuentra la sesión suspendida: el grafo no retoma la pausa original. |

---

## 6. Errores frecuentes

| Error | Consecuencia |
|---|---|
| Confundir MCP con la lógica del agente | MCP es transporte y exposición; la planificación vive en LangGraph |
| Servidor MCP monolítico con decenas de tools | El modelo elige mal y alucina parámetros. Mejor servidores por dominio |
| Guardar documentos enteros en el `State` | Contexto inflado en cada paso. Guardar referencias o fragmentos acotados |
| Sin límite de pasos | Bucles infinitos, costo y latencia descontrolados |
| Bifurcaciones sin validar | Si el LLM devuelve un camino inexistente, error en runtime. Validar con Pydantic |
| Escribir antes de `interrupt` | La aprobación humana no tiene efecto real |
| Mostrar solo el camino aprobado | Queda incompleto el criterio de mayor peso (30%) |
| Tools sin tipos o con descripciones ambiguas | Argumentos inválidos o confusión entre lectura y escritura |
| `MAX_PASOS` arbitrario | Debe justificarse según las herramientas y el recorrido esperado |

---

## 7. Pre-Entrega 4: "Mi agente supervisado"

**Objetivo:** agente en LangGraph conectado al RAG de la PE3 y a un servidor MCP propio sobre un sistema simulado del cliente. Decide entre buscar documentos, leer datos o proponer cambios, y **siempre** se detiene antes de escribir.

### Requisitos
| Bloque | Debe incluir |
|---|---|
| **Grafo** | Estado con `mensajes`, `usuario`, `pasos`, `pendiente_aprobacion`. Nodos `decidir`, `ejecutar herramienta`, `pedir aprobación`, `responder`. `MAX_PASOS` configurable con mensaje de derivación. Diagrama Mermaid. |
| **Persistencia + HITL** | `MemorySaver` para pausar y reanudar con el mismo `thread_id`. `interrupt` antes de toda escritura, mostrando acción y parámetros. Ramas aprobada y rechazada. |
| **Servidor MCP** | Al menos 2 tools tipadas (1 lectura, 1 escritura) con descripciones claras. Datos en SQLite o archivo estructurado. Script cliente que haga `tools/list` y `tools/call`. |
| **Pruebas** | 5 conversaciones con traza: 2 de consulta, 1 aprobada, 1 rechazada, 1 por límite de pasos. |
| **Bitácora** | 3 prompts usados con el asistente de código para el servidor MCP + 1 error del asistente detectado y corregido. |

### PDF `FDE_PE4_Apellido_Nombre.pdf` (2-3 páginas)
1. Diagrama Mermaid del grafo.
2. Traza de las 5 conversaciones.
3. Salida real del script cliente MCP (`tools/list` + `tools/call`).
4. Evidencia de una conversación pausada y retomada con el mismo `thread_id`.
5. Bitácora del asistente (3 prompts + 1 error corregido).
6. Decisiones y trade-offs (media página): por qué un agente y no un flujo fijo, qué acciones requieren aprobación y cómo se definió `MAX_PASOS`.

### Rúbrica
| Criterio | Peso |
|---|---|
| Aprobación humana (ambos caminos) | 30% |
| Grafo y bucle con límite | 20% |
| Servidor MCP probado | 20% |
| Estado persistente (`thread_id`) | 15% |
| Conversaciones, bitácora y decisiones | 15% |

### Orden sugerido
1. Base simulada (SQLite/JSON) con pedidos, tickets o turnos del caso.
2. Servidor MCP con type hints y docstrings, probado **aislado** con el script cliente.
3. Exponer `buscar_documentos` (PE3) como tool de consulta.
4. Grafo con el `State` requerido, nodos, `MAX_PASOS` y `MemorySaver()`.
5. Correr los 5 escenarios, verificar la reanudación y exportar el Mermaid.
6. Escribir el PDF y la bitácora.

---

## 8. Mirada de Forward Deployed Engineer: por qué esto importa

En las semanas anteriores construimos un sistema que **responde**. Esta semana construimos uno que **actúa**. Para un FDE ese es el salto que más riesgo y más valor tiene frente al cliente: un error de lectura es una mala respuesta; un error de escritura es un reembolso duplicado o un registro corrupto.

### 8.1 Conclusiones clave

1. **La confianza se diseña, no se promete.** Ningún cliente va a dejar que un LLM escriba en su sistema sin control. `interrupt` + aprobación trazable es lo que convierte "nos da miedo la IA" en "probémoslo en producción". Por eso pesa 30%.

2. **Separar cerebro de conectores es lo que hace el trabajo reutilizable.** El agente (LangGraph) decide; el servidor MCP encapsula accesos y credenciales. Así, cambiar la base simulada por la API real del cliente (Semana 5) no toca la lógica del agente. Ese desacople es lo que permite desplegar en varios clientes sin reescribir.

3. **Las credenciales nunca pasan por el modelo.** Que vivan dentro del servidor MCP elimina una clase entera de riesgos (prompt injection que exfiltra tokens, logs con secretos). Es un argumento de seguridad que el equipo de IT del cliente entiende de inmediato.

4. **Un agente sin límite es una factura sin techo.** `MAX_PASOS` no es un detalle técnico: es control de costo y de latencia. Justificarlo según las herramientas disponibles demuestra que entendés el proceso del cliente.

5. **La persistencia es auditoría.** El checkpointer no solo permite reanudar: deja registro de qué vio el agente y por qué eligió cada herramienta. Cuando algo sale mal, ese historial es lo que responde la pregunta del cliente: "¿por qué hizo eso?".

6. **Menos herramientas, mejor descritas.** Un servidor MCP por dominio, con pocas tools y descripciones precisas, rinde más que uno gigante. Diseñar la superficie de herramientas es diseñar qué puede (y qué no puede) hacer el agente.

7. **La bitácora del asistente de código entrena criterio.** Pedir 3 prompts y 1 error corregido no es burocracia: un FDE usa asistentes todo el tiempo y su valor está en detectar cuándo se equivocan. La sección 8.4 es un ejemplo real de eso.

### 8.2 Cómo encaja en el recorrido

| Semana | Pieza | Qué aporta | Rol en el agente |
|---|---|---|---|
| 1 | Caso del cliente | Contexto y corpus | Define qué problema resuelve |
| 2 | Motor Pydantic | Salidas validadas | Valida las decisiones de enrutamiento |
| 3 | RAG con permisos | Evidencia segura | Tool `buscar_documentos` |
| **4** | **LangGraph + MCP** | **Decisión, acción y freno** | **El agente en sí** |
| 5 | API legacy + OAuth2 | Integración real | Reemplaza el sistema simulado detrás del MCP |

Cada semana deja un componente que la siguiente usa. El agente es el primer lugar donde todos se combinan, y por eso también donde se notan los errores de las etapas anteriores.

### 8.3 Lo que te llevás como herramienta reutilizable

- Un **patrón de grafo supervisado** (decidir → herramienta → aprobación → responder) aplicable a cualquier proceso con lecturas y escrituras.
- Un **servidor MCP de plantilla** que se puede apuntar a cualquier sistema del cliente cambiando solo la implementación interna.
- Un **criterio de gobernanza**: qué acciones son libres, cuáles requieren aprobación y cuántos pasos se toleran.
- Un **método de prueba por escenarios** (consulta, aprobada, rechazada, límite) para validar cualquier agente antes de entregarlo.

### 8.4 Observaciones técnicas sobre la demo (para producción)

- **Bug en el código original de clase:** `nodo_decidir` solo propone `crear_devolucion` si `accion is None`, pero en el paso anterior quedó `accion = {"tipo": "buscar"}`. Resultado: el camino de devolución nunca llega a `interrupt`, vuelve a buscar hasta `MAX_PASOS` y `pausa["__interrupt__"]` lanza `KeyError`. Lo verifiqué ejecutándolo. **Arreglo:** en `nodo_buscar` devolver `"accion": None` (ya aplicado en la sección 4). Con eso la traza queda `decidir → buscar → decidir → [interrupt] → creada → decidir → responder`.
- **El nodo con `interrupt` se reejecuta completo al reanudar.** Cualquier código antes de `interrupt()` corre dos veces: nunca pongas escrituras ni efectos secundarios antes de la pausa.
- **Rama rechazada:** funciona porque `enrutar` revisa `respuesta` primero, pero `decidir` no la mira. En la PE4 conviene que `decidir` respete una respuesta ya fijada, para no depender del orden del enrutador.
- **`MemorySaver` es solo para desarrollo:** se pierde al reiniciar el proceso. En producción, un checkpointer persistente (SQLite o Postgres).
- **Validar la decisión del LLM:** cuando `decidir` lo maneje el modelo, la salida debe ser un modelo Pydantic con un `Literal` de caminos válidos, así un valor inesperado falla en la validación y no en el grafo.
- **El estado de la PE4 cambia:** usa `mensajes`, `usuario` y `pendiente_aprobacion`. `usuario` es clave porque lleva el rol que filtra el RAG de la PE3.

---

## 9. Glosario

| Término | Definición |
|---|---|
| StateGraph | Clase de LangGraph para construir agentes con estado compartido y transiciones condicionales. |
| Checkpointer | Persistencia que guarda el estado del grafo después de cada nodo (`MemorySaver` en desarrollo). |
| Thread ID | Identificador de sesión que aísla la memoria de cada conversación y permite reanudarla. |
| `interrupt` / `Command` | Pausa un nodo esperando una decisión externa / reanuda con esa decisión. |
| MCP Server / Client | El servidor encapsula el acceso seguro al sistema; el agente consume sus esquemas como cliente. |
| `stdio` / `SSE` | Transportes de MCP: procesos locales / HTTP remoto. |
| `MAX_PASOS` | Tope de iteraciones del bucle de razonamiento. |
