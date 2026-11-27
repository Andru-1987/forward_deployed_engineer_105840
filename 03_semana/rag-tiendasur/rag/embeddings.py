"""Embeddings con Cohere. Interfaz: nombre, dim, embed_documentos, embed_consulta."""
import cohere

from .config import cfg

LOTE = 96  # máximo de textos por llamada a la API de Cohere


class CohereEmbedder:
    def __init__(self, api_key: str, modelo: str = cfg.embedding.modelo, dim: int = cfg.embedding.dim):
        self.cliente = cohere.ClientV2(api_key=api_key)
        self.nombre, self.dim = modelo, dim

    def _embed(self, textos: list[str], tipo: str) -> list[list[float]]:
        vectores = []
        for i in range(0, len(textos), LOTE):
            r = self.cliente.embed(texts=textos[i:i + LOTE], model=self.nombre, input_type=tipo,
                                   embedding_types=["float"])
            vectores += r.embeddings.float_
        return vectores

    def embed_documentos(self, textos: list[str]) -> list[list[float]]:
        return self._embed(textos, "search_document")

    def embed_consulta(self, texto: str) -> list[float]:
        return self._embed([texto], "search_query")[0]
