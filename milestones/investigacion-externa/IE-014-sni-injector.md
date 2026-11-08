---
id: IE-014
titulo: sni-injector — riesgos de proxies, SSH, SNI y validación de certificados (solo como contraejemplo)
fuente: https://github.com/miyurudassanayake/sni-injector
rama-revision: master @ (último commit no visible; 37 commits)
fecha-revision: 2026-10-22
licencia: no identificada en la página
area: redes-seguridad
estado: descartado
cobertura: solo página principal (descripción, ficheros `main.py`, `settings.ini`, `ssh.sh`, `requirements.txt`). No se leyó código ni se ejecutó. No es vía de control del hogar.
relacionadas: [IE-012, IE-013]
---
## Qué se examinó (rutas y símbolos)
- Raíz del repo y descripción: herramienta Python que usa un túnel SSH y cambia el nombre SNI para eludir restricciones de red. [README]
- En AURA: `aura_skeleton/nodo_agente.py:392-401` (`_fabrica_nats`), `entorno/nodos/red_hc1.py`, `tests/integration/test_red_hc1_pki.py`, `tests/unit/test_nodo_agente.py:484`, `aura_skeleton/adapters/red_local.py:84-86`. [CÓDIGO]

## Patrones relevantes (como riesgos, no como técnicas)
- Desactivar la comprobación de clave de host SSH elimina la protección ante un servidor suplantado. [README]
- Contraseñas en línea de comandos o ficheros de configuración filtran por historial, lista de procesos o copias. [README]
- Un relé remoto ve el tráfico de quien lo usa: la confianza se delega en su operador. [README]
- Que el nombre indicado y el certificado no coincidan hace fallar la verificación; saltársela anula la garantía de TLS. [README]
- Código de terceros no auditado ejecutado con privilegios de red. [INFER]

## Límites, riesgos y dependencias
- Finalidad (eludir controles de red) ajena a AURA; sin valor como funcionalidad. No se adopta. [INFER]

## Comparación con AURA (controles que debe mantener)
1. **No desactivar verificación de certificado.** `nodo_agente.py:397` pone `check_hostname = False` por diseño (la IP de HC-1 cambia por DHCP), pero mantiene `verify_mode = CERT_REQUIRED`, CA privada y `VERIFY_X509_STRICT`; el test `test_nodo_agente.py:484-510` fija `CERT_REQUIRED`. Ya cubierto, con matiz: el test comprueba el modo, no que un certificado de otra CA sea rechazado ni que un certificado válido para otro nodo sea aceptado. Riesgo residual [INFER]: sin comprobación de nombre, cualquier certificado firmado por la CA privada sirve para HC-1; la CA debe emitir solo certificados de servidor para HC-1 (`red_hc1.py`, `test_red_hc1_pki.py` verifica la PKI estricta; no se releyó para este informe). Control a mantener: la CA privada nunca firma certificados de servidor de otros usos. [CÓDIGO][INFER]
2. **Proxies explícitos, nunca heredados.** `red_local.py:84-86`: `ProxyHandler({})` evita que `http_proxy` del entorno desvíe peticiones; más sin redirecciones. Ya cubierto. Brecha: otros `urlopen` (`home_assistant_real.py:116`, `providers_real.py:139,200`, marcados S310 por ruff) no se han comprobado frente al mismo riesgo de proxy del entorno. [EJEC][INFER]
3. **Búsqueda de desactivaciones**: `grep -rn "check_hostname\|CERT_NONE\|verify=False\|StrictHostKey"` sobre `aura_skeleton` y `entorno` dio una sola coincidencia (la anterior). No hay `CERT_NONE`, `verify=False` ni `StrictHostKeyChecking=no`. [EJEC]
4. **Secretos fuera de argv y config en claro**: el agente recibe la contraseña NATS (`_fabrica_nats(config, password…)`); queda por confirmar de dónde procede (no se verificó). [INFER]
5. **Túneles/relés externos**: AURA no debe enrutar tráfico del hogar a relés de terceros (D24; `orquestacion-herramientas.md` ya lo prohíbe para OmniRoute). [CÓDIGO]

## Decisión
- **Descartar** como fuente de código. **Adaptar** únicamente como lista de comprobación de controles (ver arriba). Investigar más: ítems 2 y 4.

## Validación mínima
- [PROPUESTA] Prueba de contrato (sin red): un test que recorra `aura_skeleton` y `entorno` y falle si aparece `CERT_NONE`, `verify=False`, `StrictHostKeyChecking=no` o `check_hostname = False` fuera de `nodo_agente.py`; caso de control: la propia línea 397 debe estar en la lista permitida con justificación. Es una prueba estática, no ejecuta red.

## Licencia y precauciones
- Licencia no confirmada; no se copia nada. Sin clonar, sin instalar, sin ejecutar. No es vía de control del hogar. Describe solo riesgos y mitigaciones; no se reproduce ninguna técnica de elusión.
