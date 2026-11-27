---
titulo: Manual técnico del router FS-3000
roles: soporte, admin
version: 4.2
actualizado: 2025-09-15
---
# Manual técnico del router FS-3000

## 1. Alcance
Este manual aplica a los routers FS-3000 instalados en clientes de los planes Hogar, Pyme y Empresas. Lo usan los agentes de soporte de Nivel 1 y Nivel 2. Las versiones de firmware soportadas son 4.1.3 y 4.2.

## 2. Códigos de error

### ERR_9921_X - Pérdida de sincronización del firmware
Si el router muestra el error ERR_9921_X, reiniciá el equipo de forma remota desde la consola de gestión y actualizá el firmware a la versión 4.2. Si el error persiste después de dos reinicios en un lapso de 24 horas, escalá el caso a Nivel 2 con el número de serie y el log del equipo.
Excepción: en clientes del plan Empresas con SLA Oro no se puede reiniciar el equipo de forma remota en horario hábil (de 8 a 20 h) sin autorización escrita del contacto técnico del cliente. En ese caso, registrá la solicitud de autorización en el ticket antes de cualquier acción.

### ERR_9912_X - Falla de autenticación PPPoE
El error ERR_9912_X indica que el servidor rechazó las credenciales PPPoE. Verificá usuario y contraseña del cliente en el sistema de aprovisionamiento y forzá una resincronización de credenciales. Si el cliente tiene deuda mayor a 60 días, la autenticación queda bloqueada por diseño: derivá el caso a Cobranzas y no lo trates como falla técnica.

### ERR_9921_Y - Señal óptica fuera de rango
El error ERR_9921_Y aparece cuando la potencia óptica recibida está fuera del rango de -8 a -27 dBm. Las causas habituales son un conector de fibra sucio, un cable doblado o la fibra mal conectada a la ONT. Pedí al cliente que revise el cable sin desconectarlo. Si la potencia es menor a -27 dBm, generá una visita técnica: no es resoluble de forma remota.

### ERR_4410_Z - Sobretemperatura
El router se apaga solo para protegerse cuando supera los 70 grados. Indicá al cliente que lo ubique en un lugar ventilado y lejos de fuentes de calor. Tres apagados por sobretemperatura en una semana justifican el reemplazo del equipo.

## 3. Actualización de firmware
La actualización se hace desde la consola de gestión, en la pestaña Firmware, eligiendo la versión 4.2. El proceso tarda unos 6 minutos y el equipo se reinicia dos veces.
Excepción: no actualices el firmware si el cliente informa cortes de energía frecuentes o si el equipo está conectado a una UPS con batería menor al 20%; un corte durante la escritura puede dejar el equipo inutilizable. Si la actualización falla, hacé rollback a la versión 4.1.3.

## 4. Restablecimiento de fábrica
El restablecimiento de fábrica borra la configuración del cliente, incluidas las redes Wi-Fi personalizadas. Solo se hace con consentimiento explícito del titular de la cuenta y después de agotar los pasos de los códigos de error.
