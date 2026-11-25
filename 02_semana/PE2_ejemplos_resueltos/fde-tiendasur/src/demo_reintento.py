"""Muestra el manejo de errores sin API key, con un modelo simulado.

Correlo con:  uv run python src/demo_reintento.py

Caso A: el modelo responde mal, el motor registra el campo, reintenta y se corrige.
Caso B: el modelo responde mal dos veces y el motor devuelve un error estructurado.
"""

import json

from modelo_simulado import ModeloSimulado
from motor import procesar

MAL = '{"categoria": "reclamo", "respuesta_sugerida": "Ok", "requiere_humano": false, "confianza": 1.4}'
BIEN = ('{"categoria": "estado_pedido", "respuesta_sugerida": "¡Hola! Ya estamos '
        'revisando tu pedido PED-10234 y en breve te contamos dónde está.", '
        '"requiere_humano": false, "confianza": 0.85}')
CONSULTA = {"consulta": "¿Dónde está mi pedido? Ya pasó una semana.", "id_pedido": "PED-10234"}

print("== Caso A: falla el primer intento y el reintento lo corrige ==")
print(json.dumps(procesar(CONSULTA, llamar=ModeloSimulado([MAL, BIEN])),
                 ensure_ascii=False, indent=2))

print("\n== Caso B: falla dos veces y devuelve un error estructurado ==")
print(json.dumps(procesar(CONSULTA, llamar=ModeloSimulado([MAL, MAL])),
                 ensure_ascii=False, indent=2))
