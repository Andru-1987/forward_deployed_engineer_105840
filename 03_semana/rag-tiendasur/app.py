"""UI Streamlit: Ingesta paso a paso + Inferencia (consulta -> vectorial || BM25 -> RRF -> generación -> HITL).

Ejecutar:  streamlit run app.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from rag import hitl
from rag.config import cfg, secretos
from rag.embeddings import CohereEmbedder
from rag.generacion import Entrada, llm_groq, responder
from rag.ingesta import abrir_coleccion, ingestar, leer_documento

st.set_page_config(page_title="RAG con permisos - FibraSur", layout="wide")
DOCS_EJEMPLO = Path(cfg.rutas.docs_cliente)

EJEMPLOS = [
    ("ana.soporte", "Que hago con el error ERR_9921_X?"),
    ("ana.soporte", "Un cliente Empresas SLA Oro tiene ERR_9921_X a las 11 de la mañana, lo reinicio?"),
    ("ana.soporte", "Se cayeron 80 clientes del nodo Quilmes, escalo a nivel 2?"),
    ("ana.soporte", "Cual es el presupuesto del proyecto Alpha-X?"),
    ("lucia.rrhh", "Cuanto cobra un agente de soporte nivel 2?"),
    ("carlos.admin", "Cual es el presupuesto del proyecto Alpha-X?"),
    ("martin.soporte", "Cuantos dias de vacaciones tengo con 7 años de antigüedad?"),
    ("martin.soporte", "Cual es el horario del comedor de la oficina?"),
]


# ---------------------------------------------------------------- recursos cacheados
@st.cache_resource
def get_embedder(cohere_key: str) -> CohereEmbedder:
    return CohereEmbedder(cohere_key)


def coleccion():
    try:
        return abrir_coleccion(st.session_state.ruta_chroma)
    except Exception:
        return None


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Configuración")
    st.subheader("Embeddings: Cohere")
    cohere_key = st.text_input("COHERE_API_KEY", value=secretos.cohere_api_key.get_secret_value(), type="password")
    st.caption(f"Modelo `{cfg.embedding.modelo}` ({cfg.embedding.dim} dimensiones, multilingüe). "
               "Es el mismo en la ingesta y en la consulta.")
    st.subheader("Generación: Groq")
    groq_key = st.text_input("GROQ_API_KEY", value=secretos.groq_api_key.get_secret_value(), type="password")
    modelo_llm = st.selectbox("LLM de generación", cfg.llm.modelos)
    st.divider()
    st.subheader("Chunking")
    tamano = st.slider("Tamaño de fragmento (caracteres)", 200, 1500, cfg.chunking.tamano, 50)
    solap_pct = st.slider("Solapamiento (%)", 0, 30, 100 * cfg.chunking.solapamiento // cfg.chunking.tamano)
    solapamiento = int(tamano * solap_pct / 100)
    st.caption(f"Solapamiento efectivo: {solapamiento} caracteres")
    st.divider()
    k = st.slider("Top-k para el contexto", 1, 8, cfg.recuperacion.k)
    st.session_state.ruta_chroma = st.text_input("Ruta ChromaDB", cfg.rutas.chroma)
    st.caption(f"Colección: `{cfg.coleccion}`")

st.title("RAG híbrido con permisos")
st.caption("Ingesta -> ChromaDB con ACL | Consulta -> pre-filter por rol -> Vectorial (Cohere) || BM25 -> RRF -> Groq -> Human in the loop")
tab_ing, tab_inf, tab_hitl = st.tabs(["1. Ingesta", "2. Inferencia", "3. Cola humana (HITL)"])

# ================================================================ 1. INGESTA
with tab_ing:
    c1, c2 = st.columns([2, 1])
    with c1:
        archivos = st.file_uploader("Subí documentos (.md, .txt, .pdf)", type=["md", "txt", "pdf"], accept_multiple_files=True)
    with c2:
        usar_ejemplo = st.checkbox("Incluir documentos de ejemplo (docs_cliente/)", value=not archivos)
        st.caption("Los .md traen la ACL en el frontmatter (`roles: soporte, admin`). Podés sobrescribirla abajo.")

    fuentes: list[tuple[str, bytes]] = []
    if usar_ejemplo and DOCS_EJEMPLO.exists():
        fuentes += [(p.name, p.read_bytes()) for p in sorted(DOCS_EJEMPLO.glob("*.md"))]
    fuentes += [(a.name, a.getvalue()) for a in archivos or []]

    if fuentes:
        st.markdown("**ACL por documento** (qué roles pueden recuperar cada archivo)")
        acl = {}
        cols = st.columns(3)
        for i, (nombre, contenido) in enumerate(fuentes):
            detectados = leer_documento(nombre, contenido).roles
            with cols[i % 3]:
                acl[nombre] = st.multiselect(nombre, cfg.roles, default=detectados, key=f"acl_{nombre}")

        if st.button("Ingestar en ChromaDB", type="primary", disabled=not cohere_key):
            with st.status("Ingestando...", expanded=True) as estado:
                st.write("Paso 1 - Lectura y limpieza")
                docs = [leer_documento(n, c, acl[n]) for n, c in fuentes]
                st.write(f"Paso 2-3 - Fragmentación y embeddings con Cohere `{cfg.embedding.modelo}`")
                embedder = get_embedder(cohere_key)
                st.write("Paso 4 - Carga en ChromaDB (colección recreada para evitar duplicados)")
                _, reporte = ingestar(docs, embedder, tamano, solapamiento, ruta=st.session_state.ruta_chroma)
                st.session_state.reporte = reporte
                estado.update(label=f"Ingesta completa: {reporte['coleccion']['total']} fragmentos", state="complete")

    rep = st.session_state.get("reporte")
    if rep:
        info = rep["coleccion"]
        m = st.columns(5)
        m[0].metric("Documentos", len(rep["documentos"]))
        m[1].metric("Fragmentos", info["total"])
        m[2].metric("Dimensión del vector", info["dim"])
        m[3].metric("Tiempo embedding", f"{rep['tiempos']['embedding_s']} s")
        m[4].metric("Tiempo carga Chroma", f"{rep['tiempos']['carga_chroma_s']} s")

        with st.expander("Paso 1 - Lectura y limpieza", expanded=True):
            st.dataframe(pd.DataFrame(rep["documentos"]), width="stretch", hide_index=True)

        with st.expander("Paso 2 - Fragmentación (secciones + Recursive Character Chunking con solapamiento)"):
            df_frag = pd.DataFrame([{"id": f["id"], "seccion": f["metadatos"]["seccion"], "chars": len(f["texto"]),
                                     "texto": f["texto"]} for f in rep["fragmentos"]])
            doc_f = st.selectbox("Documento", ["(todos)"] + [d["documento"] for d in rep["documentos"]])
            if doc_f != "(todos)":
                df_frag = df_frag[df_frag["id"].str.startswith(doc_f + "#")]
            st.dataframe(df_frag, width="stretch", hide_index=True)

        with st.expander("Paso 3 - Embeddings"):
            st.markdown(f"Modelo: `{info['embedding_modelo']}` | Dimensión: **{info['dim']}** | Métrica: coseno")
            V = np.array([f["vector"] for f in rep["fragmentos"]])
            prev = pd.DataFrame({"id": [f["id"] for f in rep["fragmentos"]],
                                 "norma_L2": np.round(np.linalg.norm(V, axis=1), 4),
                                 "primeros_8_valores": [np.round(v[:8], 4).tolist() for v in V]})
            st.dataframe(prev, width="stretch", hide_index=True)
            if len(V) >= 3:
                Vc = V - V.mean(axis=0)
                _, _, vt = np.linalg.svd(Vc, full_matrices=False)
                xy = Vc @ vt[:2].T
                st.caption("Proyección PCA 2D: fragmentos del mismo documento deberían agruparse.")
                st.scatter_chart(pd.DataFrame({"pc1": xy[:, 0], "pc2": xy[:, 1],
                                               "documento": [f["metadatos"]["documento"] for f in rep["fragmentos"]]}),
                                 x="pc1", y="pc2", color="documento")

        with st.expander("Paso 4 - Carga en ChromaDB con metadatos y ACL", expanded=True):
            st.markdown(f"Ruta: `{info['ruta']}` | Colección: `{info['nombre']}` | Registros: **{info['total']}**")
            matriz = pd.DataFrame([{"documento": d["documento"], **{r: r in d["roles"] for r in cfg.roles}}
                                   for d in rep["documentos"]])
            st.markdown("Matriz de acceso (documento x rol)")
            st.dataframe(matriz, width="stretch", hide_index=True)
            ejemplo = st.selectbox("Ver registro completo de un fragmento", [f["id"] for f in rep["fragmentos"]])
            f = next(x for x in rep["fragmentos"] if x["id"] == ejemplo)
            st.code(json.dumps({"id": f["id"], "document": f["texto"], "metadata": f["metadatos"],
                                "embedding": f"[{', '.join(f'{v:.4f}' for v in f['vector'][:6])}, ...] ({len(f['vector'])} dims)"},
                               ensure_ascii=False, indent=2), language="json")


# ================================================================ 2. INFERENCIA
def _paso(n: int, titulo: str):
    st.markdown(f"#### {n}. {titulo}")


def _inferencia():
    col = coleccion()
    if col is None:
        st.info("Primero ingestá documentos en la pestaña 1.")
        return
    if not cohere_key:
        st.info("Cargá la COHERE_API_KEY en la barra lateral: la consulta también se convierte en vector con Cohere.")
        return

    c1, c2 = st.columns([1, 3])
    ej = st.selectbox("Consultas de ejemplo", ["(escribir la propia)"] + [f"{u} | {q}" for u, q in EJEMPLOS])
    u_def, q_def = (ej.split(" | ", 1) if ej != "(escribir la propia)" else ("ana.soporte", ""))
    with c1:
        usuario = st.selectbox("Usuario", list(cfg.usuarios), index=list(cfg.usuarios).index(u_def))
        st.caption(f"Rol: **{cfg.usuarios[usuario]}**")
    with c2:
        consulta = st.text_input("Consulta", q_def)

    if st.button("Consultar", type="primary") and consulta.strip():
        entrada = Entrada(usuario=usuario, consulta=consulta, k=k)
        llm = llm_groq(modelo_llm, groq_key) if groq_key else None
        with st.spinner("Recuperando y generando..."):
            st.session_state.resultado = responder(entrada, col, get_embedder(cohere_key), llm)
            st.session_state.modelo_usado = modelo_llm if groq_key else "(sin LLM)"
            st.session_state.decidido = False
        if st.session_state.resultado["salida"].requiere_humano:
            st.session_state.caso_id = hitl.registrar_caso(st.session_state.resultado, "requiere_humano")

    res = st.session_state.get("resultado")
    if res:
        t, s = res["traza"], res["salida"]
        top_ids = {r.fragmento_id for r in t.resultados}
        st.graphviz_chart(f"""digraph {{ rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#f1f3f5", fontname="Helvetica", fontsize=10];
            q [label="Consulta\\n{t.usuario}"]; f [label="Pre-filter\\nwhere rol_{t.rol}=True\\n{t.visibles}/{t.total} fragmentos"];
            v [label="Vectorial\\n{len(t.vectorial)} candidatos"]; b [label="BM25\\n{len(t.lexica)} candidatos"];
            r [label="RRF k={cfg.recuperacion.rrf_k}\\ntop-{len(t.resultados)}"]; g [label="Groq\\n{st.session_state.modelo_usado}"];
            h [label="{'Derivado a humano' if s.requiere_humano else 'Revisión humana'}", fillcolor="{'#ffe3e3' if s.requiere_humano else '#d3f9d8'}"];
            q->f; f->v; f->b; v->r; b->r; r->g; g->h; }}""")

        _paso(0, "Entrada (contrato Pydantic)")
        st.json(res["entrada"].model_dump())

        _paso(1, "Control de acceso: usuario -> rol -> filtro ANTES de buscar")
        a = st.columns(4)
        a[0].metric("Rol", t.rol)
        a[1].metric("Fragmentos visibles", f"{t.visibles} / {t.total}")
        a[2].metric("Docs visibles", len(t.docs_visibles))
        a[3].metric("Docs excluidos", len(t.docs_excluidos))
        st.code(f"where = {t.filtro}", language="python")
        if t.docs_excluidos:
            st.caption("Excluidos antes de calcular cualquier puntaje: " + ", ".join(f"`{d}`" for d in t.docs_excluidos))

        _paso(2, "Recuperación en paralelo")
        cv, cb = st.columns(2)
        with cv:
            st.markdown("**Vectorial (embeddings, similitud coseno)**")
            st.dataframe(pd.DataFrame(t.vectorial, columns=["rank", "id", "documento", "seccion", "similitud"]),
                         hide_index=True, width="stretch")
        with cb:
            st.markdown("**Léxica (BM25 sobre el subconjunto permitido)**")
            st.dataframe(pd.DataFrame(t.lexica, columns=["rank", "id", "documento", "seccion", "score_bm25"]),
                         hide_index=True, width="stretch")

        _paso(3, f"Fusión RRF:  score(d) = 1/({cfg.recuperacion.rrf_k} + rank_vec) + 1/({cfg.recuperacion.rrf_k} + rank_bm25)")
        df_rrf = pd.DataFrame(t.rrf)[["id", "documento", "rank_vectorial", "rank_bm25", "aporte_vectorial", "aporte_bm25", "rrf"]]
        df_rrf.insert(0, "en_contexto", df_rrf["id"].isin(top_ids))
        st.dataframe(df_rrf, hide_index=True, width="stretch")

        _paso(4, "Prompt final enviado al LLM")
        if res["fugas"]:
            st.error(f"Fuga detectada: {res['fugas']}")
        else:
            st.success(f"Verificación de aislamiento: el prompt no contiene fragmentos prohibidos para '{t.rol}'.")
        with st.expander("Ver mensajes (system + user)"):
            for msg in res["prompt"]:
                st.markdown(f"**{msg['role']}**")
                st.code(msg["content"], language="xml")

        _paso(5, "Generación")
        g = st.columns(3)
        g[0].metric("Modelo", st.session_state.modelo_usado)
        g[1].metric("Latencia recuperación", f"{res['latencias']['recuperacion_s']} s")
        g[2].metric("Latencia generación", f"{res['latencias']['generacion_s']} s")
        (st.warning if s.requiere_humano else st.info)(s.respuesta or "(sin respuesta)")
        for fte in s.fuentes:
            frag = next(r for r in t.resultados if r.fragmento_id == fte.fragmento_id)
            with st.expander(f"Fuente: {fte.documento} - {fte.seccion} ({fte.fragmento_id})"):
                st.write(frag.texto)
        with st.expander("Salida validada (Pydantic) y respuesta cruda del LLM"):
            st.json(s.model_dump())
            if res["crudo"]:
                st.code(res["crudo"], language="json")

        _paso(6, "Human in the loop")
        if s.requiere_humano:
            st.error(f"requiere_humano = true. Motivo: {s.motivo_escalamiento}")
            st.caption(f"Caso `{st.session_state.get('caso_id')}` registrado en la cola. Resolvelo en la pestaña 3.")
        elif st.session_state.get("decidido"):
            st.success("Decisión registrada en el log de auditoría.")
        else:
            st.caption("La respuesta tiene evidencia, pero un operador la revisa antes de enviarla al usuario.")
            operador = st.text_input("Operador", "supervisor.turno")
            editada = st.text_area("Respuesta a enviar", s.respuesta, height=120)
            b1, b2, b3 = st.columns(3)
            if b1.button("Aprobar y enviar"):
                hitl.registrar_decision(res, operador, "aprobada" if editada == s.respuesta else "editada", editada)
                st.session_state.decidido = True
                st.rerun()
            if b3.button("Derivar a especialista"):
                res["salida"].motivo_escalamiento = "Derivado manualmente por el revisor."
                hitl.registrar_caso(res, "revision")
                st.session_state.decidido = True
                st.rerun()


with tab_inf:
    _inferencia()

# ================================================================ 3. COLA HUMANA
with tab_hitl:
    pendientes = hitl.listar("pendiente")
    st.subheader(f"Casos pendientes: {len(pendientes)}")
    for c in pendientes:
        with st.expander(f"[{c['id']}] {c['usuario']} ({c['rol']}) - {c['consulta']}"):
            st.markdown(f"**Motivo:** {c['motivo']}  \n**Origen:** {c['origen']}  \n**Fragmentos vistos:** {c['fragmentos']}")
            if c.get("borrador"):
                st.caption(f"Borrador del sistema: {c['borrador']}")
            resp = st.text_area("Respuesta del especialista", key=f"r_{c['id']}")
            op = st.text_input("Operador", "especialista.n2", key=f"o_{c['id']}")
            x1, x2 = st.columns(2)
            if x1.button("Responder y cerrar", key=f"ok_{c['id']}", disabled=not resp.strip()):
                hitl.resolver(c["id"], op, resp, "resuelto")
                st.rerun()
            if x2.button("Cerrar: fuera de alcance", key=f"no_{c['id']}"):
                hitl.resolver(c["id"], op, resp or "Consulta fuera del alcance de la base documental.", "descartado")
                st.rerun()
    historial = [c for c in hitl.listar() if c["estado"] != "pendiente"]
    if historial:
        st.subheader("Historial auditado")
        st.dataframe(pd.DataFrame(historial)[["id", "estado", "origen", "usuario", "rol", "consulta", "operador", "respuesta_final", "resuelto"]],
                     hide_index=True, width="stretch")
