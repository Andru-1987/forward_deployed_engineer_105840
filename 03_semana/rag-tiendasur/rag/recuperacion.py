"""Etapa 2: RECUPERACIÓN. usuario -> rol -> where (pre-filter) -> vectorial || BM25 -> RRF."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi

from .config import cfg

STOPWORDS = set("""a al algo como con de del el en es esta este hay la las lo los me mi para por que qué se
si sin su sus te tengo un una y o cual cuál cuando cuándo cuanto cuántos cuántas hago puedo debo""".split())


def tokenizar(texto: str) -> list[str]:
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return [w for w in re.findall(r"\w+", t) if w not in STOPWORDS]


def rol_de(usuario: str) -> str:
    if usuario not in cfg.usuarios:
        raise PermissionError(f"Usuario desconocido: {usuario!r}. Sin rol no hay búsqueda.")
    return cfg.usuarios[usuario]


def filtro_rol(rol: str) -> dict:
    return {f"rol_{rol}": True}


@dataclass
class Resultado:
    fragmento_id: str
    documento: str
    seccion: str
    texto: str


@dataclass
class Traza:
    usuario: str
    rol: str
    filtro: dict
    visibles: int
    total: int
    docs_visibles: list[str]
    docs_excluidos: list[str]
    vectorial: list[dict] = field(default_factory=list)
    lexica: list[dict] = field(default_factory=list)
    rrf: list[dict] = field(default_factory=list)
    resultados: list[Resultado] = field(default_factory=list)


# Índice BM25 cacheado por (colección, rol, contenido): se invalida solo si cambia la colección.
_CACHE_BM25: dict = {}


def _indice_bm25(col, rol):
    permitidos = col.get(where=filtro_rol(rol), include=["documents", "metadatas"])
    clave = (col.name, rol, len(permitidos["ids"]), hash(tuple(permitidos["ids"])))
    if clave not in _CACHE_BM25:
        corpus = [tokenizar(t) for t in permitidos["documents"]]
        _CACHE_BM25[clave] = (BM25Okapi(corpus) if corpus else None, permitidos)
    return _CACHE_BM25[clave]


def buscar_vectorial(col, embedder, consulta: str, rol: str, k: int) -> list[dict]:
    n_permitidos = len(col.get(where=filtro_rol(rol), include=[])["ids"])
    n = min(k, n_permitidos)  # si el rol ve menos fragmentos que k, Chroma devolvería menos (y avisa)
    if n == 0:
        return []
    r = col.query(query_embeddings=[embedder.embed_consulta(consulta)], n_results=n,
                  where=filtro_rol(rol), include=["documents", "metadatas", "distances"])
    return [{"rank": i + 1, "id": fid, "documento": m["documento"], "seccion": m["seccion"],
             "similitud": round(1 - d, 4), "texto": t}
            for i, (fid, m, d, t) in enumerate(zip(r["ids"][0], r["metadatas"][0], r["distances"][0], r["documents"][0]))]


def buscar_lexica(col, consulta: str, rol: str, k: int) -> list[dict]:
    bm25, permitidos = _indice_bm25(col, rol)
    if bm25 is None:
        return []
    puntajes = bm25.get_scores(tokenizar(consulta))
    orden = [i for i in sorted(range(len(puntajes)), key=lambda i: puntajes[i], reverse=True) if puntajes[i] > 0][:k]
    return [{"rank": r + 1, "id": permitidos["ids"][i], "documento": permitidos["metadatas"][i]["documento"],
             "seccion": permitidos["metadatas"][i]["seccion"], "score_bm25": round(float(puntajes[i]), 4),
             "texto": permitidos["documents"][i]} for r, i in enumerate(orden)]


def rrf(*rankings: list[dict], k: int = cfg.recuperacion.rrf_k) -> list[dict]:
    """Score_RRF(d) = sum 1/(k + rank(d)). Devuelve el detalle de cada aporte."""
    tabla: dict[str, dict] = {}
    for nombre, ranking in zip(("vectorial", "bm25"), rankings):
        for item in ranking:
            fila = tabla.setdefault(item["id"], {"id": item["id"], "documento": item["documento"],
                                                 "seccion": item["seccion"], "texto": item["texto"],
                                                 "rank_vectorial": None, "rank_bm25": None,
                                                 "aporte_vectorial": 0.0, "aporte_bm25": 0.0})
            fila[f"rank_{nombre}"] = item["rank"]
            fila[f"aporte_{nombre}"] = round(1 / (k + item["rank"]), 6)
            if "similitud" in item:
                fila["similitud"] = item["similitud"]
            if "score_bm25" in item:
                fila["score_bm25"] = item["score_bm25"]
    for f in tabla.values():
        f["rrf"] = round(f["aporte_vectorial"] + f["aporte_bm25"], 6)
    return sorted(tabla.values(), key=lambda f: f["rrf"], reverse=True)


def buscar(consulta: str, usuario: str, k: int, col, embedder, modo: str = "hibrida") -> Traza:
    """Contrato PE3: mapea usuario->rol, busca con where en AMBAS búsquedas y fusiona con RRF."""
    modelo_col = (col.metadata or {}).get("embedding_modelo")
    if modelo_col and modelo_col != embedder.nombre:
        raise ValueError(f"La colección se ingestó con {modelo_col} y la consulta usa {embedder.nombre}. Re-ingestá.")
    rol = rol_de(usuario)
    kc = max(3 * k, 10)  # candidatos por búsqueda antes de fusionar
    visibles = col.get(where=filtro_rol(rol), include=["metadatas"])
    todos = col.get(include=["metadatas"])
    docs_vis = sorted({m["documento"] for m in visibles["metadatas"]})
    traza = Traza(usuario=usuario, rol=rol, filtro=filtro_rol(rol), visibles=len(visibles["ids"]),
                  total=len(todos["ids"]), docs_visibles=docs_vis,
                  docs_excluidos=sorted({m["documento"] for m in todos["metadatas"]} - set(docs_vis)))

    traza.vectorial = buscar_vectorial(col, embedder, consulta, rol, kc) if modo in ("hibrida", "vectorial") else []
    traza.lexica = buscar_lexica(col, consulta, rol, kc) if modo in ("hibrida", "bm25") else []
    traza.rrf = rrf(traza.vectorial, traza.lexica)
    traza.resultados = [Resultado(fragmento_id=f["id"], documento=f["documento"], seccion=f["seccion"], texto=f["texto"])
                        for f in traza.rrf[:k]]
    return traza
