"""Cómo hablar con cada proveedor: OpenAI, Anthropic, Google (Gemini) y Groq.

El motor no sabe qué proveedor usa: siempre llama a llamar_modelo() y recibe lo mismo,
(texto, tokens_entrada, tokens_salida). Para sumar un proveedor nuevo, agregás una
función _llamar_<nombre>() y una sección [proveedores.<nombre>] en config.toml.
"""

import os

from anthropic import Anthropic
from google import genai
from google.genai import types
from groq import Groq
from openai import OpenAI

from configuracion import CONFIG

PROVEEDORES = ("openai", "anthropic", "google", "groq")
TIMEOUT = CONFIG["motor"]["timeout_segundos"]


# --- Qué proveedor usar y con qué datos ---------------------------------------
def proveedor_activo(nombre: str | None = None) -> str:
    """Prioridad: el que pasás al correr > la variable PROVEEDOR > config.toml."""
    return (nombre or os.getenv("PROVEEDOR") or CONFIG["proveedor"]).strip().lower()


def datos_proveedor(nombre: str) -> dict:
    """La sección [proveedores.<nombre>] de config.toml: modelo, clave, plan y precios."""
    return CONFIG["proveedores"][nombre]


def falta_clave(nombre: str) -> str | None:
    """Devuelve el nombre de la variable si la clave no está en .env; si está, None."""
    variable = datos_proveedor(nombre)["variable_clave"]
    return None if os.getenv(variable) else variable


# --- La única función que usa el motor ----------------------------------------
def llamar_modelo(sistema: str, mensajes: list[dict], proveedor: str) -> tuple[str, int, int]:
    """Manda el prompt al proveedor elegido y devuelve (texto, tokens_entrada, tokens_salida).

    mensajes usa el formato de OpenAI: [{"role": "user" o "assistant", "content": "..."}].
    """
    datos = datos_proveedor(proveedor)
    if proveedor == "openai":
        return _llamar_openai(datos, sistema, mensajes)
    if proveedor == "anthropic":
        return _llamar_anthropic(datos, sistema, mensajes)
    if proveedor == "google":
        return _llamar_google(datos, sistema, mensajes)
    if proveedor == "groq":
        return _llamar_groq(datos, sistema, mensajes)
    raise ValueError(f"Proveedor desconocido: {proveedor}")


# --- Un adaptador por proveedor ----------------------------------------------------
def _llamar_openai(datos, sistema, mensajes):
    cliente = OpenAI(timeout=TIMEOUT)  # lee OPENAI_API_KEY
    respuesta = cliente.chat.completions.create(
        model=datos["modelo"],
        messages=[{"role": "system", "content": sistema}, *mensajes],
        response_format={"type": "json_object"},  # pide JSON válido
    )
    uso = respuesta.usage
    return respuesta.choices[0].message.content or "", uso.prompt_tokens, uso.completion_tokens


def _llamar_groq(datos, sistema, mensajes):
    # Groq usa el mismo formato que OpenAI: solo cambian el cliente y el modelo.
    cliente = Groq(timeout=TIMEOUT)  # lee GROQ_API_KEY
    respuesta = cliente.chat.completions.create(
        model=datos["modelo"],
        messages=[{"role": "system", "content": sistema}, *mensajes],
        response_format={"type": "json_object"},
    )
    uso = respuesta.usage
    return respuesta.choices[0].message.content or "", uso.prompt_tokens, uso.completion_tokens


def _llamar_anthropic(datos, sistema, mensajes):
    cliente = Anthropic(timeout=TIMEOUT)  # lee ANTHROPIC_API_KEY
    respuesta = cliente.messages.create(
        model=datos["modelo"],
        max_tokens=CONFIG["motor"]["max_tokens"],  # obligatorio en Anthropic
        system=sistema,  # el prompt de sistema va aparte
        messages=mensajes,
    )
    texto = "".join(b.text for b in respuesta.content if b.type == "text")
    return texto, respuesta.usage.input_tokens, respuesta.usage.output_tokens


def a_formato_google(mensajes: list[dict]) -> list[dict]:
    """Google llama "model" al asistente y pone el texto dentro de "parts"."""
    return [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in mensajes
    ]


def _llamar_google(datos, sistema, mensajes):
    cliente = genai.Client(http_options={"timeout": TIMEOUT * 1000})  # lee GEMINI_API_KEY; ms
    respuesta = cliente.models.generate_content(
        model=datos["modelo"],
        contents=a_formato_google(mensajes),
        config=types.GenerateContentConfig(
            system_instruction=sistema,
            response_mime_type="application/json",  # pide JSON válido
        ),
    )
    uso = respuesta.usage_metadata
    # Si el modelo "piensa" antes de responder, esos tokens también se cobran como salida.
    tokens_salida = (uso.candidates_token_count or 0) + (uso.thoughts_token_count or 0)
    return respuesta.text or "", uso.prompt_token_count or 0, tokens_salida


# --- Errores de API: cada SDK los llama distinto, el motor los agrupa en 4 --------
def clasificar_error(error: Exception) -> tuple[str, str]:
    """Traduce el error de cualquier SDK a una etapa del motor y a un mensaje claro."""
    nombre = type(error).__name__
    codigo = getattr(error, "status_code", None) or getattr(error, "code", None)
    detalle = str(error)

    if codigo in (401, 403) or "Authentication" in nombre or "API_KEY_INVALID" in detalle:
        return "CONFIGURACION", "la clave es inválida, fue revocada o no tiene permiso"
    if codigo == 429 or "RateLimit" in nombre:
        return "API_LIMITE", "llegaste al límite de uso del plan o se agotó el crédito (429)"
    if "Connect" in nombre or "Timeout" in nombre:
        return "API_CONEXION", "sin conexión o el modelo tardó demasiado"
    return "API_ERROR", f"{nombre}: {detalle[:300]}"
