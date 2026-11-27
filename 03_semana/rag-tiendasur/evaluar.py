"""Golden set + Top-k con 2 configuraciones de chunking y 3 modos de búsqueda.

uv run python evaluar.py      (necesita COHERE_API_KEY en .env)
Salida: tabla markdown lista para pegar en el PDF de la PE3.
"""
import json

from rag.config import cfg, secretos
from rag.embeddings import CohereEmbedder
from rag.ingesta import ingestar, leer_carpeta
from rag.recuperacion import buscar

CONFIGS = [("chicos", 250, 0), ("medianos_10pct", 600, 60)]
MODOS = ["vectorial", "bm25", "hibrida"]
KS = [1, 3, 5]


def evaluar(embedder, golden, docs, ruta="./chroma_eval"):
    filas = []
    for nombre, tamano, solap in CONFIGS:
        col, rep = ingestar(docs, embedder, tamano, solap, ruta=ruta, nombre_coleccion="eval")
        for modo in MODOS:
            hits = {k: 0 for k in KS}
            frag = 0  # texto_clave dentro de los top-3 fragmentos (mide si el chunk conserva la regla completa)
            n_norm = seguros = 0
            for q in golden:
                traza = buscar(q["consulta"], q["usuario"], max(KS), col, embedder, modo=modo)
                docs_rank = [r.documento for r in traza.resultados]
                if q["tipo"] == "normal":
                    n_norm += 1
                    for k in KS:
                        hits[k] += q["documento_esperado"] in docs_rank[:k]
                    frag += any(q["texto_clave"].lower() in r.texto.lower() for r in traza.resultados[:3])
                elif q["tipo"] == "restringido":
                    seguros += q["documento_prohibido"] not in docs_rank
            filas.append({"config": f"{nombre} ({tamano}c/{solap}c)", "fragmentos": rep["coleccion"]["total"], "modo": modo,
                          **{f"Hit@{k}": f"{hits[k]}/{n_norm}" for k in KS}, "Frag@3": f"{frag}/{n_norm}", "restringidos_ok": f"{seguros}/2"})
    return filas


if __name__ == "__main__":
    golden = json.load(open("golden_set.json", encoding="utf-8"))
    embedder = CohereEmbedder(secretos.cohere_api_key.get_secret_value())
    filas = evaluar(embedder, golden, leer_carpeta(cfg.rutas.docs_cliente))
    cols = list(filas[0])
    print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
    for f in filas:
        print("| " + " | ".join(str(f[c]) for c in cols) + " |")
    print("\nPreguntas sin respuesta (7, 8): verificá en la UI que terminen en requiere_humano = true.")
