---
titulo: Protocolo de escalamiento de soporte técnico
roles: soporte, admin
version: 2.0
actualizado: 2025-06-01
---
# Protocolo de escalamiento de soporte técnico

## 1. Niveles de atención
Nivel 1 atiende el primer contacto por teléfono, chat y WhatsApp y resuelve problemas de configuración, credenciales y reinicios. Nivel 2 trata fallas de equipo, firmware y diagnóstico remoto avanzado. Nivel 3 es el equipo de red (NOC) y solo recibe incidentes de infraestructura.

## 2. Tiempos de resolución por plan (SLA)
Plan Hogar: 48 horas hábiles. Plan Pyme: 24 horas hábiles. Plan Empresas SLA Plata: 8 horas corridas. Plan Empresas SLA Oro: 4 horas corridas, todos los días del año.
Si un caso supera el 75% de su SLA sin resolución, el sistema lo marca en rojo y el supervisor de turno tiene que asignarlo personalmente.

## 3. Cuándo escalar a Nivel 2
Escalá a Nivel 2 cuando el error persiste después de los pasos del manual del equipo, cuando hace falta cambiar firmware en un plan Empresas o cuando el cliente reporta el mismo problema por tercera vez en 30 días.

## 4. Excepción: cortes masivos
Si más de 50 clientes del mismo nodo reportan falta de servicio en una ventana de 30 minutos, se trata como corte masivo. En ese caso NO se escala a Nivel 2: el agente abre directamente un incidente para el NOC (Nivel 3) y responde a los clientes con el mensaje de incidente general. No se generan visitas técnicas individuales mientras el incidente esté abierto.

## 5. Feriados y fines de semana
Los SLA en horas hábiles se congelan en feriados nacionales. Los SLA en horas corridas (Plata y Oro) no se congelan.
