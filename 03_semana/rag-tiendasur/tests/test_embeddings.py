"""CohereEmbedder: parte en lotes de 96 y usa el input_type correcto. Sin red: cliente falso."""
from types import SimpleNamespace

from rag.embeddings import LOTE, CohereEmbedder


class ClienteFalso:
    def __init__(self):
        self.llamadas = []

    def embed(self, texts, model, input_type, embedding_types):
        self.llamadas.append((len(texts), input_type))
        return SimpleNamespace(embeddings=SimpleNamespace(float_=[[0.0] * 384 for _ in texts]))


def _embedder():
    emb = CohereEmbedder("clave-falsa")
    emb.cliente = ClienteFalso()
    return emb


def test_documentos_van_en_lotes():
    emb = _embedder()
    vectores = emb.embed_documentos(["t"] * (LOTE + 1))
    assert len(vectores) == LOTE + 1
    assert emb.cliente.llamadas == [(LOTE, "search_document"), (1, "search_document")]


def test_consulta_usa_search_query():
    emb = _embedder()
    assert len(emb.embed_consulta("hola")) == emb.dim
    assert emb.cliente.llamadas == [(1, "search_query")]
