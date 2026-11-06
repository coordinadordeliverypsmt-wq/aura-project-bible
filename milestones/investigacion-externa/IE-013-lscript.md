---
id: IE-013
titulo: lscript — lanzador de menú para herramientas de Kali (solo ergonomía CLI)
fuente: https://github.com/arismelachroinos/lscript
rama-revision: master @ (último commit no visible; 308 commits; ARCHIVADO por el propietario el 2025-12-05)
fecha-revision: 2026-10-22
licencia: GPL-3.0
area: redes-seguridad
estado: descartado
cobertura: solo página principal del repositorio (estructura de ficheros y descripción del README resumida). No se leyó ningún script (`install.sh`, `l`, `lh*`, `ls/`). No se ejecutó nada.
relacionadas: [IE-012, IE-014]
---
## Qué se examinó (rutas y símbolos)
- Raíz: `README.md`, `LICENSE.md`, `Changelog`, `version.txt`, `install.sh`, `uninstall.sh`, `l` (entrada), `lh*`, `ls/`. [README]

## Patrones relevantes
- Un único comando corto de entrada con menú interactivo y comando `update` integrado. [README]
- Pares `install.sh`/`uninstall.sh` simétricos, `version.txt` y `Changelog` en la raíz. [README]
- Atajos de teclado configurables por el usuario para lanzar opciones. [README]
- Instalación pensada para ejecutarse como root sobre Kali. [README]

## Límites, riesgos y dependencias
- El propósito es automatizar herramientas ofensivas: **no se adopta nada ofensivo, ni se estudia su contenido.** [README]
- Archivado y sin mantenimiento: no recibirá correcciones. Modelo «instalar como root y autoactualizarse desde un repositorio remoto» es justo el riesgo de cadena de suministro que AURA debe evitar. [INFER]
- GPL-3.0: copiar código contaminaría la licencia de AURA; solo ideas.

## Comparación con AURA
- Instalación/retirada simétricas: ya cubierto — `entorno/nodos/instalar-hc1.sh`/`retirar-hc1.sh`, `instalar-runit-nodo.sh`/`retirar-nodo.sh`. [CÓDIGO]
- Versión y registro de cambios: ya existen `CHANGELOG.md` (desfasado según CLAUDE.md §5) y trazabilidad por commit. Brecha: ninguna nueva.
- Autoactualización remota: **contrario** a D24/local-first; AURA no debe tenerla.
- Menú interactivo: AURA se opera por Core/capacidades registradas, no por menú de herramientas.

## Decisión
- **Descartar.** Único patrón inocuo transferible, ya cubierto: instalación y retirada simétricas con comprobación posterior (`verificar-tras-reinicio-hc1.sh`).

## Validación mínima
- No aplica (nada se adopta).

## Licencia y precauciones
- GPL-3.0, repositorio archivado, contenido ofensivo. No clonar, no instalar, no ejecutar. Registrado explícitamente: **NO se adopta ninguna técnica, herramienta ni script ofensivo de este proyecto.**
