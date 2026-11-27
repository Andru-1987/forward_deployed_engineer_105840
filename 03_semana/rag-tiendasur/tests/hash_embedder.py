"""Embedder falso para tests: sin red ni API key. Hashing trick sobre palabras + trigramas."""
import hashlib
import math
import re
import unicodedata


class HashEmbedder:
    def __init__(self, dim: int = 256):
        self.nombre, self.dim = f"hash-offline-{dim}", dim

    def _vec(self, texto: str) -> list[float]:
        t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
        v = [0.0] * self.dim
        for tok in re.findall(r"\w+", t):
            for f in [tok] + [tok[i:i + 3] for i in range(max(len(tok) - 2, 0))]:
                h = int(hashlib.md5(f.encode()).hexdigest(), 16)
                v[h % self.dim] += 1.0 if (h >> 8) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documentos(self, textos: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in textos]

    def embed_consulta(self, texto: str) -> list[float]:
        return self._vec(texto)
