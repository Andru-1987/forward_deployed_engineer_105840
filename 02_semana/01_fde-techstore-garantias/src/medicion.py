"""Promedios de tokens, costo y latencia, y accuracy frente a la meta del KPI de PE1."""

from typing import Any, Sequence

from src.config import KpiConfig


def resumir(resultados: Sequence[dict[str, Any]], esperados: Sequence[str], kpi: KpiConfig) -> dict[str, Any]:
    n = len(resultados)
    aciertos = sum(r["ok"] and r["salida"]["estado"] == e for r, e in zip(resultados, esperados))
    accuracy = aciertos / n
    return {
        "consultas": n,
        "tokens_entrada_prom": sum(r["tokens"]["entrada"] for r in resultados) / n,
        "tokens_salida_prom": sum(r["tokens"]["salida"] for r in resultados) / n,
        "costo_usd_prom": sum(r["costo_usd"] for r in resultados) / n,
        "latencia_ms_prom": sum(r["latencia_ms"] for r in resultados) / n,
        "accuracy": accuracy,
        "accuracy_meta": kpi.accuracy_meta,
        "cumple_meta": accuracy >= kpi.accuracy_meta,
    }
