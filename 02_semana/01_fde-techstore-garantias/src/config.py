"""Configuracion tipada: parametros en config.toml, secretos en .env.

Leccion FDE: lo que cambia seguido y no es secreto va a TOML (versionable);
lo que jamas se versiona va a .env. Pydantic valida ambos al arrancar: un
archivo mal editado debe fallar al iniciar, no a mitad de la ejecucion.
"""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent


class LLMConfig(BaseModel):
    modelo: str
    temperatura: float = Field(ge=0.0, le=2.0)
    max_reintentos_validacion: int = Field(ge=0, le=3)
    ruta_system_prompt: str


class TarifasConfig(BaseModel):
    input: float = Field(gt=0.0)
    output: float = Field(gt=0.0)


class ReglasNegocioConfig(BaseModel):
    umbral_aprobacion_supervisor_usd: float = Field(gt=0.0)


class KpiConfig(BaseModel):
    accuracy_meta: float = Field(ge=0.0, le=1.0)


class AppConfig(BaseModel):
    llm: LLMConfig
    tarifas_usd_por_millon: TarifasConfig
    reglas_negocio: ReglasNegocioConfig
    kpi: KpiConfig


class Secrets(BaseSettings):
    """GROQ_API_KEY desde entorno o .env. SecretStr evita que aparezca en logs."""

    model_config = SettingsConfigDict(env_file=RAIZ / ".env", extra="ignore")
    groq_api_key: SecretStr


def cargar_config(ruta: Path = RAIZ / "config.toml") -> AppConfig:
    with ruta.open("rb") as f:  # tomllib exige modo binario
        return AppConfig.model_validate(tomllib.load(f))
