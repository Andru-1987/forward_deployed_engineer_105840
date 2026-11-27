"""Etapa 1: INGESTA. Lectura -> limpieza -> secciones -> chunking con solapamiento -> embeddings -> ChromaDB."""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import chromadb

from .config import cfg

SEPARADORES = ["\n\n", "\n", ". ", " "]


@dataclass
class Documento:
    id: str
    titulo: str
    roles: list[str]
    texto: str
    origen: str
    chars_crudos: int = 0


# ---------- Lectura y limpieza ----------------------------------------------
def _frontmatter(texto: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", texto, re.S)
    if not m:
        return {}, texto
    meta = {}
    for linea in m.group(1).splitlines():
        if ":" in linea:
            k, v = linea.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, texto[m.end():]


def limpiar(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\t", " ")
    texto = re.sub(r"[^\S\n]+", " ", texto)          # espacios repetidos
    texto = re.sub(r"\n{3,}", "\n\n", texto)          # líneas en blanco repetidas
    texto = "".join(c for c in texto if c == "\n" or c.isprintable())
    return texto.strip()


def leer_documento(nombre: str, contenido: bytes, roles: list[str] | None = None) -> Documento:
    if nombre.lower().endswith(".pdf"):
        from pypdf import PdfReader

        crudo = "\n\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(contenido)).pages)
    else:
        crudo = contenido.decode("utf-8", errors="ignore")
    meta, cuerpo = _frontmatter(crudo)
    roles_fm = [r.strip() for r in meta.get("roles", "").strip("[]").split(",") if r.strip()]
    roles_final = roles if roles is not None else roles_fm
    if not roles_final:
        roles_final = ["admin"]  # deny-by-default: sin ACL explícita solo lo ve admin
    doc_id = re.sub(r"\W+", "_", Path(nombre).stem.lower()).strip("_")
    return Documento(
        id=doc_id, titulo=meta.get("titulo", Path(nombre).stem), roles=[r for r in roles_final if r in cfg.roles],
        texto=limpiar(cuerpo), origen=nombre, chars_crudos=len(crudo),
    )


def leer_carpeta(ruta: str | Path) -> list[Documento]:
    exts = {".md", ".txt", ".pdf"}
    return [leer_documento(p.name, p.read_bytes()) for p in sorted(Path(ruta).iterdir()) if p.suffix.lower() in exts]


# ---------- Secciones y chunking ---------------------------------------------
def dividir_secciones(texto: str) -> list[tuple[str, str]]:
    """Corta en encabezados markdown. Devuelve (ruta_de_seccion, cuerpo)."""
    pila: list[tuple[int, str]] = []
    secciones, buffer, actual = [], [], "General"
    for linea in texto.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", linea)
        if m:
            if "\n".join(buffer).strip():
                secciones.append((actual, "\n".join(buffer).strip()))
            buffer = []
            nivel, titulo = len(m.group(1)), m.group(2).strip()
            pila = [(n, t) for n, t in pila if n < nivel] + [(nivel, titulo)]
            actual = " > ".join(t for n, t in pila if n > 1) or titulo
        else:
            buffer.append(linea)
    if "\n".join(buffer).strip():
        secciones.append((actual, "\n".join(buffer).strip()))
    return secciones


def _split_recursivo(texto: str, tamano: int, seps: list[str]) -> list[str]:
    if len(texto) <= tamano:
        return [texto]
    sep = next((s for s in seps if s in texto), None)
    if sep is None:
        return [texto[i:i + tamano] for i in range(0, len(texto), tamano)]
    resto = seps[seps.index(sep) + 1:]
    piezas, actual = [], ""
    for parte in texto.split(sep):
        candidato = f"{actual}{sep}{parte}" if actual else parte
        if len(candidato) <= tamano:
            actual = candidato
            continue
        if actual:
            piezas.append(actual)
        if len(parte) > tamano:
            piezas.extend(_split_recursivo(parte, tamano, resto))
            actual = ""
        else:
            actual = parte
    if actual:
        piezas.append(actual)
    return piezas


def fragmentar(texto: str, tamano: int = cfg.chunking.tamano, solapamiento: int = cfg.chunking.solapamiento) -> list[str]:
    """Recursive Character Chunking: párrafo > línea > oración > palabra, con solapamiento en caracteres."""
    piezas = [p.strip() for p in _split_recursivo(texto, tamano, SEPARADORES) if p.strip()]
    salida = []
    for i, p in enumerate(piezas):
        if i and solapamiento:
            cola = piezas[i - 1][-solapamiento:]
            cola = cola.split(" ", 1)[1] if " " in cola else cola  # no cortar palabras
            p = f"{cola} {p}"
        salida.append(p)
    return salida


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()[:16]


# ---------- Ingesta completa con reporte paso a paso ------------------------
def ingestar(documentos: list[Documento], embedder, tamano: int = cfg.chunking.tamano,
             solapamiento: int = cfg.chunking.solapamiento, ruta: str = cfg.rutas.chroma,
             nombre_coleccion: str = cfg.coleccion):
    """Devuelve (coleccion, reporte). Recrea la colección para no duplicar al cambiar el chunking."""
    reporte = {"documentos": [], "fragmentos": [], "tiempos": {}}

    ids, textos, metas = [], [], []
    for doc in documentos:
        doc_hash = _hash(doc.texto)
        n_doc = 0
        for seccion, cuerpo in dividir_secciones(doc.texto):
            for frag in fragmentar(cuerpo, tamano, solapamiento):
                fid = f"{doc.id}#{n_doc}"
                meta = {
                    "documento": doc.id, "titulo": doc.titulo, "seccion": seccion, "origen": doc.origen,
                    "fragmento_idx": n_doc, "hash": _hash(frag), "doc_hash": doc_hash,
                    "roles": ",".join(doc.roles), "chunk_tamano": tamano, "chunk_solapamiento": solapamiento,
                    "embedding_modelo": embedder.nombre,
                    "ingestado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                for rol in cfg.roles:  # un booleano por rol -> filtrable con where en Chroma
                    meta[f"rol_{rol}"] = rol in doc.roles
                ids.append(fid); textos.append(frag); metas.append(meta)
                n_doc += 1
        reporte["documentos"].append({
            "documento": doc.id, "titulo": doc.titulo, "origen": doc.origen, "roles": ", ".join(doc.roles),
            "chars_crudos": doc.chars_crudos, "chars_limpios": len(doc.texto), "fragmentos": n_doc, "doc_hash": doc_hash,
        })

    t1 = time.perf_counter()
    vectores = embedder.embed_documentos(textos) if textos else []
    reporte["tiempos"]["embedding_s"] = round(time.perf_counter() - t1, 3)

    t2 = time.perf_counter()
    cliente = chromadb.PersistentClient(path=ruta)
    if nombre_coleccion in [c.name for c in cliente.list_collections()]:
        cliente.delete_collection(nombre_coleccion)
    col = cliente.get_or_create_collection(
        nombre_coleccion,
        embedding_function=None,  # los vectores los calcula Cohere (rag/embeddings.py), no Chroma
        metadata={"hnsw:space": "cosine", "embedding_modelo": embedder.nombre, "dim": embedder.dim},
    )
    for i in range(0, len(ids), 256):
        col.upsert(ids=ids[i:i + 256], documents=textos[i:i + 256],
                   embeddings=vectores[i:i + 256], metadatas=metas[i:i + 256])
    reporte["tiempos"]["carga_chroma_s"] = round(time.perf_counter() - t2, 3)

    reporte["fragmentos"] = [{"id": i, "texto": t, "metadatos": m, "vector": v}
                             for i, t, m, v in zip(ids, textos, metas, vectores)]
    reporte["coleccion"] = {"nombre": nombre_coleccion, "ruta": ruta, "total": col.count(),
                            "embedding_modelo": embedder.nombre, "dim": embedder.dim}
    return col, reporte


def abrir_coleccion(ruta: str = cfg.rutas.chroma, nombre: str = cfg.coleccion):
    return chromadb.PersistentClient(path=ruta).get_collection(nombre, embedding_function=None)


if __name__ == "__main__":  # Un solo comando: python -m rag.ingesta docs_cliente
    from .config import secretos
    from .embeddings import CohereEmbedder

    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta", nargs="?", default=cfg.rutas.docs_cliente)
    ap.add_argument("--tamano", type=int, default=cfg.chunking.tamano)
    ap.add_argument("--solapamiento", type=int, default=cfg.chunking.solapamiento)
    a = ap.parse_args()
    embedder = CohereEmbedder(secretos.cohere_api_key.get_secret_value())
    _, rep = ingestar(leer_carpeta(a.carpeta), embedder, a.tamano, a.solapamiento)
    for d in rep["documentos"]:
        print(f"{d['documento']:<32} roles=[{d['roles']}] fragmentos={d['fragmentos']}")
    print("Colección:", rep["coleccion"])
