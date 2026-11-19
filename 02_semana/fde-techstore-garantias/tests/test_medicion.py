from src.medicion import resumir


def res(estado, ok=True):
    base = {"ok": ok, "tokens": {"entrada": 100, "salida": 50}, "costo_usd": 0.001, "latencia_ms": 400}
    return {**base, "salida": {"estado": estado}} if ok else base


def test_promedios_y_accuracy(config):
    r = resumir([res("faltan_datos"), res("no_elegible"), res("x", ok=False), res("faltan_datos")],
                ["faltan_datos"] * 4, config.kpi)
    assert r["accuracy"] == 0.5 and not r["cumple_meta"]
    assert r["latencia_ms_prom"] == 400 and r["tokens_entrada_prom"] == 100
