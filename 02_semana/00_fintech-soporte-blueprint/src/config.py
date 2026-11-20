"""Configuracion tipada: parametros en config.toml, secretos en .env.

Leccion FDE: separar "que cambia seguido y no es secreto" (TOML, versionable)
de "que jamas se versiona" (.env). Asi el equipo de negocio puede ajustar un
umbral sin tocar codigo y una API key nunca termina en Git.
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


class ObjetivosConfig(BaseModel):
    validez_primer_intento_min: float
    costo_promedio_max_usd: float
    latencia_p95_max_ms: int


class UmbralesRollbackConfig(BaseModel):
    tasa_validation_error_max: float
    latencia_p95_max_ms: int
    tasa_error_http_max: float
    incremento_costo_max: float


class AppConfig(BaseModel):
    llm: LLMConfig
    tarifas_usd_por_millon: TarifasConfig
    reglas_negocio: ReglasNegocioConfig
    rollout: RolloutConfig
    objetivos: ObjetivosConfig
    umbrales_rollback: UmbralesRollbackConfig


class Secrets(BaseSettings):
    """Lee GROQ_API_KEY del entorno o de .env. SecretStr evita que salga en logs."""

    model_config = SettingsConfigDict(env_file=RAIZ / ".env", extra="ignore")
    groq_api_key: SecretStr


def cargar_config(ruta: Path = RAIZ / "config.toml") -> AppConfig:
    # tomllib exige modo binario. Pydantic valida tipos y rangos al arrancar:
    # un config roto debe fallar al iniciar, no a las 3 AM en produccion.
    with ruta.open("rb") as f:
        return AppConfig.model_validate(tomllib.load(f))
