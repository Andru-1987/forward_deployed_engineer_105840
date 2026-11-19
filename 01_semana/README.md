# Pre-Entrega 1: Relevamiento y Diseño del Caso

* **Estudiante:** [Apellido, Nombre]
* **Proyecto:** Asistente de Triaje y Resolución de Garantías/Devoluciones
* **Archivo:** `FDE_PE1_Apellido_Nombre.pdf`

---

## 1. El Caso

### Descripción del Proceso y Contexto
* **Empresa/Negocio:** Tienda online de electrónica y accesorios (*TechStore*, operación mediana con ~1.200 pedidos mensuales).
* **Proceso seleccionado:** Recepción, verificación de elegibilidad y carga de resoluciones para solicitudes de devolución o garantía post-venta.
* **Ejecutor actual:** Analista de Atención al Cliente (Soporte Nivel 1). Hoy recibe correos/tickets, revisa manualmente la fecha de compra en el sistema ERP/CRM, lee el PDF de políticas de garantía según la marca y redacta la resolución o genera el cupón de cambio.

### Cumplimiento de los 7 Requisitos del Caso Viable
1. **Proceso repetitivo y manual:** El analista procesa entre 15 y 25 reclamos diarios siguiendo exactamente los mismos pasos de verificación documental y carga de datos.
2. **Acceso a entrevistas:** Se cuenta con acceso directo a **[Nombre/Iniciales]**, Analista de Soporte Post-Venta, quien ejecuta este flujo diariamente.
3. **Documentación consultable:** Existen 3 documentos internos vigentes: *Política General de Devoluciones (PDF)*, *Tabla de Garantías por Marca (Excel/PDF)* y *Manual de Uso del CRM*.
4. **Acción sobre sistema con aprobación humana:** El asistente propondrá la resolución y preparará el borrador de la *"Orden de Devolución / Nota de Crédito"* en el CRM, pero no impactará el saldo hasta que el Supervisor o Analista haga clic en **Aprobar**.
   * **Multiplicidad de roles:**
     * **Rol Analista (N1):** Consulta políticas, genera borradores de resolución y aprueba devoluciones menores a $50 USD.
     * **Rol Supervisor (N2):** Acceso total, auditoría de historial y aprobación obligatoria para montos mayores a $50 USD o excepciones.
5. **Medibilidad actual:** El CRM registra la hora de apertura y cierre de cada ticket (tiempo promedio actual: **18 minutos por caso**) y las notas de crédito rechazadas por error de cálculo.
6. **Privacidad de datos:** Se utilizará un entorno de pruebas (*sandbox*) del CRM con 50 tickets históricos anonimizados (reemplazando DNI, nombres reales y correos por IDs ficticios).

---

## 2. Relevamiento

### Identificación del Entrevistado
* **Rol:** Analista Senior de Soporte Post-Venta (2 años de antigüedad en el puesto).
* **Modalidad:** Entrevista estructurada de 30 minutos + observación de resolución de 3 tickets en vivo.

### Hallazgos Clave de la Entrevista
1. **Dispersión documental:** El analista pierde casi la mitad del tiempo buscando si una falla específica está cubierta por la garantía oficial de la marca o por la garantía de la tienda.
2. **Errores de cálculo en reembolsos:** Cuando la compra tuvo descuentos o envío gratuito, suelen cometerse errores al calcular el monto exacto a reintegrar, lo que genera re-trabajo con el área contable.
3. **Consultas repetitivas sin contexto:** El 60% de los tickets ingresan sin número de factura o foto del producto, obligando a un intercambio de 2 o 3 correos previos antes de poder evaluar el caso.

### Mapa del Proceso Actual (AS-IS)
1. El cliente envía un correo/ticket reportando una falla o solicitando devolución.
2. El Analista abre el ticket y busca manualmente el pedido en el CRM por correo o DNI.
3. Verifica si el pedido está dentro de los 30 días de compra o período de garantía.
4. Abre la carpeta compartida y consulta el PDF de *Políticas por Marca* para validar si la falla aplica.
5. Si falta información (foto o factura), responde al cliente y deja el ticket en estado **Pendiente**.
6. Si aplica, calcula manualmente el monto a devolver (restando envíos o descuentos aplicados).
7. Carga la solicitud de Nota de Crédito en el módulo de facturación del CRM.
8. Envía correo de confirmación al cliente con los pasos de envío del producto.

### Cuello de Botella Principal (Dato Empírico)
* **Etapa:** Pasos 3, 4 y 6 (Validación cruzada entre historial del CRM, manuales PDF de marcas y cálculo de reintegro).
* **Evidencia cuantitativa:** Según el registro de tiempos medido sobre una muestra de 30 tickets de la última semana, el proceso completo toma **18 minutos en promedio**, de los cuales **11 minutos (61% del tiempo total)** se consumen únicamente leyendo los PDFs de políticas por marca y verificando condiciones de compra antes de cargar la resolución.

