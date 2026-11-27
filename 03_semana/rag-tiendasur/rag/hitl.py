"""Human in the loop: cola de casos derivados y revisión de respuestas (JSONL auditable)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import cfg

COLA = Path(cfg.rutas.cola_humana)


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _leer() -> list[dict]:
    if not COLA.exists():
        return []
    return [json.loads(l) for l in COLA.read_text(encoding="utf-8").splitlines() if l.strip()]


def _guardar(casos: list[dict]) -> None:
    COLA.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in casos), encoding="utf-8")


def registrar_caso(resultado: dict, origen: str) -> str:
    """origen: 'requiere_humano' (lo decidió el sistema) o 'revision' (lo derivó el revisor)."""
    s, t = resultado["salida"], resultado["traza"]
    caso = {
        "id": uuid.uuid4().hex[:8], "creado": _ahora(), "estado": "pendiente", "origen": origen,
        "usuario": t.usuario, "rol": t.rol, "consulta": resultado["entrada"].consulta,
        "motivo": s.motivo_escalamiento, "borrador": s.respuesta,
        "fragmentos": [r.fragmento_id for r in t.resultados],
    }
    _guardar(_leer() + [caso])
    return caso["id"]


def registrar_decision(resultado: dict, operador: str, decision: str, respuesta_final: str) -> None:
    """Auditoría de respuestas aprobadas/editadas por un humano antes de enviarse."""
    t = resultado["traza"]
    caso = {"id": uuid.uuid4().hex[:8], "creado": _ahora(), "estado": decision, "origen": "revision",
            "usuario": t.usuario, "rol": t.rol, "consulta": resultado["entrada"].consulta,
            "borrador": resultado["salida"].respuesta, "respuesta_final": respuesta_final,
            "operador": operador, "resuelto": _ahora(),
            "fragmentos": [f.fragmento_id for f in resultado["salida"].fuentes]}
    _guardar(_leer() + [caso])


def listar(estado: str | None = None) -> list[dict]:
    return [c for c in _leer() if estado is None or c["estado"] == estado]


def resolver(caso_id: str, operador: str, respuesta_final: str, decision: str = "resuelto") -> None:
    casos = _leer()
    for c in casos:
        if c["id"] == caso_id:
            c.update(estado=decision, operador=operador, respuesta_final=respuesta_final, resuelto=_ahora())
    _guardar(casos)
