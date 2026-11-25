"""Lee .env y config.toml una sola vez. Lo importan el motor y los proveedores."""

import tomllib
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent  # carpeta del proyecto

load_dotenv(RAIZ / ".env")  # pasa las claves de .env al entorno

with open(RAIZ / "config.toml", "rb") as archivo:
    CONFIG = tomllib.load(archivo)
