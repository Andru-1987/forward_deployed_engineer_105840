"""Un modelo falso para probar el motor sin API key y sin gastar.

Reemplaza a llamar_modelo(): recibe lo mismo y devuelve (texto, tokens_entrada, tokens_salida).
Se usa en los tests y en src/demo_reintento.py.
"""


class ModeloSimulado:
    """Devuelve, en orden, las respuestas que le pases."""

    def __init__(self, respuestas: list[str], tokens_entrada=900, tokens_salida=120):
        self.respuestas = list(respuestas)
        self.llamadas = 0
        self.tokens_entrada = tokens_entrada
        self.tokens_salida = tokens_salida

    def __call__(self, sistema: str, mensajes: list[dict], proveedor: str):
        texto = self.respuestas[self.llamadas]
        self.llamadas += 1
        return texto, self.tokens_entrada, self.tokens_salida
