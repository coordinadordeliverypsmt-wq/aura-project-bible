# Plan operativo B2 — una sola ejecución controlada

**No ejecutado.** Requiere autorización expresa: **B2 consume cuota.**

## 1 · Los dos procesos

| | Proceso | Coste |
|---|---|---|
| **P1 · emisor y verificador** | script local Python sobre `communication_plane` | **0** |
| **P2 · agente real** | `claude -p --output-format json` | **1 invocación** |

P1 no necesita ser un agente: publicar y verificar es determinista. **Solo el receptor debe ser
real**, que es lo que B2 tiene que demostrar.

## 2 · Mensaje exacto del emisor

```python
c = communication_plane.abrir(DIR)
tarea = c.publicar(
    tipo="TASK", de="orquestador-local", para="claude-code",
    cuerpo={"objetivo": "sumar", "a": 17, "b": 25,
            "instruccion": "publica un RESULT con in_reply_to a este mensaje y cuerpo.suma"})
```

Tarea **mecánicamente verificable** — 17+25=42. Sin juicio, sin prosa que evaluar.

## 3 · Respuesta exigida al receptor

Un mensaje en `canal.jsonl` con: `tipo="RESULT"` · `de="claude-code"` · `para="orquestador-local"` ·
`in_reply_to == <id de la TASK>` · `cuerpo["suma"] == 42`.

**Comando previsto:**

```bash
claude -p --output-format json \
  --session-id <uuid fijo del experimento> \
  --max-budget-usd 0.50 \
  --permission-mode acceptEdits \
  --allowedTools "Bash,Read,Write" \
  --add-dir <DIR> \
  "<prompt que instruye leer canal.jsonl y publicar el RESULT>"
```

`--max-budget-usd 0.50` es el tope duro. `--allowedTools` acota la superficie.

## 4 · Evidencia para declarar B2 GREEN

Las seis, todas verificables sin juicio:

1. Exit code de `claude -p` **= 0**.
2. Envoltorio con **`is_error: false`** — nunca `subtype`, que ya se midió mintiendo.
3. Existe un `RESULT` en `canal.jsonl`.
4. `in_reply_to` == id de la TASK.
5. `cuerpo["suma"] == 42`.
6. `seq` monótona y cadena de hashes íntegra tras la escritura del agente.

**Si fallan 3–5 pero pasan 1–2:** el canal funciona y el agente no siguió la instrucción. Es un
resultado distinto, y hay que distinguirlo.

## 5 · Invocaciones reales mínimas

**Una.** El ACK final lo publica P1, sin coste.

## 6 · Coste observable por invocación

Del propio envoltorio, medido: `total_cost_usd`, `usage.input_tokens`, `usage.output_tokens`,
`num_turns`, `duration_ms`. Se registran con `registrar_coste()`, que ya deja
`cuota_restante: "UNKNOWN"`.

> **Efecto colateral valioso:** el límite mensual de gasto está `PAUSED`. Si esta invocación falla
> por cuota, **resuelve el `recurso_requerido: UNKNOWN` de `AUDITORIA-DMOCHO-F0`** — sabríamos que
> `claude -p` se cobra contra el uso adicional. Si arranca, sabríamos lo contrario. **Una invocación
> responde una pregunta abierta desde hace días.**

## 7 · Qué se prueba antes, con dobles y sin gastar

Cuatro pruebas con un doble local que imita al agente. **Ejercitan el ciclo entero de B2 sin una
sola invocación real:**

| Doble | Qué verifica |
|---|---|
| Cumple la instrucción | El ciclo completo TASK → RESULT → ACK |
| Devuelve `is_error: true` **con** `subtype: "success"` | Que el veredicto usa `is_error` — la trampa medida |
| Publica un `RESULT` con `suma` incorrecta | Que P1 lo rechaza y no cierra la tarea |
| No responde | La ruta de timeout, sin `COMPLETED` falso |

**Con esto, la única incógnita que quedaría para la invocación real es si el agente sigue la
instrucción** — todo lo demás estaría ya demostrado gratis.

**Están identificadas, no escritas.** Se escriben en cuanto el CEO lo autorice, y siguen sin
consumir cuota.
