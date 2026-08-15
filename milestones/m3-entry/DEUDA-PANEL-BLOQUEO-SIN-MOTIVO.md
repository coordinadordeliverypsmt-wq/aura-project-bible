# Deuda — el panel revienta ante una tarea bloqueada sin motivo registrado

**Registrada:** 2026-08-10 · **Origen:** prueba del incremento «buzón visible»
**Estado:** deuda declarada **fuera de alcance** por decisión del CEO. **No corregir ahora.**

---

## Qué ocurre

`Seccion.__post_init__` exige que una sección con origen declarado traiga contenido. `_bloqueos()`
devuelve cadena vacía cuando una tarea bloqueada no tiene nada en `bloqueos`, así que la sección
«Que esta bloqueado» se construye vacía y `panel()` lanza:

```
ValueError: 'Que esta bloqueado': una seccion con origen declarado debe traer contenido
```

**No es alcanzable en producción hoy**: el director siempre transita a `bloqueada` pasando
`bloqueos=[...]` junto a la causa. Se destapó al escribir una prueba que usaba `transitar` con
`causa` sola.

## Por qué importa igualmente

El fallo no está en quien bloquea, sino en que **el panel no tolera un dato incompleto**. La interfaz
oficial del CEO revienta entera por una tarea mal formada, en vez de declarar la ausencia — que es
justo lo que el módulo predica: *«prefiero una ausencia declarada a una capacidad simulada»*.

Cualquier ruta futura que bloquee una tarea sin motivo —una migración, un almacén editado a mano, un
componente nuevo— tumbaría `--gobierno`.

## Condición que la promovería a trabajo

Si aparece una segunda ruta que transite a `bloqueada` sin `bloqueos`, o si `--gobierno` falla alguna
vez en uso real. Mientras el director sea el único que bloquea, no hay evidencia de que ocurra.

**No se abre trabajo por anticipado** (regla del CEO, 2026-08-04: el desarrollo lo guía la evidencia
del uso real).