---

## 3. Historias de Usuario

### Historia de Usuario 1 (Triaje y Validación Documental)
> *"Como Analista de Soporte Post-Venta, quiero que el asistente analice el ticket del cliente cruzando los datos del pedido con las políticas de garantía vigentes, para obtener un dictamen preliminar de elegibilidad sin buscar manualmente en los PDFs."*

**Criterios de Aceptación:**
1. ¿El sistema identifica automáticamente si el pedido está dentro del plazo vigente según la fecha de entrega registrada? `(Sí / No)`
2. ¿La respuesta del asistente cita exactamente el artículo o cláusula del documento de políticas que justifica si el caso aplica o no? `(Sí / No)`
3. ¿Si faltan datos obligatorios (ej. foto del daño), el asistente redacta automáticamente el mensaje solicitando exclusivamente los datos faltantes? `(Sí / No)`

### Historia de Usuario 2 (Acción en Sistema con Human-in-the-Loop)
> *"Como Supervisor de Post-Venta, quiero revisar y aprobar con un clic el borrador de Nota de Crédito generado por el asistente en el CRM, para evitar errores de cálculo financiero y mantener el control sobre las salidas de dinero."*

**Criterios de Aceptación:**
1. ¿El asistente deja cargada la solicitud de Nota de Crédito en estado *"Borrador / Pendiente de Aprobación"* sin emitir el comprobante fiscal? `(Sí / No)`
2. ¿El sistema bloquea la auto-aprobación si el usuario logueado tiene rol de Analista N1 y el monto supera el umbral configurado? `(Sí / No)`
3. ¿El borrador muestra desglosado el cálculo del monto (subtotal producto menos descuentos/envío) antes de confirmar la acción? `(Sí / No)`

---

## 4. Medición y KPIs

| Tipo | Nombre del KPI | Unidad de Medida | Valor Actual (Baseline) | Meta Propuesta (Semana 10) | Método Exacto de Medición |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Negocio** | Tiempo promedio de resolución por ticket (AHT) | Minutos por ticket | 18 min | ≤ 7 min (-61%) | Diferencia de timestamps (`hora_cierre - hora_apertura`) exportada del log del CRM sobre una muestra de 40 tickets. |
| **Técnico** | Precisión en el dictamen de elegibilidad y cálculo (Accuracy) | Porcentaje (%) | 82% (18% con error de cálculo/política) | ≥ 95% | Evaluación humana (*ground truth*) comparando el dictamen y monto sugerido por la IA contra la resolución correcta sobre un dataset de 50 casos de prueba. |

---

## 5. Alcance y Riesgos

### Riesgos y Estrategias de Mitigación
1. **Riesgo de alucinación en políticas de garantía:** Que el modelo invente una cobertura no contemplada en el manual de la marca.
   * **Mitigación:** Implementar RAG estricto con instrucción de respuesta cerrada (*"Si no consta en el documento, responder 'Requiere revisión manual'"*) y obligatoriedad de citar fuente.
2. **Fuga de datos personales (PII) hacia el LLM:** Envío de nombres, direcciones o tarjetas de clientes reales en los prompts.
   * **Mitigación:** Capa intermedia de anonimización (enmascaramiento de nombres/DNI por tokens) antes de enviar el texto al modelo, y uso exclusivo de dataset sintético durante el desarrollo.
3. **Aprobación automática por fatiga del operador (Sesgo de automatización):** Que el supervisor apruebe borradores sin leerlos.
   * **Mitigación:** Mostrar en la interfaz de aprobación únicamente los 3 datos críticos resaltados (Motivo, Cláusula y Monto) y exigir confirmación explícita cuando el monto supere el umbral de riesgo.

### Matriz de Valor vs. Viabilidad (Selección de Alternativa)

| Alternativa Evaluada | Valor de Negocio (1-5) | Viabilidad Técnica en 10 Semanas (1-5) | Puntaje Total | Análisis y Decisión |
| :--- | :---: | :---: | :---: | :--- |
| **Alt. 1: Chatbot autónomo de cara al cliente** (resuelve y emite reembolso sin intervención humana) | 5 | 2 | **7/10** | **Descartada:** Alto riesgo financiero y reputacional ante errores; incumple el requisito de aprobación humana. |
| **Alt. 2: Buscador semántico pasivo (Solo RAG)** (el analista pregunta dudas sobre los PDFs, pero carga todo a mano en el CRM) | 3 | 5 | **8/10** | **Descartada:** Muy fácil de construir, pero solo resuelve la lectura de PDFs y no elimina los errores de carga ni el tiempo en el CRM. |
| **Alt. 3: Copiloto interno con RAG + Borrador de Acción en CRM (HITL)** | 5 | 4 | **9/10** | **SELECCIONADA:** Maximiza el ahorro de tiempo (lee políticas + pre-carga el ticket), mantiene control humano total y es 100% ejecutable en 10 semanas. |
