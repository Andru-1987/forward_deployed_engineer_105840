"""Unico entrypoint: corre las 5 consultas contra Groq y compara con la meta del KPI.

Uso:  cp .env.example .env  (completar GROQ_API_KEY)  ->  uv run python main.py
"""

import json
import logging

from groq import Groq

from src import CASOS, Secrets, cargar_config, procesar_ticket, resumir


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[LOG] %(message)s")
    config = cargar_config()
    cliente = Groq(api_key=Secrets().groq_api_key.get_secret_value())

    resultados = []
    for idx, (caso, _) in enumerate(CASOS, start=1):
        print(f"\n--- Consulta {idx} ({caso['ticket_id']}) ---")
        resultado = procesar_ticket(caso, cliente, config)
        resultados.append(resultado)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))

    print("\n=== Resumen vs KPI PE1 ===")
    print(json.dumps(resumir(resultados, [e for _, e in CASOS], config.kpi), indent=2))


if __name__ == "__main__":
    main()
