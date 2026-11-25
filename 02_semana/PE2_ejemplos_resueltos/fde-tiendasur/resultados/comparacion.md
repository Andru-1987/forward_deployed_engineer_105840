| Proveedor | Modelo | Plan | Validadas | Tokens promedio (entrada / salida) | Costo USD promedio | Latencia ms promedio |
|---|---|---|---|---|---|---|
| google | gemini-3.5-flash-lite | gratis | 3 de 5 | 397 / 50 | 0.000244 | 1093 |
| groq | openai/gpt-oss-20b | gratis | 5 de 5 | 862 / 385 | 0.000279 | 894 |

Proveedor: google · modelo: gemini-3.5-flash-lite · plan: gratis

| # | Consulta | ¿Validó? | Categoría o error | Tokens (entrada / salida) | Costo USD | Latencia ms | Intentos |
|---|---|---|---|---|---|---|---|
| 1 | Caso típico | Sí | estado_pedido | 660 / 74 | 0.000383 | 1255 | 1 |
| 2 | Caso típico | Sí | cambio | 659 / 89 | 0.000420 | 1159 | 1 |
| 3 | Caso límite | Sí | devolucion | 665 / 86 | 0.000415 | 1100 | 1 |
| 4 | Confusa | No | API_ERROR | 0 / 0 | 0.000000 | 976 | 1 |
| 5 | Fuera de tema | No | API_ERROR | 0 / 0 | 0.000000 | 976 | 1 |
| | **Promedio** | | | 397 / 50 | 0.000244 | 1093 | |

- Consultas validadas: 3 de 5
- Meta de latencia (PE1): 5000 ms → cumple
- Meta de costo por consulta (PE1): 0.001 USD → cumple
- Plan gratuito: no pagás, pero el costo se calcula con la tarifa paga para que la medición sirva para decidir.

Proveedor: groq · modelo: openai/gpt-oss-20b · plan: gratis

| # | Consulta | ¿Validó? | Categoría o error | Tokens (entrada / salida) | Costo USD | Latencia ms | Intentos |
|---|---|---|---|---|---|---|---|
| 1 | Caso típico | Sí | estado_pedido | 694 / 178 | 0.000158 | 647 | 1 |
| 2 | Caso típico | Sí | cambio | 692 / 245 | 0.000192 | 576 | 1 |
| 3 | Caso límite | Sí | devolucion | 700 / 153 | 0.000147 | 670 | 1 |
| 4 | Confusa | Sí | otra | 688 / 377 | 0.000257 | 821 | 1 |
| 5 | Fuera de tema | Sí | otra | 1535 / 971 | 0.000639 | 1758 | 2 |
| | **Promedio** | | | 862 / 385 | 0.000279 | 894 | |

- Consultas validadas: 5 de 5
- Meta de latencia (PE1): 5000 ms → cumple
- Meta de costo por consulta (PE1): 0.001 USD → cumple
- Plan gratuito: no pagás, pero el costo se calcula con la tarifa paga para que la medición sirva para decidir.
