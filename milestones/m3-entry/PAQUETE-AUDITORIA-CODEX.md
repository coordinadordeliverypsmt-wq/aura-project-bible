# Paquete de auditoría Codex — diseño mínimo y reproducible

> **DOCUMENTO DE DISEÑO. No implementado, no ejecutado, no consume cuota.**
> Redactado el 2026-08-24 tras la FASE 8, en la que la primera auditoría real con Codex quedó
> **incompleta por agotamiento de cuota** (*«usage limit… try again at Sep 22nd, 2026»*).
> Su propósito es que, cuando haya cuota, **una sola ejecución** baste.

## 1 · Qué falló en el intento del 2026-08-24

Tres cosas medidas, no supuestas:

| Observado | Consecuencia |
|---|---|
| Codex empezó por `rg --files` y **leyó el repositorio entero** antes de auditar nada | Gastó contexto en descubrir lo que podíamos haberle dado hecho |
| Ejecutó la batería completa **desde cero**, incluidas RED que invocan Codex real | Recursión implícita y gasto duplicado |
| Se quedó sin cuota **antes de emitir veredicto** | Trabajo real hecho, conclusión perdida |

**Lección:** el paquete debe entregar a Codex **el trabajo ya hecho** para que lo *verifique*,
no un repositorio para que lo *descubra*. Auditar es refutar, y refutar necesita el resultado
delante, no el material en bruto.

## 2 · Estructura del paquete

```
/tmp/codex-mvp/paquete-<fecha>/          ← repo git sintético, root commit ≠ AURA
├── INDICE.md          ← qué hay, qué se afirma, qué debe refutarse. Se lee PRIMERO.
├── encargo.txt        ← preguntas de auditoría. Nunca conclusiones a confirmar.
├── artefactos/        ← delegar.sh · mutantes.def · bateria_mutacion.sh · test_red_*.sh · metared/
├── resultados/        ← salida YA EJECUTADA por Claude: batería, regresión, bash -n, sha256
└── RESPUESTA.md       ← plantilla que Codex rellena. Formato fijo = incorporación mecánica.
```

**Qué NO entra, y por qué:** `aura_skeleton/`, `docs/`, `adr/`, `decisiones/`,
`entorno/control-plane/` completo. El fixture no puede exponer fuentes de verdad de AURA, y el
wrapper rechaza por diseño cualquier objetivo que las contenga. Del Control Plane solo viaja un
**extracto** con las claves del MVP.

## 3 · `INDICE.md` — el que ahorra la relectura

Es el corazón del ahorro. Contiene, precomputado:

- **inventario de los 18 mutantes**: id · garantía · transformación · RED · veredicto declarado;
- **hash del diff** de cada mutante, para que Codex compruebe equivalencias sin recalcularlas;
- **resultado de la última batería** con su `RUN_ID` y la ruta de la evidencia;
- **sha256 de `delegar.sh`** y de cada RED;
- **las tres reglas metodológicas vigentes** (validez del mutante, anti-enmascaramiento, E1+E2+E3);
- **la lista explícita de lo que NO debe ejecutarse** y por qué.

## 4 · Qué RED debe ejecutar Codex, y cuáles no

| Grupo | Ejecutar | Motivo |
|---|---|---|
| RED con doble o centinela (13) | **Sí** | Deterministas, sin coste, sin red |
| Meta-RED de clasificación | **Sí** | Determinista por construcción desde FASE 8 |
| `test_red_señales_reales`, `test_red_m17_exit_con_thread`, `test_red_fallo_real` | **No** | Invocan Codex real: dentro de una sesión de Codex son recursión y gasto duplicado |

Para ese último grupo, el paquete entrega la **evidencia ya capturada** (`events.jsonl`,
`manifest.json`, `stderr.txt` de ejecuciones reales) para que Codex **audite la evidencia**
en vez de regenerarla. Es la diferencia entre pedirle que repita el experimento y pedirle que
revise el cuaderno de laboratorio.

## 5 · `RESPUESTA.md` — formato fijo

Que Codex escriba en un formato conocido convierte la incorporación en mecánica y elimina el
riesgo de que Claude interprete su prosa. Campos: `VEREDICTO` (PASS/FAIL) · `GRAVES[]` ·
`MENORES[]` · `NO_VERIFICADO[]` · `FALSOS_POSITIVOS_PROPIOS[]`, cada hallazgo con
`fichero:línea` y **cómo reproducirlo**.

El último campo no es cortesía: en la FASE 8 **dos de los hallazgos de Codex eran falsos
positivos suyos** —una línea condicional que leyó como incondicional, y tres invocaciones que sí
tenían centinela—. Pedirle que se autoevalúe reduce el trabajo de descarte.

## 6 · Presupuesto

**Una invocación.** Si no alcanza, el paquete está mal dimensionado y se corrige el paquete, no se
gasta una segunda. Contexto estimado del intento anterior: **~29 000 tokens** de entrada.

## 7 · Qué queda fuera de esto

Este paquete **no es el orquestador** y no debe crecer hacia él. Es un sobre: material dentro,
preguntas dentro, respuesta fuera. Quien decide qué se hace con la respuesta sigue siendo el CEO,
y quien la incorpora, Claude.
