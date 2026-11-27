"""Entrypoint: runs 3 sample queries.

Usage: cp .env.example .env (set GROQ_API_KEY) -> uv run python main.py
"""

import json

from groq import Groq

from src import Secrets, cargar_config, ejecutar_turno, elegir_version

CONSULTAS = [
    ("user-001", "Quiero un reembolso parcial de 150 dolares por un cobro duplicado en el ticket TKT-482910."),
    ("user-002", "En que estado esta mi ticket TKT-123456?"),
    ("user-003", "Cual es la mejor receta de milanesas?"),
]


def main() -> None:
    config = cargar_config()
    cliente = Groq(api_key=Secrets().groq_api_key.get_secret_value())

    for user_id, consulta in CONSULTAS:
        version = elegir_version(user_id, config.rollout.porcentaje_canary)
        ruta = config.rollout.prompt_canary if version == "v2" else config.rollout.prompt_estable
        resultado = ejecutar_turno(consulta, cliente, config, ruta)
        print(f"[{version}] {consulta}")
        print(json.dumps(resultado, indent=2, ensure_ascii=False), "\n")


if __name__ == "__main__":
    main()
