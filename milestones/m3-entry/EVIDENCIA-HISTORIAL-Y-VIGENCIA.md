# Evidencia — historial y vigencia de hechos declarados (AMP-AURA etapas 1–2)

**Decisión que lo autoriza:** `D-AMP-1 = B` (CEO, 2026-09-10). Cuatro campos y ni uno más:
`version`, `supersedes`, `valid_from`, `valid_until`.
**Punto de retorno:** checkpoint `5ebdce4`. **Estado:** sin commit, sin push, `PARADA` armada.

---

## 1 · El defecto, medido ANTES de tocar código `[EJEC]`

Se declaró «Mi cumpleaños es el 10 de mayo» y después «Mi cumpleaños es el 3 de junio». En el almacén
quedaron **dos entradas indistinguibles y las dos igual de vivas**:

```
{"content": "Mi cumpleaños es el 10 de mayo", "provenance": {"trace_id":…,"clase":"hecho_declarado",…}}
{"content": "Mi cumpleaños es el 3 de junio",  "provenance": {"trace_id":…,"clase":"hecho_declarado",…}}
¿hay version/supersedes/valid_from/valid_until? False
```

La consulta **acertaba** —respondía «3 de junio»— pero por un `reversed()` en la lectura: acertaba por
el **orden de llegada**, no porque el sistema supiera cuál estaba vigente. Un inspector que leyera el
almacén no podía decir cuál era el cumpleaños del usuario, ni desde cuándo, ni que una sustituía a la
otra. **Acertar no es saberlo**, y esa diferencia es justo lo que esta etapa cierra.

## 2 · El mismo caso, después `[EJEC]`

Reproducible con:

```bash
cd walking-skeleton && PYTHONPATH=. python3 ../milestones/m3-entry/evidencia-amp/verificar_historial_vigencia.py
```

Se ejecuta el **producto real** —orquestador, motor único, ejecutor del modelo de usuario y almacén—.
El único doble es el proveedor de modelo, y está ahí **para contar**: si responde una sola vez, la
autoridad se le habría delegado y la demostración falla (ADR-0014).

```
--- LO QUE QUEDA EN EL ALMACEN (crudo, como lo leeria un inspector):
{"content": "Mi cumpleaños es el 10 de mayo", "provenance": {…, "ts": 1000.0,
   "version": 1, "supersedes": null, "valid_from": 1000.0, "valid_until": 2000.0}}
{"content": "Mi cumpleaños es el 3 de junio",  "provenance": {…, "ts": 2000.0,
   "version": 2, "supersedes": 1,    "valid_from": 2000.0, "valid_until": null}}

--- LO QUE EL USUARIO PUEDE VER DE SU PROPIO HISTORIAL (`ver`):
    v1  supersedes=None  [1000.0 → 2000.0]  superseded en 2000.0
        'Mi cumpleaños es el 10 de mayo'
    v2  supersedes=1     [2000.0 → None]    VIGENTE
        'Mi cumpleaños es el 3 de junio'

>>> El usuario pregunta: '¿Cuál es mi cumpleaños?'
    AURA responde: 'Tu cumpleaños es 3 de junio.'
    proveedor=core  dominio=modelo_usuario  latencia=0.94 ms
    LLAMADAS AL MODELO durante la consulta: 0

VEREDICTO: PASS — historial conservado, una sola version vigente, 0 llamadas al LLM
```

Traza de auditoría de la supersession, emitida dentro del motor único `[EJEC]`:

```
[AUDIT]  permissions       soberania registrar_informacion_usuario -> sin HITL (§4.3)
[MODELO] ejecutor-modelo   registrada sobre 'mauricio': 'Mi cumpleaños es el 10 de mayo' v1
[MODELO] ejecutor-modelo   'cumpleanos' v1: 1 entrada(s) superseded, vigencia cerrada en 2000.0
[MODELO] ejecutor-modelo   registrada sobre 'mauricio': 'Mi cumpleaños es el 3 de junio' v2
[CORE ]  routing           dominio=modelo_usuario
[LAT  ]  orchestrator      latencia total 1.3 ms (proveedor=core)
```

## 3 · Por qué el versionado vive donde vive

| Candidato | Veredicto |
|---|---|
| `AlmacenSenales` | **No.** Su contrato dice «no lee, no infiere, no decide», y versionar exige **leer** el historial para saber qué versión toca y cuál cerrar |
| `ModeloUsuario` | **No.** Mutaría el almacén fuera del motor — el agujero de `ALERTA-006`, ya cerrado |
| **`EjecutorModeloUsuario`** | **Sí.** Ya está **dentro** del motor único: dry-run, permisos, parada y auditoría. Y el cierre de la versión anterior **muta**, luego G-1 exige que pase por ahí |

La **identidad** del hecho («¿de qué ya sabía algo esto?») sale de la gramática de la propia frase del
usuario, en `core/identidad_memoria.py`, de forma determinista y **sin una sola llamada al modelo**. El
módulo existe porque esa gramática la necesitan dos sitios que no pueden importarse entre sí —el
orquestador para responder, el ejecutor para versionar—, y duplicarla habría creado dos definiciones de
«mismo atributo» que divergirían en el primer cambio.

## 4 · Lo que NO se ha hecho, por decisión del CEO

`PROPOSE` (`D-AMP-4`) · alias de identidad (`D-AMP-5`) · Context Builder (`D-AMP-2`) · asesores ·
búsqueda semántica · Qdrant · Obsidian · `confidence`. Tampoco un quinto campo `superseded`:
«superseded» es **derivado** de `valid_until is not None`, porque un booleano aparte podría contradecir
a la fecha y entonces habría que decidir cuál manda.

## 5 · Limitación declarada

Se versiona lo que la gramática posesiva reconoce como atributo («mi cumpleaños», «mi coche»). Las
declaraciones que **no** nombran un atributo —«me llamo Pedro», «me gusta el jazz»— no se versionan:
numerarlas sería declarar un historial que nadie pidió. Para esas sigue vigente la regla anterior
—gana la última declaración—, y su unificación depende de `D-AMP-5` (alias de identidad), pospuesta.
