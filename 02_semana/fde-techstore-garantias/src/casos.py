"""Las 5 consultas de la medicion (consigna PE2) y el estado correcto de cada una.

`esperado` es el "ground truth" que sirve para medir el KPI tecnico de PE1 (accuracy).
"""

CASOS = [
    # 1. Valida, bajo el umbral de supervisor
    ({"ticket_id": "TCK-1001", "mensaje_cliente": "Los auriculares dejaron de sonar del lado izquierdo a los 10 dias de recibirlos.",
      "dias_desde_entrega": 10, "monto_pagado_usd": 35.0, "tiene_factura_y_foto": True}, "elegible_borrador"),
    # 2. Valida, sobre el umbral: exige Supervisor N2
    ({"ticket_id": "TCK-1002", "mensaje_cliente": "El monitor llego con una linea de pixeles muertos en el centro de la pantalla.",
      "dias_desde_entrega": 15, "monto_pagado_usd": 240.0, "tiene_factura_y_foto": True}, "elegible_borrador"),
    # 3. Faltan datos obligatorios
    ({"ticket_id": "TCK-1003", "mensaje_cliente": "Quiero devolver el teclado mecanico que compre la semana pasada, no me gusto.",
      "dias_desde_entrega": 7, "monto_pagado_usd": 80.0, "tiene_factura_y_foto": False}, "faltan_datos"),
    # 4. Confusa / ambigua
    ({"ticket_id": "TCK-1004", "mensaje_cliente": "El cargador a veces carga y a veces no, creo que lo compre hace 4 meses pero tire la caja.",
      "dias_desde_entrega": 125, "monto_pagado_usd": 25.0, "tiene_factura_y_foto": False}, "requiere_revision_manual"),
    # 5. Fuera de tema
    ({"ticket_id": "TCK-1005", "mensaje_cliente": "Hola, me podrian pasar la receta para hacer pan casero o el horario del local?",
      "dias_desde_entrega": 0, "monto_pagado_usd": 10.0, "tiene_factura_y_foto": False}, "requiere_revision_manual"),
]
