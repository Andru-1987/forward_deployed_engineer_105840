"""Tests de permisos y grounding. Corren offline con HashEmbedder y un LLM falso.

pytest -q
"""
import json

import pytest

from rag.generacion import Entrada, responder
from rag.ingesta import ingestar, leer_carpeta
from rag.recuperacion import buscar
from tests.hash_embedder import HashEmbedder

RESTRINGIDOS = {"soporte": {"bandas_salariales_2025", "presupuesto_2025"},
                "rrhh": {"presupuesto_2025", "manual_router_fs3000", "protocolo_escalamiento_soporte"},
                "admin": set()}
USUARIO_DE = {"soporte": "ana.soporte", "rrhh": "lucia.rrhh", "admin": "carlos.admin"}
CONSULTAS_SENSIBLES = ["presupuesto del proyecto Alpha-X", "banda salarial agente nivel 2",
                       "error ERR_9921_X reiniciar router"]


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    emb = HashEmbedder()
    col, _ = ingestar(leer_carpeta("docs_cliente"), emb, 600, 60, ruta=str(tmp_path_factory.mktemp("chroma")))
    return col, emb


class LLMEspia:
    """Captura el prompt y responde citando el primer fragmento recibido."""

    def __init__(self):
        self.prompts = []

    def __call__(self, mensajes):
        self.prompts.append("\n".join(m["content"] for m in mensajes))
        import re
        m = re.search(r'id="([^"]+)" documento="([^"]+)"', mensajes[1]["content"])
        return json.dumps({"respuesta": "ok", "fuentes": [{"documento": m.group(2), "fragmento_id": m.group(1)}] if m else [],
                           "requiere_humano": m is None, "confianza": "media"})


@pytest.mark.parametrize("rol", ["soporte", "rrhh", "admin"])
@pytest.mark.parametrize("consulta", CONSULTAS_SENSIBLES)
def test_buscar_no_devuelve_documentos_restringidos(entorno, rol, consulta):
    col, emb = entorno
    traza = buscar(consulta, USUARIO_DE[rol], 10, col, emb)
    vistos = {r.documento for r in traza.resultados} | {f["documento"] for f in traza.vectorial + traza.lexica}
    assert not vistos & RESTRINGIDOS[rol]


def test_admin_ve_presupuesto(entorno):
    col, emb = entorno
    traza = buscar("presupuesto del proyecto Alpha-X", "carlos.admin", 3, col, emb)
    assert traza.resultados[0].documento == "presupuesto_2025"


@pytest.mark.parametrize("rol", ["soporte", "rrhh"])
def test_dato_restringido_no_llega_al_prompt(entorno, rol):
    col, emb = entorno
    espia = LLMEspia()
    r = responder(Entrada(usuario=USUARIO_DE[rol], consulta="presupuesto 2025 Alpha-X 1.200 millones"), col, emb, espia)
    prompt = espia.prompts[0]
    # La consulta menciona el tema, pero ningún fragmento del documento restringido puede estar en el contexto.
    assert 'documento="presupuesto_2025"' not in prompt and "18.000 hogares" not in prompt
    assert r["fugas"] == []


def test_usuario_desconocido_no_busca(entorno):
    col, emb = entorno
    with pytest.raises(PermissionError):
        buscar("vacaciones", "intruso", 3, col, emb)


def test_hibrida_distingue_codigos_casi_identicos(entorno):
    col, emb = entorno
    traza = buscar("Que hago con el error ERR_9921_X?", "ana.soporte", 3, col, emb)
    assert "ERR_9921_X" in traza.resultados[0].texto


def test_fuente_inventada_fuerza_requiere_humano(entorno):
    col, emb = entorno
    falso = lambda _m: json.dumps({"respuesta": "Son 99 días", "fuentes": [{"documento": "x", "fragmento_id": "no_existe#0"}],
                                    "requiere_humano": False, "confianza": "alta"})
    r = responder(Entrada(usuario="martin.soporte", consulta="dias de vacaciones"), col, emb, falso)
    assert r["salida"].requiere_humano and r["salida"].fuentes == []


def test_salida_invalida_deriva_a_humano(entorno):
    col, emb = entorno
    r = responder(Entrada(usuario="martin.soporte", consulta="dias de vacaciones"), col, emb, lambda _m: "no soy json")
    assert r["salida"].requiere_humano
