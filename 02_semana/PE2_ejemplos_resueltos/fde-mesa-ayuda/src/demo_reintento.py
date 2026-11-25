"""Muestra el manejo de errores sin API key, con un modelo simulado.

Correlo con:  uv run python src/demo_reintento.py

Caso A: el modelo rompe una regla de negocio, el motor la registra, reintenta y se corrige.
Caso B: el modelo responde mal dos veces y el motor devuelve un error estructurado.
"""

import json

from modelo_simulado import ModeloSimulado
from motor import procesar

# Prioridad alta sin escalar: rompe la regla de negocio del contrato.
MAL = ('{"tipo": "red", "prioridad": "alta", "resumen": "Se cayó el wifi del piso 3", '
       '"pasos_sugeridos": ["Reiniciar el access point del piso 3"], '
       '"escalar_a_n2": false, "confianza": 0.8}')
BIEN = MAL.replace('"escalar_a_n2": false', '"escalar_a_n2": true')
PEDIDO = {"legajo": "EMP-0315", "mensaje": "Nadie del piso 3 tiene wifi desde las 9."}

print("== Caso A: falla el primer intento y el reintento lo corrige ==")
print(json.dumps(procesar(PEDIDO, llamar=ModeloSimulado([MAL, BIEN])),
                 ensure_ascii=False, indent=2))

print("\n== Caso B: falla dos veces y devuelve un error estructurado ==")
print(json.dumps(procesar(PEDIDO, llamar=ModeloSimulado([MAL, MAL])),
                 ensure_ascii=False, indent=2))
