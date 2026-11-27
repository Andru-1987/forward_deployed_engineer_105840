"""Typed config: parameters in config.toml, secrets in .env."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent


class LLMConfig(BaseModel):
    modelo: str
    temperatura: float = Field(ge=0.0, le=2.0)
    max_reintentos_validacion: int = Field(ge=0, le=3)


class TarifasConfig(BaseModel):
    input: float = Field(gt=0.0)
    output: float = Field(gt=0.0)


class ReglasNegocioConfig(BaseModel):
    monto_maximo_reembolso_usd: float = Field(gt=0.0)
    umbral_confianza_hitl: float = Field(ge=0.0, le=1.0)


class RolloutConfig(BaseModel):
    porcentaje_canary: int = Field(ge=0, le=100)
    prompt_estable: str
    prompt_canary: str


class AppConfig(BaseModel):
    llm: LLMConfig
    tarifas_usd_por_millon: TarifasConfig
    reglas_negocio: ReglasNegocioConfig
    rollout: RolloutConfig


class Secrets(BaseSettings):
    """Reads GROQ_API_KEY from env or .env. SecretStr keeps it out of logs."""

    model_config = SettingsConfigDict(env_file=RAIZ / ".env", extra="ignore")
    groq_api_key: SecretStr


def cargar_config(ruta: Path = RAIZ / "config.toml") -> AppConfig:
    # tomllib requires binary mode. A broken config must fail at startup.
    with ruta.open("rb") as f:
        return AppConfig.model_validate(tomllib.load(f))
