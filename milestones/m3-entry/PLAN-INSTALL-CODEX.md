# Preparación de instalación de Codex — `CODEX_INSTALL = READY_FOR_CEO_AUTHORIZATION`

**Nada instalado.** Todos los datos de abajo son `[EJEC]` por consulta al sistema y al registro npm,
sin ejecutar la instalación. `codex` sigue **AUSENTE**.

## 1 · Entorno verificado

| Dato | Valor `[EJEC 2026-08-18]` |
|---|---|
| SO | Linux Mint 22.3 · kernel 6.14.0-37 |
| Arquitectura | x86_64 |
| Node | v24.18.0 (vía nvm) |
| npm | 11.16.0 |
| Paquete Codex | **`@openai/codex`** · última versión **0.147.0**, disponible en el registro |
| Ejecutable que expone | `codex` → `bin/codex.js` |
| Engines requeridos | `node >=16` — **se cumple** (v24) |
| Espacio en `$HOME` | 8,1 GB libres (86 % usado) — suficiente |

## 2 · Comando exacto de instalación

```bash
npm install -g @openai/codex@0.147.0
```

Versión **fijada** a propósito: instalar `@latest` haría el resultado no reproducible. Si el CEO
prefiere la última en el momento de autorizar, se cambia a `@openai/codex` sin sufijo.

## 3 · Ubicación de instalación

| | |
|---|---|
| Módulo | `/home/majo1230/.nvm/versions/node/v24.18.0/lib/node_modules/@openai/codex/` |
| Ejecutable | `/home/majo1230/.nvm/versions/node/v24.18.0/bin/codex` |

Es el prefix de **nvm, dentro del home del usuario** — no una ruta de sistema.

## 4 · ¿Requiere sudo?

**No.** `[EJEC]` El directorio `…/v24.18.0/lib` es **escribible por el usuario** (nvm instala en el
home). La instalación **no requiere privilegios de administrador y no habrá prompt de contraseña**.

> Si por cualquier razón npm intentara escribir fuera del prefix de nvm, aparecería un `EACCES` y la
> intervención humana sería **volver a lanzar con permisos**, nunca introducir una contraseña dentro
> de esta sesión. **No se solicita, almacena ni infiere ninguna contraseña.**

## 5 · Verificación posterior (tras autorizar e instalar)

| Qué | Comando | Éxito |
|---|---|---|
| Instalado | `command -v codex` | imprime la ruta del bin |
| Versión | `codex --version` | número de versión |
| Ejecutable | `codex --help` | ayuda, exit 0 |
| **Autenticación** | `codex login status` *(nombre exacto por confirmar en `--help`)* | *authenticated* / *not logged in* |
| Tarea no destructiva | `codex --version` o `codex exec --help` | **sin invocar el modelo, coste 0** |

> **La comprobación de autenticación y la de «ejecutar una tarea» son distintas capacidades y
> distintos costes.** `--version`/`--help` son locales y gratis. Autenticarse (`codex login`) es una
> acción **interactiva del usuario** con el navegador. Ejecutar una tarea real (`codex exec` con
> prompt) **sí consume cuota** y **es B3, no esta fase.**

## 6 · Posibles estados tras instalar

| Estado | Firma |
|---|---|
| Instalado y ejecutable | `command -v codex` OK · `codex --version` OK |
| Instalado, no ejecutable | bin presente pero `codex --help` falla (dependencia, permiso) |
| Ejecutable, sin auth | `--help` OK pero `login status` → *not logged in* |
| Ejecutable y autenticado | listo para que B3 lo mida — **requiere `codex login`, acción humana** |

## 7 · Decisiones humanas que siguen faltando

| Id | Qué |
|---|---|
| **`D-CP-1.bis`** | Autorizar **ejecutar** el comando de §2. Todo lo demás ya está preparado |
| **`D-CP-1.ter`** | ToS de auth de suscripción en bucle `[INCIERTO]` — **independiente de instalar** |
| **Autenticación** | `codex login` es **interactivo y del usuario** (abre navegador). No lo puede hacer esta sesión |
| **Versión** | fijar `@0.147.0` o tomar `@latest` al autorizar |

**Instalar no es autenticar, y autenticar no es ejecutar.** Las tres son pasos separados, y solo el
primero queda cubierto por este plan.
