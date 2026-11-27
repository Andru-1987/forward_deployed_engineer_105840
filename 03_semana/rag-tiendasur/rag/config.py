"""Configuración tipada: parámetros en config.toml, secretos en .env."""
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent


class Rutas(BaseModel):
    docs_cliente: str
    chroma: str
    cola_humana: str


class Chunking(BaseModel):
    tamano: int = Field(gt=0)
    solapamiento: int = Field(ge=0)


class Recuperacion(BaseModel):
    k: int = Field(ge=1, le=10)
    rrf_k: int = Field(gt=0)


class LLM(BaseModel):
    temperatura: float = Field(ge=0.0, le=2.0)
    modelos: list[str] = Field(min_length=1)


class Embedding(BaseModel):
    modelo: str
    dim: int = Field(gt=0)


class AppConfig(BaseModel):
    roles: list[str]
    coleccion: str
    rutas: Rutas
    chunking: Chunking
    recuperacion: Recuperacion
    llm: LLM
    embedding: Embedding
    usuarios: dict[str, str]  # usuario -> rol

    @model_validator(mode="after")
    def _roles_conocidos(self) -> "AppConfig":
        invalidos = {u: r for u, r in self.usuarios.items() if r not in self.roles}
        if invalidos:
            raise ValueError(f"Usuarios con rol inexistente: {invalidos}")
        return self


class Secretos(BaseSettings):
    """Lee las API keys del entorno o de .env. SecretStr evita que salgan en logs. Vacía = no configurada."""

    model_config = SettingsConfigDict(env_file=RAIZ / ".env", extra="ignore")
    groq_api_key: SecretStr = SecretStr("")      # generación
    cohere_api_key: SecretStr = SecretStr("")    # embeddings (ingesta y consulta)


def cargar_config(ruta: Path = RAIZ / "config.toml") -> AppConfig:
    with ruta.open("rb") as f:  # tomllib exige modo binario
        return AppConfig.model_validate(tomllib.load(f))


cfg = cargar_config()   # una config para toda la app: si el TOML está roto, falla al arrancar
secretos = Secretos()
