"""La config del repo es válida y rechaza usuarios con rol inexistente."""
import pytest
from pydantic import ValidationError

from rag.config import AppConfig, cfg


def test_config_del_repo_carga():
    assert cfg.embedding.dim == 384
    assert set(cfg.usuarios.values()) <= set(cfg.roles)


def test_usuario_con_rol_inexistente_falla():
    datos = cfg.model_dump() | {"usuarios": {"x": "rol_que_no_existe"}}
    with pytest.raises(ValidationError):
        AppConfig.model_validate(datos)
