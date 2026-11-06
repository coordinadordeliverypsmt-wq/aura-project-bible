# Acta — Supervisión de NODO-01, construcción R1 (2026-10-18)

**Fuente:** orden ejecutiva 5.7.2 del CEO, recibida en sesión el 2026-10-18. Este documento **transcribe** la orden;
no añade alcance. Propuesta de referencia: `milestones/m3-entry/PROPUESTA-ACTA-SUPERVISION-NODO-01.md` (rev. 2).

**Autorizado (literal de la orden):** «Procede con la integración R1 de supervisión de NODO-01, limitada al centro de
notificaciones existente. Esta orden autoriza la implementación de R1 dentro de las decisiones e invariantes vigentes.»
Comprende: caída confirmada, recuperación durante la sesión, último estado en memoria de sesión, dedupe por
transiciones, distinción receptor indisponible / nodo caído / nodo nunca registrado, textos de la tabla del acta rev. 2,
Core sin sistema de ficheros (registro en el adaptador, puerto inyectado desde la composición).
Equivale a aprobar D1-D4 de la propuesta rev. 2 (apertura parcial y nominal de integración solo nodos → Centro).

**No autorizado (literal):** «ampliar D-M-8, modificar el esquema de registro.json, utilizar el audit log para eludir el
punto K, tocar el nodo físico ni realizar operaciones Git remotas». D5 (recuperación con AURA cerrado) **no** se aprueba.
Tampoco commit/push/merge ni despliegues.
