# Contrato operativo · agente externo bajo demanda

> **Documento de gobernanza. No autoriza nada por sí mismo y no instala nada.**
> Redactado el 2026-08-25 al retirar OpenCode del entorno permanente.

## 1 · Quién es quién

| | |
|---|---|
| **Agente principal, permanente** | **Claude Code.** Ejecuta, decide técnicamente y responde del proyecto. |
| **Agente externo, bajo demanda** | **OpenCode.** Se invita, trabaja, entrega y **se retira**. No permanece instalado. |

**Ningún agente externo puede quedar instalado de forma permanente.** La instalación es parte de la
tarea y termina con ella.

## 2 · Cuándo procede invitar a un externo

Solo cuando `AGENTE_EXTERNO_REQUIRED` esté **explícitamente determinado y justificado**.

**Un fallo del agente principal NO es, por sí solo, motivo suficiente.** Que algo salga mal no
convierte automáticamente la situación en «hace falta otro agente»: casi siempre significa que hay
que corregir el trabajo, no cambiar de trabajador.

Razones que sí pueden sostenerlo, cada una verificable:

- **incapacidad técnica específica** del agente principal, demostrada, no supuesta;
- **segunda opinión independiente** cuando el propio implementador no puede auditarse
  —regla ya vigente: *el que implementa nunca audita su propio trabajo*—;
- **auditoría especializada** que exija un punto de vista que no comparta el contexto;
- **recuperación ante una incapacidad conocida** y registrada.

## 3 · Política de datos — la barrera que ninguna prisa levanta

> **«Gratis» NO significa «apto para AURA».** Lo demostró la evaluación del 2026-08-24/25.

Lo medido entonces, y que sigue vigente:

- los modelos free evaluados tuvieron **coste $0** y **Nemotron rindió bien** en fixtures sintéticos;
- **pero su política de datos los excluye**: OpenCode Zen declara que los `free` pueden usar las
  peticiones para mejorar los modelos, y **Nemotron dice literalmente** *«Trial use only — do not
  submit personal or confidential data»*;
- **Zen atiende sin credencial**, así que la barrera económica que dábamos por supuesta **no existe**.

**Ningún modelo evaluado queda marcado `AURA_APPROVED`.** Esa marca exige una decisión de gobernanza
expresa del CEO, y hasta que exista, **ningún externo recibe código confidencial de AURA** — solo
fixtures sintéticos.

## 4 · Procedimiento (conceptual — no implementado, no ejecutado)

`detectar necesidad` → `registrar motivo` → `verificar política de datos` → `verificar
proveedor/modelo` → `verificar permisos` → `crear entorno aislado` → **instalar temporalmente** →
`ejecutar UNA tarea` → `capturar evidencia` → `verificar resultado` → **desinstalar** →
`limpiar residuos` → `verificar que no quedan procesos` → `verificar espacio` → `registrar resultado`.

**Precondición del arnés:** el validador de comandos de `/tmp/opencode-hardening/validador.py` debe
estar activo. Sin él, la allow-list se evade encadenando comandos —medido: `python3 x && rm -rf y`
con `rm *` denegado—.

## 5 · Lo que un agente externo NO puede hacer, nunca

modificar `tareas_AUTO` · cambiar decisiones, ADRs o Decision Packages · alterar autoridad ·
saltarse zonas bloqueadas · recibir código confidencial de AURA · quedarse instalado.

## 6 · Y lo que DISCOVERY tampoco puede

**descubrir, clasificar y proponer: sí. Aprobar, promover o autorizar a un externo: no.**
La separación está probada por ejecución —`tareas_AUTO` comparada por igualdad exacta— y protegida
por 11 mutantes. **Invitar a un externo es una decisión del CEO, igual que promover una propuesta.**

## 7 · Lo que este documento NO es

No es un Orchestrator, ni un scheduler, ni un router de proveedores, ni una autorización automática.
Es **el contrato que habría que cumplir** el día que se invite a alguien. Hoy no hay nadie invitado.
