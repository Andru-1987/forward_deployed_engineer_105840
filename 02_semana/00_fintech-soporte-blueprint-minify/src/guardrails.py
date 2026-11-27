"""Input guardrail (Prompting stage): mask PII before it reaches the external LLM API."""

import re

# Order matters: longest first, so a CBU (22 digits) is not taken as card or DNI.
_PATRONES_PII = [
    ("CBU", re.compile(r"\b\d{22}\b")),
    ("TARJETA", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("DNI", re.compile(r"\b\d{7,8}\b")),
]


def enmascarar_pii(texto: str) -> str:
    for etiqueta, patron in _PATRONES_PII:
        texto = patron.sub(f"[{etiqueta}]", texto)
    return texto
