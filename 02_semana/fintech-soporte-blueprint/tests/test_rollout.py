from src.metricas import RegistroTurno, incumplimientos, percentil, resumir
from src.rollout import elegir_version, evaluar_rollback


def reg(version="v1", **kw):
    base = dict(version=version, ok=True, primer_intento=True, costo_usd=0.001,
                latencia_ms=800, error_validacion=False, error_http=False)
    return RegistroTurno(**{**base, **kw})


def test_hash_consistente_y_proporcion():
    assert elegir_version("u1", 5) == elegir_version("u1", 5)
    canary = sum(elegir_version(f"user-{i}", 5) == "v2" for i in range(10_000))
    assert 350 < canary < 650   # ~5%
    assert elegir_version("u1", 0) == "v1" and elegir_version("u1", 100) == "v2"


def test_percentil():
    assert percentil(list(range(1, 101)), 95) == 95


def test_canary_sano_no_hace_rollback(config):
    regs = [reg("v1") for _ in range(95)] + [reg("v2") for _ in range(5)]
    assert evaluar_rollback(regs, config.umbrales_rollback) == []


def test_un_fallo_de_seguridad_basta(config):
    regs = [reg("v1")] * 95 + [reg("v2", fallo_seguridad=True)] + [reg("v2")] * 4
    assert any("seguridad" in m for m in evaluar_rollback(regs, config.umbrales_rollback))


def test_rollback_por_costo_latencia_y_validacion(config):
    regs = [reg("v1")] * 50 + [reg("v2", costo_usd=0.002, latencia_ms=3000, error_validacion=True)] * 10
    motivos = " ".join(evaluar_rollback(regs, config.umbrales_rollback))
    for clave in ("calidad", "latencia", "costo"):
        assert clave in motivos


def test_incumplimientos(config):
    assert incumplimientos(resumir([reg()]), config.objetivos) == []
    assert incumplimientos(resumir([reg(latencia_ms=5000)]), config.objetivos)
