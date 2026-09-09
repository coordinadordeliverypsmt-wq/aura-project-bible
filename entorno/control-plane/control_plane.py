"""Development Control Plane — estado persistente del TRABAJO sobre AURORA.

## Que es, y sobre todo que NO es

Es **infraestructura de desarrollo**. Existe para que el trabajo pueda continuar entre sesiones y
entre herramientas sin que un humano copie mensajes de una ventana a otra.

**No forma parte de AURORA y no le concede ninguna capacidad.** No importa ni un solo modulo del
producto, y una prueba lo verifica leyendo el texto de este fichero. Confundir «autonomia para
desarrollar AURORA» con «autonomia de AURORA» seria el error mas caro posible aqui: la metrica de
gobierno sigue en 0/7 y nada de esto la mueve.

## Por que no duplica el checkpoint existente

`CHECKPOINT-CONTINUIDAD.md` ya es estado persistente entre sesiones, y es la fuente de verdad
narrativa: decisiones, alcance aprobado, prohibiciones. Este modulo **no lo sustituye ni lo copia**.
Guarda lo que un documento en prosa no puede dar: estado **legible por maquina**, verificable contra
`git` y actualizable sin que nadie redacte. El campo `checkpoint` apunta al documento; la autoridad
sigue estando alli.

## La honestidad sobre la cuota es el nucleo de este modulo

El CEO prohibio expresamente inventar porcentajes. Se investigo que expone realmente Claude Code:

- `~/.claude/policy-limits.json` contiene **restricciones de politica, no cuota**.
- `~/.claude/history.jsonl` contiene marcas temporales de actividad: dice **cuando** se trabajo, no
  **cuanto** se consumio.
- No existe ningun fichero ni orden que publique consumo o cuota restante.
- La unica evidencia real de agotamiento es **el error que devuelve la herramienta al fallar**, que
  es una observacion a posteriori y no una prediccion. Se observo empiricamente en esta sesion:
  varios agentes murieron con «You've hit your monthly spend limit».

En consecuencia `usage_known` es **false** y los dos limites arrancan en `UNKNOWN`. Este modulo
**jamas** afirma cuanto queda. Estimar un porcentaje seria el patron `declarado != real` cometido
dentro de la herramienta que vigila el trabajo — que es donde mas dano hace.

Las dos ventanas se modelan por separado porque se renuevan por separado: la movil (~4 h 30 min) y
la semanal.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import fcntl
import hashlib
import json
import os
import pathlib
import re
import subprocess

VERSION = 1

# Vocabulario fijado por el CEO el 2026-08-17. `WAITING_FOR_NEXT_TASK` se conserva como octavo
# estado porque «no hay tarea asignada» no es lo mismo que «espero una decision humana»: el primero
# se resuelve dandole trabajo, el segundo solo lo resuelve una persona.
ESTADOS = ("WORKING", "WAITING_FOR_QUOTA", "WAITING_FOR_ENVIRONMENT", "DECISION_REQUIRED",
           "WAITING_FOR_HUMAN", "COMPLETED", "FAILED", "WAITING_FOR_NEXT_TASK")

ESTADOS_CUOTA = ("NORMAL", "WARNING", "CHECKPOINT_REQUIRED", "PAUSED", "UNKNOWN")

# Duracion declarada de la ventana movil. Es el dato que dio el CEO; no se deriva de ninguna
# medicion propia y por eso se marca como declarado, no observado.
VENTANA_MOVIL_MIN = 270

HISTORIAL = pathlib.Path.home() / ".claude" / "history.jsonl"

ESTADO_POR_DEFECTO = pathlib.Path(__file__).resolve().parent / "estado.json"


def _ahora() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


# ================================================================= MODELO DE ESTADO --


def estado_inicial() -> dict:
    return {
        "version": VERSION,
        "actualizado": _ahora(),
        "status": "WAITING_FOR_NEXT_TASK",
        "tarea_actual": None,
        "git": {"rama": None, "ultimo_commit": None, "ficheros_modificados": [], "limpio": None},
        "verificacion": {"tests": None, "quality_gate": None},
        "defectos": [],
        "decisiones_pendientes": [],
        "aprobaciones": [],
        "siguiente_tarea": None,
        "trabajo_completado": [],
        "checkpoint": {"documento": "CHECKPOINT-CONTINUIDAD.md", "commit": None},
        "sesion_claude": None,
        "estado_ejecucion": None,
        "motivo_pausa": None,
        "cuota": observar_cuota(),
    }


def migrar_cuota(cuota: dict) -> dict:
    """Completa las ventanas que un estado antiguo no conocia. **Siempre como UNKNOWN.**

    Un estado escrito antes de existir `monthly_spend` no dice nada sobre el limite mensual;
    rellenarlo con `NORMAL` afirmaria un margen que nadie observo, que es el patron
    `declarado != real` aplicado a la propia herramienta de vigilancia."""
    plantilla = observar_cuota()
    for clave in CLAVES_DE_CUOTA:
        if not isinstance(cuota.get(clave), dict):
            cuota[clave] = dict(plantilla[clave])
    cuota.setdefault("usage_known", False)
    cuota.setdefault("senales_observadas", [])
    return cuota


def validar(estado: dict) -> dict:
    if estado.get("status") not in ESTADOS:
        raise ValueError(f"status desconocido: {estado.get('status')!r}; validos: {ESTADOS}")
    cuota = migrar_cuota(estado.get("cuota") or {})
    estado["cuota"] = cuota
    for ventana in CLAVES_DE_CUOTA:
        v = cuota.get(ventana) or {}
        if v.get("estado") not in ESTADOS_CUOTA:
            raise ValueError(f"estado de cuota desconocido en {ventana}: {v.get('estado')!r}")
    # Regla del CEO, 2026-08-17: no se declara espera por cuota sin haberla observado.
    #
    # Desconocer la cuota no es haberla agotado. Si `WAITING_FOR_QUOTA` pudiera ponerse por
    # ignorancia, el trabajo se detendria esperando una renovacion que quiza no bloquea nada — y el
    # siguiente agente heredaria una parada inventada. La unica evidencia valida es haber visto a la
    # herramienta rechazar trabajo por limite.
    if estado["status"] == "WAITING_FOR_QUOTA" and not cuota.get("senales_observadas"):
        raise ValueError(
            "WAITING_FOR_QUOTA sin evidencia observada de limite. Desconocer la cuota no es "
            "haberla agotado: si el bloqueo es de memoria o disco, el estado es "
            "WAITING_FOR_ENVIRONMENT; si simplemente no se sabe, es WORKING"
        )
    return estado


# Lo arma `conftest.py` durante las pruebas. Fuera de ellas es None y `guardar` se comporta igual
# que siempre: el modulo no se entera de que existe una bateria de pruebas.
_ESCRITURA_VIGILADA: "callable | None" = None


def vigilar_escrituras(centinela) -> None:
    """Instala (o retira, con None) el centinela que revisa cada destino antes de escribirlo."""
    global _ESCRITURA_VIGILADA
    _ESCRITURA_VIGILADA = centinela


_CAMPOS_DE_GOBIERNO = ("autoridad", "previo")


def validar_tareas(estado: dict) -> None:
    """**Borde de persistencia** (3.a auditoria, hallazgo GRAVE 1).

    `validar()` solo miraba `status` y `cuota`, asi que escribir a mano en `estado["tareas"]` y
    llamar a `guardar()` persistia cualquier estado inventado —incluida una tarea creada en
    `COMPLETED`—, entrando **por debajo** de `validar_transicion`. El detector de rutas de F1 no
    podia verlo: enumera funciones, y una asignacion a un diccionario no es ninguna.

    Lo que se puede garantizar, y no mas: que lo que **se escribe a disco** lleve los campos que
    solo pone el gobierno. Dentro de un proceso, el codigo siempre puede tocar su propia memoria; la
    garantia fuerte no es el diccionario sino el **log append-only** de F1, que si es verificable.
    Esto eleva la falsificacion de trivial a deliberada y **la deja escrita**: hay que declarar una
    autoridad."""
    for id_tarea, tarea in (estado.get("tareas") or {}).items():
        if not isinstance(tarea, dict):
            raise ValueError(f"la tarea {id_tarea!r} no es un registro valido")
        if tarea.get("estado") not in ESTADOS:
            raise ValueError(f"la tarea {id_tarea!r} tiene un estado desconocido: "
                             f"{tarea.get('estado')!r}")
        faltan = [c for c in _CAMPOS_DE_GOBIERNO if c not in tarea]
        if faltan:
            raise ValueError(
                f"la tarea {id_tarea!r} no paso por el gobierno: le faltan {faltan}. Su procedencia "
                f"no consta, y un estado sin procedencia no se persiste")
        if tarea.get("estado") == "COMPLETED" and tarea.get("autoridad") not in AUTORIDADES_HUMANAS:
            # Comprobaba que los campos de gobierno **estuvieran**, no lo que decian: un COMPLETED
            # con `autoridad="cualquiera"` se persistia. Y `render_handoff()` lee de aqui, asi que un
            # relevo habria presentado como terminado un trabajo fabricado. Lo encontro la 4.a
            # auditoria; a diferencia de `_registrar_sin_lock`, esto **si** se cierra en proceso, y
            # declararlo irreducible habria sido la forma comoda del `declarado != real`.
            raise ValueError(
                f"la tarea {id_tarea!r} se persiste en COMPLETED con autoridad "
                f"{tarea.get('autoridad')!r}: este modelo no tiene log donde comprobar un criterio "
                f"mecanico, asi que cerrarla exige acto humano (§14.bis regla 4)")


def guardar(estado: dict, destino: pathlib.Path | None = None) -> pathlib.Path:
    """Escritura atomica. El estado se lee desde otra herramienta y desde otra sesion: un fichero
    a medio escribir no es «un poco de estado», es un estado falso."""
    # Resuelto **al llamar**, no al importar. Con el `Path` como valor por defecto de la firma, el
    # objeto quedaba horneado en tiempo de import: quien aislaba una prueba reasignando
    # `ESTADO_POR_DEFECTO` creia estar a salvo y seguia escribiendo el fichero real. Lo encontro la
    # tercera auditoria, y es la peor clase de trampa: fallaba justo el patron que la gente usa
    # **para protegerse**.
    destino = pathlib.Path(destino) if destino is not None else ESTADO_POR_DEFECTO
    if _ESCRITURA_VIGILADA is not None:
        _ESCRITURA_VIGILADA(destino)
    validar(estado)
    validar_tareas(estado)
    estado["actualizado"] = _ahora()
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(destino)
    return destino


def cargar(origen: pathlib.Path | None = None) -> dict | None:
    """Devuelve None si no hay estado. Que no exista es informacion, no motivo para fabricarlo.

    Mismo motivo que `guardar` para no fijar el `Path` en la firma: se resuelve al llamar."""
    origen = pathlib.Path(origen) if origen is not None else ESTADO_POR_DEFECTO
    if not origen.exists():
        return None
    estado = json.loads(origen.read_text(encoding="utf-8"))
    estado["cuota"] = migrar_cuota(estado.get("cuota") or {})
    return estado


def estado_vigente(estado: dict, commit_actual: str | None) -> tuple[bool, str]:
    """«No asumir que un proceso anterior termino correctamente solo porque existe un archivo de
    estado.» Si el commit registrado no es el de ahora, alguien trabajo despues y el estado
    describe un pasado que ya no es el presente."""
    registrado = (estado.get("git") or {}).get("ultimo_commit")
    if registrado and commit_actual and registrado != commit_actual:
        return False, (f"el estado se escribio en el commit {registrado} y el actual es "
                       f"{commit_actual}: hay trabajo posterior no reflejado")
    return True, "vigente"


# =============================================== TRABAJO COMPLETADO Y CHECKPOINT --


def iniciar_tarea(estado: dict, id_tarea: str, descripcion: str, **extra) -> dict:
    estado["tarea_actual"] = {"id": id_tarea, "descripcion": descripcion,
                              "iniciada_en": _ahora(), **extra}
    estado["status"] = "WORKING"
    return estado


def _exigir_humano_para_completar(funcion: str, id_tarea: str, valor: str, autoridad: str) -> None:
    """`§14.bis` regla 3 aplicada a las rutas que **no tienen log que consultar**.

    `completar_tarea` y `fijar_estado_tarea` trabajan sobre el modelo en memoria, no sobre
    `eventos.jsonl`, asi que no pueden comprobar ningun criterio mecanico. Inventarles una
    verificacion seria fingirla; lo honesto es exigir el acto humano que la **regla 4** reserva para
    lo que no es automatizable.

    Se lanza `CriterioNoVerificado`, que **es** una `TransicionInvalida`: quien capturaba el rechazo
    generico sigue capturandolo, y quien quiera distinguir este motivo puede.

    Ambas estaban declaradas `GOBERNADAS` desde F1 y aun asi cerraban `COMPLETED` con autoridad no
    humana y sin criterio. Lo encontro la **segunda** auditoria independiente, despues de que la
    primera me hiciera escribir una prueba que decia recorrer «todas las vias publicas» y enumeraba
    tres a mano. La leccion no es que faltaran dos: es que **una lista escrita a mano no es un
    barrido**."""
    if valor == "COMPLETED" and autoridad not in AUTORIDADES_HUMANAS:
        raise CriterioNoVerificado(
            f"{funcion}() no puede cerrar {id_tarea!r} como COMPLETED con autoridad {autoridad!r}: "
            f"trabaja sobre el estado en memoria y no tiene log donde comprobar el criterio "
            f"mecanico. La via automatica es transicion() sobre el event log; esta exige humano")


def completar_tarea(estado: dict, id_tarea: str, resultado: str,
                    evidencia: dict | None = None, *, autoridad: str = "") -> dict:
    """Registra la tarea como hecha. Idempotente: completar dos veces no la duplica.

    **Gobernada tras la auditoria de F1 (hallazgo GRAVE 1).** Escribe en `trabajo_completado`, y
    `estado_de_tarea` lee COMPLETED de ahi: era una **tercera ruta** al estado, sin autoridad, sin
    causa y sin tabla. Permitia cerrar una tarea parada en `DECISION_REQUIRED` **sin ningun acto
    humano**, que es exactamente lo que el criterio A5 prohibe — y la demostracion de A5 no la
    probo, porque solo intento entrar por `transicion()`.

    El chequeo va **antes** del retorno por idempotencia: si ya estaba completada, re-completarla no
    cambia nada, pero pedir autoridad igualmente mantiene una sola regla en lugar de dos."""
    hechas = estado.setdefault("trabajo_completado", [])
    # La tabla primero: «crear no es transicionar» y «falta autoridad» son errores mas basicos, y
    # decirlos antes evita que el gate humano tape el motivo real con uno mas general.
    validar_transicion(estado_de_tarea(estado, id_tarea)["estado"], "COMPLETED",
                       autoridad, resultado)
    _exigir_humano_para_completar("completar_tarea", id_tarea, "COMPLETED", autoridad)
    if any(t["id"] == id_tarea for t in hechas):
        return estado
    actual = estado.get("tarea_actual") or {}
    duracion = None
    if actual.get("id") == id_tarea and actual.get("iniciada_en"):
        try:
            inicio = _dt.datetime.fromisoformat(actual["iniciada_en"])
            duracion = round((_dt.datetime.now() - inicio).total_seconds())
        except ValueError:
            duracion = None
    marca = (estado.get("tareas") or {}).get(id_tarea, {}).get("creada_sin_origen", False)
    hechas.append({"id": id_tarea, "resultado": resultado, "evidencia": evidencia or {},
                   "cuando": _ahora(), "duracion_s": duracion,
                   "creada_sin_origen": bool(marca)})
    if actual.get("id") == id_tarea:
        estado["tarea_actual"] = None
    return estado


def debe_ejecutar(estado: dict, id_tarea: str) -> tuple[bool, str]:
    """Impide repetir trabajo ya hecho.

    Un agente que reanuda y repite una tarea completada la presenta como nueva: es la forma mas
    cara de `declarado != real` en un relevo, porque el siguiente lector cuenta dos veces el mismo
    avance."""
    for t in estado.get("trabajo_completado", []):
        if t["id"] == id_tarea:
            return False, f"la tarea {id_tarea} ya esta completada ({t['cuando']}): no se repite"

    # Una decision pendiente bloquea **solo las tareas que declara**, no todo el trabajo.
    #
    # `DECISION_REQUIRED` como estado global detendria tareas independientes que si pueden avanzar,
    # y el trabajo se pararia entero por una decision acotada. Una decision que no declara a quien
    # afecta es informacion anotada, no un freno: frenar por defecto pararia todo por cualquier nota.
    for d in estado.get("decisiones_pendientes", []):
        bloquea = d.get("bloquea")
        if bloquea == "todo" or (isinstance(bloquea, (list, tuple)) and id_tarea in bloquea):
            return False, (f"la tarea {id_tarea} espera la decision {d.get('id', '?')}: "
                           f"{d.get('asunto', 'sin asunto')}")
    return True, "no consta como completada ni bloqueada por una decision"


def leer_checkpoint(documento: pathlib.Path) -> dict:
    """Lee el checkpoint narrativo. **No lo interpreta ni lo reescribe:** solo observa que existe,
    cuanto ocupa, que secciones tiene y su huella, para poder detectar despues si cambio."""
    if not documento.exists():
        return {"documento": str(documento), "existe": False, "secciones": [],
                "lineas": 0, "sha256": None}
    texto = documento.read_text(encoding="utf-8", errors="replace")
    secciones = [ln.lstrip("# ").strip() for ln in texto.splitlines() if ln.startswith("## ")]
    return {
        "documento": str(documento),
        "existe": True,
        "lineas": len(texto.splitlines()),
        "secciones": secciones,
        "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
    }


def checkpoint_sin_cambios(estado: dict, documento: pathlib.Path) -> tuple[bool, str]:
    """Si el checkpoint cambio desde que se escribio el estado, el estado describe otra realidad."""
    registrada = (estado.get("checkpoint") or {}).get("sha256")
    actual = leer_checkpoint(documento).get("sha256")
    if registrada and actual and registrada != actual:
        return False, ("el checkpoint cambio desde que se escribio este estado: releelo antes de "
                       "continuar, la narrativa manda sobre el estado observado")
    return True, "sin cambios"


# ================================= ESTADO POR TAREA · el global no oculta el individual --
#
# Regla del CEO, 2026-08-17. Pueden coexistir `EXP-REPRO: WAITING_FOR_ENVIRONMENT` y
# `EXP-CAMPANA: DECISION_REQUIRED` sin contradiccion: el global describe la tarea que el agente
# intenta ejecutar, las demas conservan el suyo. Colapsarlos haria que un agente esperase memoria
# por una decision pendiente, o pidiese una decision por falta de memoria.

VENTANAS_CUOTA = ("SHORT_4H30", "WEEKLY", "MONTHLY_SPEND_LIMIT", "UNKNOWN")

# Nombre de la ventana (como lo dice el CEO) -> clave del estado persistente.
#
# Son TRES limites independientes, no tres nombres del mismo. Se observo el mensaje «You've hit
# your monthly spend limit» el 2026-08-17: ese limite no es la ventana movil ni la semanal, y
# tratarlo como una de ellas haria deducir una renovacion falsa. `UNKNOWN` no mapea a ninguna
# clave a proposito: sin saber cual se agoto, NINGUNA se marca agotada.
CLAVE_DE_VENTANA = {
    "SHORT_4H30": "rolling_window",
    "WEEKLY": "weekly",
    "MONTHLY_SPEND_LIMIT": "monthly_spend",
}
CLAVES_DE_CUOTA = ("rolling_window", "weekly", "monthly_spend")

# Las tres ventanas no son del mismo tipo, y confundirlo detuvo trabajo que si era posible.
#
# Evidencia visual del CEO (pagina oficial de uso, 2026-08-17): sesion 26 % usada DISPONIBLE,
# semanal 56 % usada DISPONIBLE, uso adicional USD 21,84 sobre un limite de USD 20,00 = 109 %
# PAUSADO. El mensaje «You've hit your monthly spend limit» NO decia «Claude Code agotado»: decia
# «el uso adicional de pago esta agotado». Lo incluido en el plan seguia disponible.
CAPACIDAD_INCLUIDA = ("rolling_window", "weekly")   # lo que el plan da; agotarlo detiene el trabajo
USO_ADICIONAL = ("monthly_spend",)                  # gasto extra; agotarlo NO detiene lo incluido

# Por que un momento de interrupcion NO puede dar COMPLETED: falta la evidencia que lo demuestre.
INTERRUPCION = {
    "espera_ambiental": ("WAITING_FOR_ENVIRONMENT", "interrumpida esperando condicion ambiental"),
    "primera_inferencia": ("FAILED", "interrumpida durante la primera inferencia"),
    "segunda_inferencia": ("FAILED", "interrumpida durante la segunda inferencia"),
    "escritura_evidencia": ("FAILED", "interrumpida escribiendo la evidencia: puede haber .parcial"),
    "agotamiento_cuota": ("WAITING_FOR_QUOTA", "interrumpida por limite de uso"),
    "cierre_de_claude": ("FAILED", "la sesion termino sin cerrar la tarea"),
}


def fijar_estado_tarea(estado: dict, id_tarea: str, valor: str, motivo: str = "", *,
                       autoridad: str = "", causa: str = "") -> dict:
    """**Gobernada desde F1 (`§9.3`)**: valida el estado previo contra `TRANSICIONES` y exige
    **autoridad y causa**, «como ya hace el producto».

    Existen dos rutas al mismo estado —esta, en memoria, y `transicion()`, sobre el log— y gobernar
    solo una dejaria la otra como **puerta trasera**: ALERTA-005 otra vez, «ninguna ruta
    alternativa». Por eso ambas comparten `validar_transicion`.

    `motivo` **es** la causa: se conserva el nombre historico en la firma posicional y `causa` queda
    como alias explicito. Inventar un segundo campo con el mismo significado solo habria producido
    dos sitios donde mirar y uno de ellos vacio.

    El estado previo se lee con `estado_de_tarea`, **no** de `estado['tareas']`: completar por
    `completar_tarea` tambien produce COMPLETED, y mirar solo el diccionario dejaria esa via
    reabrible.

    Una tarea sin estado previo se **crea**, no transiciona: no hay origen contra el que validar.
    Sin esa distincion el gobierno prohibiria registrar un bloqueo de entorno sobre una tarea que
    aun no consta como WORKING —que es lo que `interrumpir` y `registrar_bloqueo_de_cuota` hacen— y
    P4 se habria «cerrado» rompiendo el uso legitimo."""
    previo = estado_de_tarea(estado, id_tarea)["estado"]
    causa_efectiva = causa or motivo
    validar_transicion(previo, valor, autoridad, causa_efectiva)
    _exigir_humano_para_completar("fijar_estado_tarea", id_tarea, valor, autoridad)
    anterior = (estado.get("tareas") or {}).get(id_tarea) or {}
    # **Huella del rodeo** (3.a auditoria, hallazgo GRAVE 2). Crear en `FAILED` y de ahi ir a
    # `WORKING` y `COMPLETED` produce, en tres llamadas y sin autoridad humana, una tarea que nunca
    # existio y consta terminada. Eso **no se cierra aqui**: exigir autoridad humana para completar
    # rompe el proposito del orquestador, y el control que lo cierra es el criterio **A12**
    # —«COMPLETED solo tras ejecutar el criterio mecanico»—, que pertenece a F4/F5, hoy bloqueadas.
    # Lo que si se puede hoy es que el rodeo **deje rastro**, y que el rastro no se borre al avanzar.
    # Marcar **toda** tarea nueva no distinguiria nada: todas nacen sin estado previo. Lo que
    # importa es si aparecio como tarea *pendiente* —registro limpio— o directamente en un estado de
    # trabajo o terminal, que es el rodeo.
    sin_origen = anterior.get(
        "creada_sin_origen",
        previo == ESTADO_SIN_REGISTRAR and valor != ESTADO_INICIAL_DE_TAREA)
    estado.setdefault("tareas", {})[id_tarea] = {
        "estado": valor, "motivo": causa_efectiva, "autoridad": autoridad,
        "previo": previo, "creada_sin_origen": bool(sin_origen), "actualizado": _ahora()}
    return estado


def estado_de_tarea(estado: dict, id_tarea: str) -> dict:
    """Estado individual. **Nunca hereda el global**: heredarlo haria creer que una tarea nueva ya
    esta bloqueada por un motivo que no le concierne."""
    for t in estado.get("trabajo_completado", []):
        if t["id"] == id_tarea:
            return {"estado": "COMPLETED", "motivo": t.get("resultado", ""),
                    "actualizado": t.get("cuando")}
    propio = (estado.get("tareas") or {}).get(id_tarea)
    if propio:
        return propio
    return {"estado": "UNKNOWN", "motivo": "sin estado propio registrado", "actualizado": None}


def interrumpir(estado: dict, id_tarea: str, momento: str) -> dict:
    """Registra una interrupcion **sin marcar COMPLETED**.

    Un COMPLETED falso hace que el siguiente agente de por hecho un trabajo que nunca ocurrio, y
    nadie vuelve a mirarlo. Sin evidencia suficiente, el estado honesto es el que dice que se
    interrumpio y por donde."""
    if momento not in INTERRUPCION:
        raise ValueError(f"momento de interrupcion desconocido: {momento!r}")
    valor, motivo = INTERRUPCION[momento]
    return fijar_estado_tarea(estado, id_tarea, valor, motivo, autoridad="control_plane")


def registrar_bloqueo_de_cuota(estado: dict, mensaje: str, ventana: str | None,
                               tarea: str, siguiente_paso: str = "") -> dict:
    """La cuota es un **recurso externo** que bloquea temporalmente, no una decision humana.

    **Una ventana no arrastra a la otra:** una renovacion de la corta no implica que la semanal se
    haya renovado, y deducirlo haria reanudar trabajo que la semanal sigue bloqueando. Si no hay
    evidencia de cual se agoto, se registra UNKNOWN en vez de suponerlo."""
    ventana = ventana or "UNKNOWN"
    if ventana not in VENTANAS_CUOTA:
        raise ValueError(f"ventana de cuota desconocida: {ventana!r}; validas: {VENTANAS_CUOTA}")
    estado["cuota"] = migrar_cuota(estado.get("cuota") or {})
    hechas = [t["id"] for t in estado.get("trabajo_completado", [])]
    estado["quota_block"] = {
        "tipo": "QUOTA_LIMIT_OBSERVED",
        "timestamp": _ahora(),
        "ventana": ventana,
        # El producto no publica cuando se renueva ninguna de las tres ventanas. Calcular una
        # fecha seria inventarla, y el agente siguiente volveria a chocar contra el mismo muro
        # convencido de que ya habia pasado.
        "renovacion": "UNKNOWN",
        # WAITING_FOR_QUOTA describe la ACCION —esperar—, no anula el estado que la cuota
        # interrumpio. Sin este campo, al renovarse la cuota el relevo creeria que ya no habia
        # decisiones pendientes.
        "estado_previo": estado.get("status"),
        "mensaje": mensaje,
        "tarea_pausada": tarea,
        "ultimo_paso_completado": hechas[-1] if hechas else None,
        "siguiente_paso": siguiente_paso or "leer el checkpoint y continuar desde el ultimo COMPLETED",
        "archivos_modificados": (estado.get("git") or {}).get("ficheros_modificados", []),
        "pruebas_realizadas": (estado.get("verificacion") or {}).get("tests"),
        "nota": ("las tres ventanas son independientes: la renovacion de una NO implica la de "
                 "ninguna otra; sin evidencia, UNKNOWN"),
    }
    # Se marca EXCLUSIVAMENTE la ventana observada. Las demas siguen como estuvieran —tipicamente
    # UNKNOWN— porque de ellas no hay evidencia: ni de que queden, ni de que se hayan agotado.
    clave = CLAVE_DE_VENTANA.get(ventana)
    if clave:
        estado["cuota"][clave]["estado"] = "PAUSED"
        estado["cuota"][clave]["senal"] = mensaje
        estado["cuota"][clave]["observado_en"] = _ahora()
    estado["cuota"].setdefault("senales_observadas", []).append(
        {"ventana": ventana, "senal": mensaje, "cuando": _ahora()})
    fijar_estado_tarea(estado, tarea, "WAITING_FOR_QUOTA", mensaje, autoridad="entorno")
    estado["status"] = "WAITING_FOR_QUOTA"
    return estado


# ============================================================================ CUOTA --


def observar_cuota() -> dict:
    """Estado de cuota basado SOLO en lo observable. Nunca estima consumo."""
    return {
        "usage_known": False,
        "por_que": ("Claude Code no publica consumo ni cuota restante. `policy-limits.json` "
                    "contiene restricciones de politica; `history.jsonl` contiene marcas de "
                    "actividad, no consumo. La unica evidencia de agotamiento es el error "
                    "devuelto al fallar, que es posterior al hecho."),
        "rolling_window": {"estado": "UNKNOWN", "duracion_declarada_min": VENTANA_MOVIL_MIN,
                           "fuente": "declarada por el CEO, no medida",
                           "observado_en": None, "senal": None},
        "weekly": {"estado": "UNKNOWN", "fuente": "sin senal observable",
                   "observado_en": None, "senal": None},
        "monthly_spend": {"estado": "UNKNOWN",
                          "fuente": "solo observable en el error devuelto al fallar",
                          "observado_en": None, "senal": None,
                          "renovacion": "UNKNOWN"},
        "senales_observadas": [],
    }


def estimar_ventana_movil(historial: pathlib.Path = HISTORIAL,
                          ahora_ms: int | None = None) -> dict:
    """Estima **el limite temporal** de la ventana movil, jamas su consumo.

    `history.jsonl` registra una linea por entrada del usuario, con marca de tiempo. Eso permite
    situar cuando empezo la actividad reciente y, sumando la duracion declarada, cuando se
    renovaria la ventana. **No dice nada sobre cuanta cuota se ha gastado**, y este modulo no lo
    insinua: el estado sigue siendo UNKNOWN salvo que se observe una senal de limite real.
    """
    base = {"estado": "UNKNOWN", "duracion_declarada_min": VENTANA_MOVIL_MIN,
            "fuente": str(historial), "observado_en": None, "senal": None}
    if not historial.exists():
        base["nota"] = "no hay historial observable"
        return base
    if ahora_ms is None:
        ahora_ms = int(_dt.datetime.now().timestamp() * 1000)
    ventana_ms = VENTANA_MOVIL_MIN * 60 * 1000
    marcas = []
    for linea in historial.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            t = json.loads(linea).get("timestamp")
        except Exception:  # noqa: BLE001 — una linea corrupta no invalida el resto
            continue
        if isinstance(t, (int, float)) and ahora_ms - t <= ventana_ms:
            marcas.append(int(t))
    if not marcas:
        base["nota"] = "sin actividad dentro de la ventana declarada"
        return base
    inicio = min(marcas)
    base["primera_actividad_en_la_ventana"] = _dt.datetime.fromtimestamp(inicio / 1000).isoformat(
        timespec="seconds")
    base["renovacion_estimada"] = _dt.datetime.fromtimestamp(
        (inicio + ventana_ms) / 1000).isoformat(timespec="seconds")
    base["minutos_transcurridos"] = round((ahora_ms - inicio) / 60000)
    base["nota"] = ("limite temporal estimado de la ventana; NO indica cuanta cuota queda")
    return base


def registrar_señal_de_limite(cuota: dict, senal: str, ventana: str) -> dict:
    """Unica via por la que una ventana pasa a PAUSED: haberlo observado al fallar.

    Ejemplo real de esta sesion: varios subagentes terminaron con «You've hit your monthly spend
    limit». Eso es evidencia; una estimacion previa no lo habria sido."""
    if ventana not in CLAVES_DE_CUOTA:
        raise ValueError(f"ventana desconocida: {ventana!r}; validas: {CLAVES_DE_CUOTA}")
    cuota[ventana]["estado"] = "PAUSED"
    cuota[ventana]["senal"] = senal
    cuota[ventana]["observado_en"] = _ahora()
    cuota.setdefault("senales_observadas", []).append(
        {"ventana": ventana, "senal": senal, "cuando": _ahora()})
    return cuota


def puede_empezar(cuota: dict, coste: str = "alto",
                  requiere_uso_adicional: bool = False) -> tuple[bool, str]:
    """Decide si arrancar una unidad de trabajo. **Desconocer la cuota no es tenerla.**

    Con `UNKNOWN` se permite el trabajo barato —inspeccion, pruebas locales, documentacion— y se
    rechaza el caro, porque empezar algo grande sin margen conocido termina en trabajo abandonado
    a mitad, que es peor que no haberlo empezado.

    **El uso adicional agotado NO detiene el trabajo que cabe en la capacidad incluida.** Solo
    detiene aquello que declare necesitarlo (`requiere_uso_adicional=True`). La version anterior
    de esta funcion bloqueaba todo —incluido el trabajo barato— en cuanto `monthly_spend` pasaba a
    `PAUSED`, y con ello habria parado documentar, revisar y ordenar el estado, que era
    exactamente lo unico que si se podia hacer."""
    cuota = migrar_cuota(cuota)
    for ventana in CAPACIDAD_INCLUIDA:
        estado = cuota[ventana]["estado"]
        if estado in ("PAUSED", "CHECKPOINT_REQUIRED"):
            return False, f"{ventana} en {estado}: checkpoint y esperar renovacion"
    if requiere_uso_adicional:
        for ventana in USO_ADICIONAL:
            estado = cuota[ventana]["estado"]
            if estado in ("PAUSED", "CHECKPOINT_REQUIRED"):
                return False, (f"{ventana} en {estado}: esta tarea declara necesitar uso adicional "
                               f"y el limite mensual de gasto esta superado")
    if coste == "alto":
        # Solo se mira lo incluido: desconocer el uso adicional no es haber agotado el plan.
        if any(cuota[v]["estado"] == "UNKNOWN" for v in CAPACIDAD_INCLUIDA):
            return False, ("cuota desconocida: no se arranca trabajo caro sin margen conocido. "
                           "Desconocer la cuota no es tenerla")
        if any(cuota[v]["estado"] == "WARNING" for v in CAPACIDAD_INCLUIDA):
            return False, "cuota en WARNING: solo trabajo barato"
    return True, "hay margen para este coste"


def registrar_uso_observado(cuota: dict, ventana: str, porcentaje_usado: float | None,
                            fuente: str, observado_en: str, estado: str,
                            renovacion: str | None = None) -> dict:
    """Registra un consumo **leido**, nunca estimado.

    Este modulo prohibe inventar porcentajes; no prohibe anotar uno que alguien vio de verdad. La
    diferencia esta en `fuente` e `observado_en`, que por eso son obligatorios: sin ellos el dato
    se leeria manana como si siguiera siendo cierto. Por eso tambien va marcado `caduca`: es una
    instantanea de un contador que se mueve solo."""
    cuota = migrar_cuota(cuota)
    if ventana not in CLAVES_DE_CUOTA:
        raise ValueError(f"ventana desconocida: {ventana!r}; validas: {CLAVES_DE_CUOTA}")
    if estado not in ESTADOS_CUOTA:
        raise ValueError(f"estado de cuota desconocido: {estado!r}; validos: {ESTADOS_CUOTA}")
    if not fuente or not observado_en:
        raise ValueError("un porcentaje sin fuente ni instante de observacion es indistinguible "
                         "de uno inventado: ambos son obligatorios")
    cuota[ventana].update({
        "estado": estado,
        "porcentaje_usado_observado": porcentaje_usado,
        "fuente": fuente,
        "observado_en": observado_en,
        "caduca": True,
        "nota": "instantanea observada; el contador se mueve solo. No extrapolar.",
    })
    if renovacion is not None:
        cuota[ventana]["renovacion"] = renovacion
    return cuota


def resumen_de_cuota(cuota: dict) -> str:
    """Una linea que separa lo que el plan incluye de lo que se paga aparte.

    Sin esta separacion, quien lee el handoff concluye «Claude esta bloqueado» y no intenta el
    trabajo que si puede hacerse."""
    cuota = migrar_cuota(cuota)

    def _grupo(claves: tuple[str, ...]) -> str:
        estados = [cuota[k]["estado"] for k in claves]
        if any(e in ("PAUSED", "CHECKPOINT_REQUIRED") for e in estados):
            return "AGOTADA" if claves == CAPACIDAD_INCLUIDA else "BLOQUEADO"
        if any(e == "UNKNOWN" for e in estados):
            return "DESCONOCIDA" if claves == CAPACIDAD_INCLUIDA else "DESCONOCIDO"
        return "DISPONIBLE"

    return (f"capacidad incluida: {_grupo(CAPACIDAD_INCLUIDA)} · "
            f"uso adicional: {_grupo(USO_ADICIONAL)}")


# ============================================================================== GIT --


def observar_git(directorio: pathlib.Path) -> dict:
    """Observa; no declara. Git es la fuente auditable."""
    def _git(*args: str) -> str | None:
        try:
            r = subprocess.run(["git", *args], cwd=directorio, capture_output=True,
                               text=True, timeout=30)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:  # noqa: BLE001
            return None

    porcelain = _git("status", "--porcelain")
    # `ln[3:]` se comia un caracter del nombre segun el estado del fichero: el prefijo de
    # `--porcelain` son dos columnas de estado y un separador, pero la primera puede ir vacia y el
    # recorte por posicion fija no lo contempla. Se detecto leyendo un handoff real, donde aparecia
    # «HECKPOINT-CONTINUIDAD.md».
    modificados = [ln[2:].lstrip() for ln in porcelain.splitlines()] if porcelain else []
    return {
        "rama": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "ultimo_commit": _git("rev-parse", "--short", "HEAD"),
        "ficheros_modificados": modificados,
        "limpio": porcelain == "" if porcelain is not None else None,
    }


# ========================================================================== HANDOFF --


def _linea(valor) -> str:
    if valor is None:
        return "(sin registrar)"
    if isinstance(valor, (list, tuple)):
        return ", ".join(str(x) for x in valor) if valor else "(ninguno)"
    if isinstance(valor, dict):
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


def render_handoff(estado: dict) -> str:
    """Bloque legible para que otro agente continue SIN leer la conversacion entera."""
    g = estado.get("git") or {}
    v = estado.get("verificacion") or {}
    c = estado.get("cuota") or {}
    sig = estado.get("siguiente_tarea") or {}
    filas = [
        ("STATUS", estado.get("status")),
        ("CURRENT_TASK", estado.get("tarea_actual")),
        # Se enumeran las tareas ya hechas, no solo un resumen en prosa: sin esa lista el siguiente
        # agente puede reconstruir trabajo terminado y presentarlo como nuevo.
        ("COMPLETED", " · ".join(filter(None, [
            estado.get("estado_ejecucion"),
            ("hechas: " + ", ".join(t["id"] for t in estado.get("trabajo_completado", [])))
            if estado.get("trabajo_completado") else "",
        ])) or "(nada completado todavia)"),
        ("EVIDENCE", estado.get("checkpoint")),
        ("TESTS", v.get("tests")),
        ("QUALITY_GATE", v.get("quality_gate")),
        ("COMMIT", g.get("ultimo_commit")),
        ("FILES_CHANGED", g.get("ficheros_modificados")),
        ("DECISIONS_PENDING", estado.get("decisiones_pendientes")),
        ("BLOCKERS", estado.get("motivo_pausa")),
        ("QUOTA_STATE", (f"usage_known: {str(c.get('usage_known')).lower()} · "
                         f"rolling_window: {(c.get('rolling_window') or {}).get('estado')} · "
                         f"weekly: {(c.get('weekly') or {}).get('estado')} · "
                         f"monthly_spend: {(c.get('monthly_spend') or {}).get('estado')} · "
                         f"renovacion: UNKNOWN (las tres ventanas son independientes)")),
        ("QUOTA_GROUPS", resumen_de_cuota(c)),
        ("NEXT_TASK", sig.get("descripcion") if isinstance(sig, dict) else sig),
        ("NEXT_TASK_RATIONALE", sig.get("motivo") if isinstance(sig, dict) else None),
    ]
    ancho = max(len(k) for k, _ in filas)
    cuerpo = "\n".join(f"{k.ljust(ancho)}  {_linea(val)}" for k, val in filas)
    return f"===== HANDOFF · {estado.get('actualizado')} =====\n{cuerpo}\n"


# ============================================================================== CLI --


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Development Control Plane (no forma parte de AURORA)")
    p.add_argument("orden", choices=["estado", "handoff", "cuota", "refrescar"])
    p.add_argument("--fichero", default=str(ESTADO_POR_DEFECTO))
    a = p.parse_args(argv)
    destino = pathlib.Path(a.fichero)

    if a.orden == "cuota":
        c = observar_cuota()
        c["rolling_window"] = estimar_ventana_movil()
        print(json.dumps(c, ensure_ascii=False, indent=2))
        return 0

    e = cargar(destino) or estado_inicial()
    if a.orden == "refrescar":
        e["git"] = observar_git(pathlib.Path(__file__).resolve().parents[2])
        e["cuota"] = observar_cuota()
        e["cuota"]["rolling_window"] = estimar_ventana_movil()
        guardar(e, destino)
        print(f"[estado] {destino}")
        return 0
    if a.orden == "handoff":
        print(render_handoff(e))
        return 0
    print(json.dumps(e, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ================================================================================================
# SELECCION AUTOMATICA DE LA SIGUIENTE TAREA AUTO (2026-08-25)
# ================================================================================================
# Cierra el unico hueco del ciclo autonomo. Todo lo demas ya existia: `debe_ejecutar` sabe si una
# tarea concreta puede correr; faltaba recorrer las candidatas y devolver la primera.
#
# NO INTRODUCE AUTORIDAD NUEVA, y esto es lo que hace que sea seguro: el selector **no decide** que
# es AUTO. Lee `tareas_AUTO` —que solo el CEO llena— y aplica `debe_ejecutar`, la regla ya aprobada.
# Si nadie autorizo nada, devuelve None. AURA no puede darse trabajo a si misma.


def siguiente_auto_con_motivo(estado: dict) -> tuple[dict | None, str]:
    """Devuelve `(tarea, motivo)`. La tarea es None si no hay ninguna ejecutable ahora.

    El motivo se devuelve SIEMPRE: detenerse en silencio es indistinguible de un fallo, y la
    siguiente sesion necesita saber por que no habia trabajo, no solo que no lo habia.
    """
    candidatas = estado.get("tareas_AUTO") or []
    if not candidatas:
        return None, ("no hay tareas AUTO autorizadas: la lista `tareas_AUTO` esta vacia. AURA no "
                      "se inventa trabajo — hace falta que el CEO autorice una tarea")
    motivos = []
    for tarea in candidatas:
        ident = tarea.get("id")
        if not ident:
            motivos.append("una entrada de tareas_AUTO no declara `id`: se ignora")
            continue
        puede, porque = debe_ejecutar(estado, ident)
        if puede:
            return tarea, f"{ident}: {porque}"
        motivos.append(f"{ident}: {porque}")
    return None, " · ".join(motivos)


def siguiente_auto(estado: dict) -> dict | None:
    """Como `siguiente_auto_con_motivo`, pero solo la tarea. Para quien no necesita el porque."""
    tarea, _ = siguiente_auto_con_motivo(estado)
    return tarea


# ================================================================================================
# DISCOVERY -> CLASSIFY -> PROPOSE (2026-08-25)
# ================================================================================================
# AURA puede DESCUBRIR trabajo. No puede AUTORIZARSELO.
#
# Esa frase es la arquitectura entera, y esta separada por ESCRITURA, no por buena intencion:
# `descubrir()` y `registrar_propuestas()` escriben en `propuestas`; **solo** `promover_a_auto()`
# toca `tareas_AUTO`, y exige una accion explicita con aprobador. Un descubridor que se saltase esto
# no estaria «tomando una decision»: estaria escribiendo en un sitio donde no tiene permiso, y las
# pruebas lo detectan por igualdad exacta de la lista.

#: Las zonas bloqueadas NO se cablean aqui. Viven en `estado.json`, que es donde el CEO registra sus
#: decisiones — y ademas el Control Plane tiene prohibido nombrar artefactos del producto, garantia
#: que `test_el_control_plane_no_importa_nada_del_producto` protege y que un literal habria roto.
#: **Fail-closed**: si el estado no declara ninguna zona, TODO hallazgo es DECISION_REQUIRED, porque
#: no poder comprobar si algo esta bloqueado no es lo mismo que saber que no lo esta.
_CLAVE_ZONAS = "zonas_bloqueadas_para_discovery"

#: Fichero que la resolucion tendria que MODIFICAR, distinto del fichero que la comprueba. Se
#: DECLARA, nunca se deriva: no existe ninguna fuente contractual que mapee una prueba roja al
#: fichero de produccion que hay que cambiar, y deducirlo del nombre del test seria la heuristica
#: que la decision del CEO prohibe expresamente. Su ausencia es fail-closed.
_CAMPO_TRABAJO = "fichero_de_trabajo"

#: Origenes de evidencia que el descubridor sabe interpretar. Cualquier otro es DECISION_REQUIRED.
_ORIGENES = ("defecto", "red_roja", "mutante_superviviente", "gate_fallido")

#: Vocabulario CERRADO de apertura de un defecto (DEC-DEFECTO-ESTADO-ESTRUCTURADO, opcion B del CEO
#: 2026-08-25). La apertura es un DATO, no una narracion: vive en su propio campo y la prosa del
#: registro se conserva intacta sin que nadie la interprete.
APERTURAS = ("ABIERTO", "CERRADO", "OBSERVACION", "NO_CONSTA")

#: Campo estructurado que declara la apertura. Su ausencia significa NO_CONSTA.
_CAMPO_APERTURA = "apertura"


def apertura_de(defecto: dict) -> str:
    """`ABIERTO` · `CERRADO` · `OBSERVACION` · `NO_CONSTA`. **Determinista y sin interpretacion.**

    Lee UN campo y compara contra un vocabulario cerrado. No mira la prosa, no busca subcadenas, no
    infiere: `DEF-CUERPO-LIBRE` dice literalmente *«VECTOR 1 CONFIRMADO ABIERTO; vectores 2-4 sin
    analizar»*, y ninguna de esas palabras puede abrir un defecto.

    **Ausencia y valor no reconocido colapsan ambos a `NO_CONSTA`, nunca a `ABIERTO`.** Un registro
    escrito antes de este mecanismo no afirmo nada sobre su apertura; suponerlo seria inventarlo, y
    ese es exactamente el fallo que la decision del CEO prohibe.
    """
    valor = (defecto or {}).get(_CAMPO_APERTURA)
    return valor if valor in APERTURAS else "NO_CONSTA"


class PromocionInvalida(Exception):
    """Se intento introducir en `tareas_AUTO` algo que no puede entrar ahi."""


def _normalizar(texto: str) -> str:
    """Minusculas y sin separadores. `D-CP-8`, `d_cp_8` y `DCP8` colapsan al mismo `dcp8`."""
    return "".join(c for c in str(texto).lower() if c.isalnum())


def _fragmentos(texto: str) -> set[str]:
    """Trocea por separadores y devuelve tambien las concatenaciones de tokens CONSECUTIVOS.

    Por que no basta con normalizar el texto entero y buscar dentro: `dcp8` aparece como subcadena
    de `mdcp8x`, que es otro identificador. Y por que no basta con los tokens sueltos: `d_cp_8` se
    trocea en `d`,`cp`,`8` y ninguno es `dcp8`. Las concatenaciones de tokens contiguos resuelven
    ambos casos sin recurrir a coincidencia aproximada, que era el otro riesgo.
    """
    crudos = [t for t in re.split(r"[^0-9A-Za-z]+", str(texto)) if t]
    piezas = set()
    for i in range(len(crudos)):
        for j in range(i + 1, min(i + 5, len(crudos)) + 1):   # hasta 4 tokens contiguos
            piezas.add(_normalizar("".join(crudos[i:j])))
    return piezas


def _toca_zona_bloqueada(hallazgo: dict, estado: dict | None = None) -> bool:
    """¿El hallazgo cae en una zona que el CEO declaro bloqueada? Sin lista declarada -> True.

    **Corregido 2026-08-25.** El matching era por substring exacto y fallaba en los dos sentidos:
    `'d-cp-8' in 'dcp8_cableado'` era False —un hallazgo de zona vetada pasaba como ejecutable— y a
    la vez `'d-cp-8' in 'md-cp-8x'` era True, bloqueando un identificador ajeno. La comparacion es
    ahora entre fragmentos NORMALIZADOS, determinista y sin coincidencia aproximada.
    """
    zonas = (estado or {}).get(_CLAVE_ZONAS)
    if not zonas:
        return True
    # DEC-ZONA-POR-FICHERO-DE-TRABAJO (2026-08-25). La zona protege el TRABAJO, no el fichero que
    # lo comprueba. Cuando el hallazgo declara donde esta el trabajo, **manda el trabajo**: los 11
    # rojos de Linea A tienen su prueba fuera de toda zona y su trabajo DENTRO de una zona vetada
    # que el estado declara. Mirando la prueba salian AUTO_EXECUTABLE.
    # Si NADIE lo declara, se evalua lo unico que se sabe —donde esta la prueba—, que es la
    # contencion anterior y no se retira. `clasificar` impide ademas que esa ignorancia llegue a AUTO.
    trabajo = hallazgo.get(_CAMPO_TRABAJO)
    if trabajo:
        texto = str(trabajo)
    else:
        texto = " ".join(str(hallazgo.get(k, ""))
                         for k in ("ref", "fichero", "prueba", "descripcion"))
    piezas = _fragmentos(texto)
    return any(_normalizar(z) in piezas for z in zonas)


def descubrir(estado: dict, evidencia: dict | None = None) -> list[dict]:
    """Recorre la evidencia OBJETIVA y devuelve hallazgos. **No escribe nada.**

    No mide: clasifica lo ya medido. Quien ejecuta pytest o el arnes de mutacion es quien mide, y su
    resultado se inyecta en `evidencia`. Separar medir de interpretar evita el defecto que este
    proyecto ya conoce —un arnes que decide por el texto de una salida en vez de por su returncode—.

    **Sin evidencia devuelve lista vacia.** No se inventa trabajo para no quedarse quieto.
    """
    ev = evidencia or {}
    hallazgos = []
    for d in estado.get("defectos") or []:
        # `apertura_de` sustituye al filtro anterior sobre el campo `estado`, que era prosa libre.
        # Efecto buscado sobre los registros historicos: NO_CONSTA -> siguen sin descubrirse, pero
        # ahora por una regla declarada en vez de por que su texto no coincidia con un literal.
        if not isinstance(d, dict) or apertura_de(d) != "ABIERTO":
            continue
        hallazgos.append({"origen": "defecto", "ref": d.get("id"), "fichero": d.get("fichero"),
                          "prueba": d.get("prueba"), "descripcion": d.get("descripcion"),
                          _CAMPO_TRABAJO: d.get(_CAMPO_TRABAJO),
                          "determinado_por": "contrato existente"})
    for r in ev.get("reds_rojas") or []:
        hallazgos.append({"origen": "red_roja", "ref": r.get("nodeid"),
                          "fichero": r.get("fichero"), "prueba": r.get("nodeid"),
                          "descripcion": r.get("motivo"),
                          _CAMPO_TRABAJO: r.get(_CAMPO_TRABAJO),
                          "determinado_por": "contrato existente"})
    for m in ev.get("mutantes_supervivientes") or []:
        # Un superviviente admite mas de una resolucion —falta prueba, mutante mal construido o
        # garantia descubierta—, asi que nunca se da por determinado.
        hallazgos.append({"origen": "mutante_superviviente", "ref": m.get("id"),
                          "fichero": m.get("bateria"), "descripcion": "mutante superviviente",
                          "determinado_por": None, "resoluciones_posibles": 3})
    for g in ev.get("gates_fallidos") or []:
        hallazgos.append({"origen": "gate_fallido", "ref": g.get("gate"),
                          "descripcion": g.get("motivo"), "determinado_por": None,
                          "resoluciones_posibles": 2})
    return hallazgos


def clasificar(hallazgo: dict, estado: dict | None = None) -> str:
    """`AUTO_EXECUTABLE` · `PROPOSAL_ONLY` · `DECISION_REQUIRED`. **Fail-closed.**

    Lo que no se entiende no degrada en permiso: un hallazgo sin origen conocido, sin referencia o
    que toque una zona bloqueada se clasifica como `DECISION_REQUIRED`, nunca al reves.
    """
    if not isinstance(hallazgo, dict) or hallazgo.get("origen") not in _ORIGENES:
        return "DECISION_REQUIRED"
    if not hallazgo.get("ref"):
        return "DECISION_REQUIRED"
    if _toca_zona_bloqueada(hallazgo, estado):
        return "DECISION_REQUIRED"
    # CONTENCION (CEO 2026-08-25, condicion de seguridad de la opcion B). MEDIDO en el DP: un
    # defecto sin `fichero` ni `prueba` deja VACIO el texto sobre el que se calculan las zonas
    # bloqueadas, ninguna zona coincide, y la clasificacion caia en AUTO_EXECUTABLE. Es decir: la
    # falta de informacion actuaba como permiso. Un trabajo que no se sabe DONDE esta ni QUE lo
    # verifica no esta determinado, por definicion, y no puede ejecutarse solo.
    # No introduce un nivel nuevo: cae en `PROPOSAL_ONLY`, que ya exige aprobacion expresa del CEO.
    if not (hallazgo.get("fichero") and hallazgo.get("prueba")):
        return "PROPOSAL_ONLY"
    # No saber que fichero habria que tocar no es un detalle: es no poder comprobar en que zona cae
    # el trabajo. Esa ignorancia no puede valer como permiso — es la misma regla que ya rige para
    # `apertura`, aplicada al dato que decide la contencion.
    if not hallazgo.get(_CAMPO_TRABAJO):
        return "PROPOSAL_ONLY"
    if hallazgo.get("determinado_por") and not hallazgo.get("resoluciones_posibles"):
        return "AUTO_EXECUTABLE"
    return "PROPOSAL_ONLY"


def registrar_propuestas(estado: dict, hallazgos: list[dict]) -> dict:
    """Anota los hallazgos en `propuestas`. **Idempotente**: repetir el descubrimiento no duplica.

    La identidad de una propuesta es `origen:ref`, no su posicion ni el momento: dos pasadas sobre
    la misma evidencia describen el mismo trabajo, y duplicarlo inflaria el backlog con ruido.
    """
    propuestas = list(estado.get("propuestas") or [])
    conocidas = {p["id"] for p in propuestas}
    for h in hallazgos:
        ident = f"{h.get('origen')}:{h.get('ref')}"
        if ident in conocidas:
            continue
        conocidas.add(ident)
        propuestas.append({"id": ident, "origen": h.get("origen"), "ref": h.get("ref"),
                           "fichero": h.get("fichero"), "prueba": h.get("prueba"),
                           "explicacion": h.get("descripcion"),
                           "clasificacion": clasificar(h, estado), "estado": "PROPUESTA",
                           "evidencia": {k: v for k, v in h.items() if k != "descripcion"}})
    estado["propuestas"] = propuestas
    return estado


def _evidencia_sigue_existiendo(estado: dict, propuesta: dict) -> bool:
    """Una propuesta cuya evidencia desaparecio describe trabajo fantasma: no puede promoverse."""
    if propuesta.get("origen") == "defecto":
        return any(isinstance(d, dict) and d.get("id") == propuesta.get("ref")
                   for d in estado.get("defectos") or [])
    return True     # el resto se midio fuera; su vigencia la acredita quien vuelva a medir


def promover_a_auto(estado: dict, id_propuesta: str, aprobado_por: str,
                    aprobacion_expresa: bool = False) -> dict:
    """**La UNICA via hacia `tareas_AUTO`**, y exige una accion humana explicita.

    Revalida el hallazgo en el momento de promover, no confia en la clasificacion guardada: entre el
    descubrimiento y la promocion pueden haber cambiado el contrato o la propia evidencia.

    · `DECISION_REQUIRED` no se promueve **nunca**.
    · `PROPOSAL_ONLY` exige `aprobacion_expresa=True`: admite mas de una resolucion valida y elegir
      una es del CEO.
    · Si la evidencia ya no existe, falla cerrada.
    """
    if not aprobado_por:
        raise PromocionInvalida("una promocion sin aprobador no es una decision humana")
    propuestas = estado.get("propuestas") or []
    p = next((x for x in propuestas if x.get("id") == id_propuesta), None)
    if p is None:
        raise PromocionInvalida(f"no existe la propuesta {id_propuesta!r}")
    if p.get("estado") == "PROMOVIDA":
        raise PromocionInvalida(f"la propuesta {id_propuesta!r} ya fue promovida")
    clase = clasificar(p.get("evidencia") or p, estado)
    if clase == "DECISION_REQUIRED":
        raise PromocionInvalida(
            f"{id_propuesta!r} es DECISION_REQUIRED: toca una zona bloqueada o no esta determinada")
    if clase == "PROPOSAL_ONLY" and not aprobacion_expresa:
        raise PromocionInvalida(
            f"{id_propuesta!r} admite mas de una resolucion valida: exige aprobacion expresa")
    if not _evidencia_sigue_existiendo(estado, p):
        raise PromocionInvalida(
            f"la evidencia de {id_propuesta!r} ya no existe: seria trabajo fantasma")
    estado["tareas_AUTO"] = list(estado.get("tareas_AUTO") or []) + [{
        "id": p.get("ref"), "descripcion": p.get("explicacion") or p.get("ref"),
        "origen_propuesta": id_propuesta, "aprobado_por": aprobado_por,
        "clasificacion": clase, "promovida": _ahora()}]
    for x in estado["propuestas"]:
        if x.get("id") == id_propuesta:
            x["estado"] = "PROMOVIDA"
            x["aprobado_por"] = aprobado_por
    return estado

def confirmar_checkpoint(estado: dict, documento: pathlib.Path) -> dict:
    """Registra que el checkpoint fue RELEIDO, sellando la version leida.

    `checkpoint_sin_cambios()` avisa cuando el documento cambio desde que se escribio el estado.
    Faltaba la operacion inversa: sin ella el aviso se queda encendido para siempre, y **una alarma
    que suena siempre deja de informar** — medido en tres sesiones seguidas.

    No silencia el futuro: acredita **una version concreta**. Si el documento vuelve a cambiar, el
    aviso reaparece, que es justo lo que debe pasar.

    **Fail-closed**: no se acredita la lectura de un documento que no existe; seria fabricar
    evidencia de haber leido algo inexistente. Y no toca `tareas_AUTO`: leer no autoriza.
    """
    lectura = leer_checkpoint(documento)
    if not lectura.get("existe"):
        raise ValueError(
            f"no se puede confirmar la lectura de {documento}: el documento no existe")
    estado["checkpoint"] = lectura
    return estado



def trazabilidad(estado: dict, id_trabajo: str) -> dict:
    """Deriva `hallazgo -> propuesta -> promocion -> tarea -> resultado` **en consulta**.

    Decision del CEO 2026-08-25, **opcion A**: el vinculo NO se duplica dentro de
    `trabajo_completado` ni se migra la historia. Ya vive repartido entre `tareas_AUTO`
    (`origen_propuesta`, `aprobado_por`) y `propuestas`; esta funcion solo lo recompone.

    **Un trabajo sin procedencia no es un error**: es anterior al mecanismo de propuestas.
    Se devuelve identificado como tal, nunca enlazado a la fuerza — inventarle un origen seria
    fabricar procedencia, que es exactamente lo que la decision prohibe.

    `coherente` responde a algo distinto de `tiene_procedencia`: una tarea puede declarar un
    `origen_propuesta` que ya no exista, y entonces la cadena esta **rota**, no ausente. Confundir
    ambas cosas ocultaria justo el caso que hay que ver.
    """
    trabajo = next((t for t in estado.get("trabajo_completado") or []
                    if isinstance(t, dict) and t.get("id") == id_trabajo), None)
    base = {"trabajo": id_trabajo, "completado": trabajo is not None,
            "tiene_procedencia": False, "propuesta": None, "origen": None, "ref": None,
            "aprobado_por": None, "coherente": None, "motivo": ""}
    if trabajo is None:
        base["motivo"] = f"no consta ningun trabajo completado con id {id_trabajo!r}"
        return base
    tarea = next((t for t in estado.get("tareas_AUTO") or []
                  if isinstance(t, dict) and t.get("id") == id_trabajo), None)
    if tarea is None or not tarea.get("origen_propuesta"):
        base["motivo"] = ("trabajo sin procedencia registrada: es anterior al mecanismo de "
                          "propuestas. No se le inventa un origen")
        return base
    id_prop = tarea["origen_propuesta"]
    prop = next((p for p in estado.get("propuestas") or []
                 if isinstance(p, dict) and p.get("id") == id_prop), None)
    base.update({"tiene_procedencia": True, "propuesta": id_prop,
                 "aprobado_por": tarea.get("aprobado_por")})
    if prop is None:
        base["coherente"] = False
        base["motivo"] = (f"la tarea declara la propuesta {id_prop!r}, que no existe: la cadena "
                          f"esta rota, no ausente")
        return base
    base.update({"origen": prop.get("origen"), "ref": prop.get("ref"), "coherente": True,
                 "motivo": "cadena completa: propuesta -> promocion -> tarea -> resultado"})
    return base


# ============================================================================================ --
# DP-DEVELOPMENT-ORCHESTRATOR · FASE 1 = C1 + C2
#
# Tres cambios, **todos aditivos** (`§9`). Cierran tres defectos que el DP midio `[EJEC]`, no
# supuso:
#
# - **P3** — «`estado.json` se sobrescribe entero en cada guardado»: no habia historia. Ahora la
#   historia es `eventos.jsonl`, append-only, y `estado.json` pasa a ser **proyeccion**.
# - **P2** — «si dos procesos cargan y guardan, el ultimo gana y el otro pierde sus cambios en
#   silencio»: no habia lock. Ahora `flock` envuelve leer-modificar-escribir.
# - **P4** — «nada impide pasar de `COMPLETED` a `WORKING`»: no habia gobierno. Ahora la tabla de
#   `§6` decide, y toda transicion exige **autoridad y causa**.
#
# Sigue siendo infraestructura de desarrollo: **no concede ninguna capacidad a AURORA** y no importa
# un solo modulo del producto.
# ============================================================================================ --

NOMBRE_EVENTOS = "eventos.jsonl"
NOMBRE_CENTINELA = ".control-plane.lock"

# Octavo estado del vocabulario, anadido por `§6`: «Se conserva el vocabulario existente y se anade
# **un solo estado**, `WAITING_FOR_REVIEW`».
ESTADO_REVISION = "WAITING_FOR_REVIEW"
if ESTADO_REVISION not in ESTADOS:
    ESTADOS = ESTADOS + (ESTADO_REVISION,)

# Tabla de `§6`, replicando `estado_operativo.py`. `COMPLETED` **no figura como origen de ninguna
# transicion**: es final. Reabrir una tarea cerrada sin declarar por que es exactamente lo que el
# producto ya prohibe.
TRANSICIONES = {
    "WAITING_FOR_NEXT_TASK": ("WORKING",),
    # Literalmente la de `§6`. `WAITING_FOR_HUMAN` **no** figura aqui como destino aunque el DP le
    # de salidas, y eso lo deja inalcanzable desde el flujo. Se detecto al corregir el hallazgo 2 de
    # la auditoria y **no se enmienda por cuenta propia**: anadirlo en silencio seria decidir por el
    # CEO sobre su propia tabla. Queda registrado como observacion en el cierre de F1.
    "WORKING": (ESTADO_REVISION, "WAITING_FOR_ENVIRONMENT", "WAITING_FOR_QUOTA",
                "DECISION_REQUIRED", "FAILED", "COMPLETED"),
    ESTADO_REVISION: ("WORKING", "DECISION_REQUIRED", "COMPLETED", "FAILED"),
    "WAITING_FOR_ENVIRONMENT": ("WORKING", "FAILED"),
    "WAITING_FOR_QUOTA": ("WORKING", "FAILED"),
    "DECISION_REQUIRED": ("WORKING", "FAILED"),
    "WAITING_FOR_HUMAN": ("WORKING", "FAILED"),
    "COMPLETED": (),
    "FAILED": ("WORKING",),
}

# `§6`: «Salir de `DECISION_REQUIRED` exige un evento de **autoridad humana**, con su registro.
# **Ningun adaptador puede producirlo.**» La lista es cerrada a proposito: si bastara con declararse
# humano, la garantia no existiria.
AUTORIDADES_HUMANAS = ("ceo", "humano")
ESTADOS_SOLO_HUMANO = ("DECISION_REQUIRED", "WAITING_FOR_HUMAN")


ESTADO_INICIAL_DE_TAREA = "WAITING_FOR_NEXT_TASK"

# Lo que devuelve `estado_de_tarea` cuando la tarea no consta. **No es un estado del flujo**: es su
# ausencia, y por eso no figura en `TRANSICIONES`.
ESTADO_SIN_REGISTRAR = "UNKNOWN"

# En que estados puede **aparecer** una tarea que aun no constaba. Crear no es transicionar, pero
# tampoco es poder empezar en cualquier sitio: `COMPLETED` exige haber trabajado, `WAITING_FOR_REVIEW`
# exige algo que revisar, y `DECISION_REQUIRED`/`WAITING_FOR_HUMAN` declaran una espera humana
# **sobre un trabajo en curso** — crearlas ya ahi fabricaria una decision pendiente que nadie pidio.
#
# Los cuatro creables son exactamente los que el uso legitimo necesita: `interrumpir` crea en
# WAITING_FOR_ENVIRONMENT / WAITING_FOR_QUOTA / FAILED, y `registrar_bloqueo_de_cuota` en
# WAITING_FOR_QUOTA, ambos sobre tareas que pueden no constar todavia.
ESTADOS_CREABLES = (ESTADO_INICIAL_DE_TAREA, "WORKING", "WAITING_FOR_ENVIRONMENT",
                    "WAITING_FOR_QUOTA", "FAILED")

# El unico tipo de evento que produce estado, y por eso el unico que no se acepta crudo.
_EVENTO_DE_ESTADO = "estado_de_tarea"

# Eventos que **conceden estado** y por eso no se registran en crudo. `estado_de_tarea` estaba desde
# F1; los dos del criterio se anadieron el 2026-08-30 porque una segunda auditoria independiente
# cerro una tarea a `COMPLETED` fabricandolos a mano: conceden exactamente lo mismo que el primero,
# asi que gobernarlos menos era dejar la misma puerta con otro nombre.
EVENTOS_GOBERNADOS = frozenset({_EVENTO_DE_ESTADO, "criterio_fijado", "criterio_verificado",
                                "cuota_observada"})

# **Una sola lista, y la declara el modulo.** Estaba escrita a mano dentro de una prueba de F1, y
# cuando hizo falta barrer «todas las vias publicas a COMPLETED» se escribio OTRA lista, mas corta:
# `completar_tarea` y `fijar_estado_tarea` quedaron fuera y una auditoria las cerro en un intento.
# Dos listas del mismo hecho es el defecto del `§0` del CHECKPOINT; aqui costo repetir el mismo fallo
# dos veces en el mismo incremento.
FUNCIONES_GOBERNADAS = frozenset({
    # `control_plane`
    "fijar_estado_tarea", "completar_tarea", "transicion", "reconciliar_tras_caida",
    "interrumpir", "registrar_bloqueo_de_cuota", "validar_transicion",
    "_registrar_evento_gobernado", "registrar_criterio_fijado", "registrar_criterio_verificado",
    # `agentes` — el barrido dejo de mirar solo este modulo tras la 3.a auditoria
    "cerrar_tarea", "ejecutar_tarea",
})

# Funciones que **nombran** COMPLETED sin concederlo: unas lo leen, otras lo rechazan. Se declaran
# una a una para que el meta-control pueda distinguir «clasificada a proposito» de «se me paso».
# Enumerarlas es barato; que una concesion se cuele por no estar en ninguna lista sale caro y ya
# ocurrio dos veces.
NO_CONCEDEN_ESTADO = frozenset({
    "estado_de_tarea",      # lee
    "debe_ejecutar",        # lee y decide si tocaria ejecutar
    "render_handoff",       # presenta
    "informe_estado",       # presenta
    "validar_tareas",       # valida el borde de persistencia: solo lanza, nunca concede
    "_exigir_humano_para_completar",   # rechaza; es la puerta, no lo que la cruza
    "registrar_evento",     # primitiva publica: NIEGA los eventos que conceden estado
    "pedir_revision",       # mueve a WAITING_FOR_REVIEW o DECISION_REQUIRED; nunca a COMPLETED
    "esperar_por_cuota",    # mueve a WAITING_FOR_QUOTA; nunca a COMPLETED
    # La maquinaria de vigilancia. **Nombra** las señales porque su trabajo es encontrarlas, asi que
    # se delata sola en cuanto el barrido se amplio a las privadas. Inspecciona; no concede nada.
    "modulos_vigilados", "invocables_vigilados", "invocables_sin_clasificar",
    "parece_conceder_estado", "es_invocable_vigilable", "invocables_de",
    "cargar",               # lee del disco
    "validar_tareas",       # ya estaba: valida el borde y rechaza
    "cuota_observada_de",   # lee
    # La consola de observabilidad. **Nombra** el vocabulario de estados de tarea porque su trabajo
    # es explicar por que NO lo compara con el del ciclo —son dos ejes distintos—, y el barrido la
    # delata por eso mismo. Lee dos fuentes y enumera donde discrepan; no concede nada, no escribe
    # nada, y una prueba sobre su arbol sintactico lo comprueba
    # (`test_red_observatorio.py::test_el_observatorio_NO_PUEDE_escribir`).
    "_contradicciones",
})

# **Residual declarado, no cerrado.** `_registrar_sin_lock` es el escritor del fichero: le da igual
# lo que escriba, porque es la mano que sostiene el boligrafo. No se puede gobernar desde dentro del
# proceso —quien puede importarla puede tambien abrir `eventos.jsonl` con un editor de texto—, y
# fingir que si seria exactamente lo que este proyecto llama «declarado != real».
#
# Lo que el modulo **si** garantiza, y es lo que hay que leer aqui:
#
# 1. Ninguna ruta **publica** concede estado sin gobierno. Eso se prueba, y es lo que cerraron las
#    tres auditorias.
# 2. La cadena de `sha256` es **verificable**: `verificar_integridad_log()` detecta cualquier linea
#    alterada o suprimida. Una escritura cruda no pasa desapercibida; lo que no puede es impedirse.
# 3. El worker sub-invocado **no tiene** permiso de escritura sobre `entorno/control-plane/` — el
#    criterio A6, medido `[EJEC]`. Ese es el actor del que este diseno protege.
#
# Lo que NO se afirma: que un proceso con acceso normal al sistema de ficheros no pueda forjar el
# log. Puede. Se declara aqui, en el cierre y en el CHECKPOINT, porque un residual que solo consta
# en el docstring de una prueba no lo conoce quien lee el cierre.
ESCRITORES_CRUDOS = frozenset({
    "_registrar_sin_lock",
    # `guardar` y `actualizar_estado` escriben el modelo en memoria a disco. **Ya no son una ruta
    # libre** —`validar_tareas()` rechaza un COMPLETED sin autoridad humana, que es lo mismo que
    # exigen `completar_tarea` y `fijar_estado_tarea`—, pero siguen siendo escritores: se declaran
    # aqui para que consten y no vuelvan a quedar fuera de toda lista, que fue como se colaron.
    "guardar", "actualizar_estado",
})


# Que puerta gobernada corresponde a cada evento. Un mensaje de error que dice «esto no» sin decir
# «esto si» empuja a quien lo lee a buscarse la vida, y buscarse la vida es como nacen las rutas
# alternativas.
_PUERTA_DE = {
    "estado_de_tarea": "transicion() o reconciliar_tras_caida()",
    "criterio_fijado": "registrar_criterio_fijado()",
    "criterio_verificado": "registrar_criterio_verificado()",
    "cuota_observada": "esperar_por_cuota()",
}


class EscrituraDeProduccionProhibida(RuntimeError):
    """Una prueba intento escribir sobre el estado **real** del Control Plane.

    No es una precaucion teorica: el 2026-08-26 una prueba de F1 recorrio las funciones publicas de
    este modulo y llamo a `guardar()` sin destino —cuyo valor por defecto es el estado de
    produccion—, destruyendo informacion historica que solo pudo restaurarse en parte.

    El bloqueo lo **arma el `conftest.py`** durante las pruebas, no el modulo: en produccion escribir
    ahi es exactamente lo que hay que hacer."""


class TransicionInvalida(ValueError):
    """Se rechaza una transicion. **Fail-closed**: si no consta que sea legal, no ocurre.

    Hereda de `ValueError` porque un estado prohibido **es** un valor invalido: quien ya capturaba
    `ValueError` de `fijar_estado_tarea` sigue capturandolo. Endurecer una garantia no deberia
    obligar a reescribir el manejo de errores de quien la usaba bien."""


class CriterioNoVerificado(TransicionInvalida):
    """Se intento cerrar una tarea como `COMPLETED` sin que su criterio mecanico se haya ejecutado
    con exito, y sin autoridad humana que lo respalde.

    **Vive aqui, en la primitiva, y no en quien la llama.** La puerta estuvo un rato en
    `agentes.cerrar_tarea`, y una auditoria independiente demostro que `transicion()` la esquivaba
    sin esfuerzo: es la primitiva que usa toda la base, incluida `agentes.py`. `ALERTA-005` otra vez
    —*«toda ejecucion pasa por el motor unico; ninguna ruta alternativa»*—, y las 34 pruebas que
    entonces cubrian A12 no la veian porque todas entraban por la puerta que yo habia puesto."""


def modulos_del_plano() -> tuple[str, ...]:
    """Los modulos del plano, **leidos del directorio**.

    Estaba escrito a mano, que es el defecto exacto que este trabajo lleva cuatro auditorias
    corrigiendo — y lo cometi una vez mas al ampliar el barrido. Si alguien anade un modulo y se
    olvida de la tupla, «no esta en la lista» vuelve a significar «nadie lo ha mirado».

    Se excluyen las pruebas, el `conftest` y los ficheros con guion en el nombre —no son importables
    como modulo— y esa exclusion es explicita, no un descarte silencioso."""
    base = pathlib.Path(__file__).resolve().parent
    return tuple(sorted(
        f.stem for f in base.glob("*.py")
        if not f.name.startswith(("test_", "conftest")) and "-" not in f.name))


def modulos_vigilados() -> list:
    """Los modulos que el meta-control recorre. Se importan al vuelo porque varios de ellos importan
    este: hacerlo arriba crearia un ciclo, y no cambia lo que se vigila."""
    import importlib
    vistos = []
    for nombre in modulos_del_plano():
        try:
            vistos.append(importlib.import_module(nombre))
        except Exception:                              # pragma: no cover - modulo no importable
            continue
    return vistos


def es_invocable_vigilable(objeto) -> bool:
    """Si el objeto ejecuta codigo propio que merezca inspeccionarse.

    Incluye `functools.partial`: `inspect.isfunction` devuelve `False` para uno, asi que una funcion
    gobernada envuelta y colgada de un modulo era invisible. Lo encontro la 4.a auditoria
    construyendo el caso, no leyendo el codigo."""
    import functools
    import inspect
    if isinstance(objeto, functools.partial):
        return True
    return inspect.isfunction(objeto) or inspect.ismethod(objeto)


def invocables_de(contenedor, prefijo: str, profundidad: int = 4) -> list:
    """Los invocables de una clase, **descendiendo a las clases anidadas**.

    El barrido recorria un solo nivel de `vars(clase)`, asi que una clase dentro de otra escondia sus
    metodos. La cota de profundidad existe para que un ciclo de referencias no lo cuelgue: acotado
    por construccion, como el bucle del `§14`."""
    import inspect
    hallados = []
    if profundidad <= 0:                               # pragma: no cover - cota defensiva
        return hallados
    for nombre, valor in vars(contenedor).items():
        if es_invocable_vigilable(valor):
            hallados.append((f"{prefijo}.{nombre}", valor))
        elif inspect.isclass(valor):
            hallados.extend(invocables_de(valor, f"{prefijo}.{nombre}", profundidad - 1))
    return hallados


def invocables_vigilados() -> list:
    """**Todo** lo invocable de esos modulos: funciones publicas, **privadas**, **metodos**,
    **metodos de clases anidadas** y **`functools.partial`**.

    Cada exclusion del barrido anterior se pago con una auditoria: `_` escondio la puerta interna,
    «solo funciones sueltas» escondia los metodos, «solo este modulo» escondia los otros seis, y
    `partial` y las clases anidadas los encontro la cuarta. Una lista de sitios donde mirar que
    excluye sitios no es un barrido: es una muestra."""
    import inspect
    encontrados = []
    for modulo in modulos_vigilados():
        for nombre, objeto in vars(modulo).items():
            propio = getattr(objeto, "__module__", None) == modulo.__name__
            if es_invocable_vigilable(objeto) and (propio or not inspect.isfunction(objeto)):
                encontrados.append((nombre, objeto))
            elif inspect.isclass(objeto) and propio:
                encontrados.extend(invocables_de(objeto, nombre))
    return encontrados


# Lo que hace sospechosa a una funcion. `ESTADO_FINAL` y las dos escrituras crudas estan aqui porque
# una funcion hostil no tiene por que escribir el literal: puede guardarlo en una constante, y la 3.a
# auditoria lo demostro construyendo exactamente ese caso.
SEÑALES_DE_CONCESION = ("COMPLETED", "ESTADO_FINAL",
                        "_registrar_evento_gobernado", "_registrar_sin_lock")


def parece_conceder_estado(fuente: str) -> bool:
    """Predicado del barrido, **expuesto para poder ejercitarlo**.

    Vivia dentro del bucle, asi que solo se probaba con el codigo que hubiera ese dia: el mutante que
    reducia las señales al literal sobrevivia porque hoy ninguna funcion real usa la constante. Fuera,
    se le puede dar fuente sintetica y comprobar que la reconoce."""
    return any(s in fuente for s in SEÑALES_DE_CONCESION) and "TRANSICIONES" not in fuente


def invocables_sin_clasificar() -> list:
    """Los que nombran el estado final y no estan declarados ni como gobernados ni como inocuos.

    Se busca el estado **por su constante ademas de por su literal**: la auditoria demostro que una
    funcion hostil puede escribir `ESTADO_FINAL = "COMPLETED"` y no aparecer en un `grep` del
    literal."""
    import inspect
    fuera = []
    for nombre, objeto in invocables_vigilados():
        corto = nombre.split(".")[-1]
        if corto in FUNCIONES_GOBERNADAS or corto in NO_CONCEDEN_ESTADO or corto in ESCRITORES_CRUDOS:
            continue
        import functools
        destino = objeto.func if isinstance(objeto, functools.partial) else objeto
        try:
            fuente = inspect.getsource(destino)
        except (OSError, TypeError):                   # pragma: no cover - defensivo
            continue
        if parece_conceder_estado(fuente):
            fuera.append(nombre)
    return sorted(fuera)


class EventoNoGobernado(TransicionInvalida):
    """Se intento registrar en crudo un evento que **concede estado**. Hay una funcion gobernada para
    cada uno, y pasar por ella es lo que deja autoridad, causa y validacion en el historial.

    Hereda de `TransicionInvalida` —que a su vez es `ValueError`— porque **es** una transicion
    invalida, rechazada por un motivo mas preciso. Quien ya capturaba el rechazo generico sigue
    capturandolo: endurecer una garantia no puede romper a quien la respetaba."""


class VentanaIndeterminada(ValueError):
    """Se intento aparcar una tarea en `WAITING_FOR_QUOTA` sin saber que ventana se agoto.

    `§11`: *«si no puede determinarse la ventana, `UNKNOWN` · **`UNKNOWN` nunca se convierte en
    `WAITING_FOR_QUOTA`**»*. Y el motivo es el mismo que sostiene el apartado entero:
    `WAITING_FOR_QUOTA` **afirma** que una cuota concreta bloqueo el trabajo y que se renovara. Con
    `UNKNOWN` no se sabe ni que se agoto ni si se renovara, asi que declararlo seria fabricar una
    explicacion. Lo honesto para «algo fallo y no se que» es `FAILED`, que no promete ninguna
    renovacion — y de `FAILED` se puede volver a `WORKING`."""


class LogCorrupto(RuntimeError):
    """Una linea del log no es legible y **no es la ultima**. Una escritura interrumpida solo puede
    partir la ultima, asi que esto no es una caida: es manipulacion, y no se repara sola."""


def ruta_eventos(directorio: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(directorio) / NOMBRE_EVENTOS


def ruta_centinela(directorio: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(directorio) / NOMBRE_CENTINELA


@contextlib.contextmanager
def lock_estado(directorio: pathlib.Path):
    """**C2 · cierra P2.** `flock` exclusivo sobre un centinela, alrededor de leer-modificar-escribir.

    El centinela es un fichero aparte y **nunca se borra**: soltar el lock borrando el fichero es la
    forma clasica de que dos procesos acaben sosteniendo locks sobre inodos distintos y crean ambos
    que lo tienen. Se libera siempre, incluso si el bloque lanza — un lock que no se suelta convierte
    el primer fallo en un interbloqueo permanente."""
    centinela = ruta_centinela(directorio)
    centinela.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(centinela, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield centinela
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def huella_de_criterio(criterio: dict) -> str:
    """`sha256` del criterio canonicalizado. **La calcula la puerta**, no quien la cruza.

    Aceptarla como parametro dejaba fijar un criterio con una huella arbitraria y verificar despues
    esa misma huella: dos llamadas legitimas, encadenadas, cerraban la tarea sin que el criterio
    tuviera nada que ver con lo que se comprobo. Lo destapo el barrido ampliado tras la 3.a
    auditoria — no una prueba escrita a proposito para ello, sino el barrido recorriendo rutas
    nuevas—. Derivada aqui, huella y criterio no se pueden separar."""
    return hashlib.sha256(
        json.dumps(criterio, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def registrar_criterio_fijado(directorio: pathlib.Path, id_tarea: str, criterio: dict) -> dict:
    """La puerta gobernada del evento `criterio_fijado`. Existe para que `registrar_evento` pueda
    negarse a la via cruda **y ofrecer una salida**: un «esto no» sin «esto si» empuja a quien lo lee
    a rodearlo, y asi nacen las rutas alternativas."""
    return _registrar_evento_gobernado(directorio, "criterio_fijado",
                                       {"id": id_tarea, "criterio": criterio,
                                        "huella": huella_de_criterio(criterio)})


def registrar_criterio_verificado(directorio: pathlib.Path, id_tarea: str, huella: str,
                                  verificado: bool, comprobacion: str = "") -> dict:
    """La puerta gobernada del evento `criterio_verificado`.

    Aqui la huella **si** es parametro, y a proposito: describe *que* criterio se ejecuto, y tiene
    que poder no coincidir para que `criterio_superado()` rechace una verificacion que no es la
    suya. Lo que no puede es inventarse en el lado del `criterio_fijado`, que es donde nace."""
    return _registrar_evento_gobernado(directorio, "criterio_verificado",
                                       {"id": id_tarea, "huella": huella,
                                        "verificado": bool(verificado),
                                        "comprobacion": comprobacion})


def esperar_por_cuota(directorio: pathlib.Path, id_tarea: str, *, ventana: str, autoridad: str,
                      evidencia: str) -> dict:
    """Aparca una tarea en `WAITING_FOR_QUOTA`, **solo con ventana determinada y evidencia leida**.

    Es la unica via que este modulo ofrece para ese estado, y existe para que la regla del `§11` no
    dependa de que quien llame a `transicion()` se acuerde: *«UNKNOWN nunca se convierte en
    WAITING_FOR_QUOTA»* es una garantia, no una recomendacion."""
    if ventana not in VENTANAS_CUOTA:
        raise ValueError(f"ventana de cuota desconocida: {ventana!r}; validas: {VENTANAS_CUOTA}")
    if ventana == "UNKNOWN":
        raise VentanaIndeterminada(
            f"no se aparca {id_tarea!r} en WAITING_FOR_QUOTA con la ventana sin determinar: ese "
            f"estado afirma que una cuota concreta bloqueo y que se renovara, y eso no consta. "
            f"Sin saber cual se agoto, el estado honesto es FAILED (§11)")
    if not (evidencia or "").strip():
        raise ValueError(
            "esperar por cuota exige la evidencia observada (§11: «ante evidencia REAL de "
            "agotamiento»). Sin el mensaje leido, la ventana se estaria deduciendo")
    _registrar_evento_gobernado(pathlib.Path(directorio), "cuota_observada",
                                {"id": id_tarea, "ventana": ventana, "evidencia": evidencia})
    return transicion(pathlib.Path(directorio), id_tarea, "WAITING_FOR_QUOTA", autoridad=autoridad,
                      causa=f"cuota {ventana} agotada · evidencia observada: {evidencia}")


def cuota_observada_de(directorio: pathlib.Path, id_tarea: str) -> dict | None:
    """La observacion de cuota registrada para esa tarea, si la hay."""
    vistas = [e["datos"] for e in leer_eventos(directorio)
              if e["tipo"] == "cuota_observada" and e["datos"].get("id") == id_tarea]
    return vistas[-1] if vistas else None


def criterio_fijado_de(directorio: pathlib.Path, id_tarea: str) -> dict | None:
    """El criterio mecanico fijado para una tarea, si lo hay. Se lee del log, que es donde vive: si
    viviera en la memoria de quien lo ejecuto, no habria nada que consultar al cerrar."""
    fijados = [e["datos"] for e in leer_eventos(directorio)
               if e["tipo"] == "criterio_fijado" and e["datos"].get("id") == id_tarea]
    return fijados[0] if fijados else None


def criterio_superado(directorio: pathlib.Path, id_tarea: str) -> bool:
    """`True` solo si el criterio fijado para esa tarea se **ejecuto** y **salio bien**.

    Haberlo ejecutado no basta: si valiera la mera ejecucion, bastaria lanzarlo y despreciar el
    resultado. Y la huella tiene que ser la **suya**: sin eso, verificar la tarea mas facil del ciclo
    abriria las demas."""
    fijado = criterio_fijado_de(directorio, id_tarea)
    if fijado is None:
        return False
    return any(e["tipo"] == "criterio_verificado"
               and e["datos"].get("id") == id_tarea
               and e["datos"].get("huella") == fijado["huella"]
               and e["datos"].get("verificado") is True
               for e in leer_eventos(directorio))


def _canonico(evento: dict) -> str:
    return json.dumps(evento, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_de(evento: dict) -> str:
    return hashlib.sha256(_canonico({k: v for k, v in evento.items()
                                     if k != "hash"}).encode("utf-8")).hexdigest()


def _leer_con_cola(directorio: pathlib.Path) -> tuple[list[dict], bool]:
    """Los eventos legibles y si la **ultima** linea quedo a medias.

    `§12` declara que una escritura de evidencia interrumpida se resuelve con *«linea descartada del
    log»*. No estaba implementado: un `json.loads` sin red hacia que una sola linea partida dejara
    ilegible el Control Plane entero —`leer_eventos`, `proyectar`, `verificar_integridad_log` y,
    lo peor, `registrar_evento`, asi que el sistema no podia ni anotar que estaba roto—.

    **Truncada no es lo mismo que alterada.** Solo la ultima linea puede quedar a medias por una
    caida: las anteriores ya estaban completas y con `fsync`. Una linea rota **en medio** no viene
    de un `SIGKILL`, viene de que alguien toco el fichero, y descartarla en silencio convertiria el
    log encadenado en un registro que se repara solo borrando lo que le estorba."""
    ruta = ruta_eventos(directorio)
    if not ruta.exists():
        return [], False
    lineas = [ln.strip() for ln in ruta.read_text(encoding="utf-8").splitlines() if ln.strip()]
    eventos: list[dict] = []
    for numero, linea in enumerate(lineas, 1):
        try:
            eventos.append(json.loads(linea))
        except json.JSONDecodeError as exc:
            if numero == len(lineas):
                return eventos, True                  # cola truncada: caida, se descarta
            raise LogCorrupto(                        # en medio: manipulacion, no se toca
                f"la linea {numero} de {len(lineas)} no es JSON valido y NO es la ultima: una "
                f"escritura interrumpida solo puede partir la ultima. Esto no es una caida ({exc})"
            ) from exc
    return eventos, False


def leer_eventos(directorio: pathlib.Path) -> list[dict]:
    """Historia completa, en orden. Que no exista es informacion, no motivo para fabricarla."""
    eventos, _ = _leer_con_cola(directorio)
    return eventos


def _retirar_cola_truncada(directorio: pathlib.Path, eventos: list[dict]) -> None:
    """Quita la linea partida **truncando el fichero**, sin tocar un solo byte anterior.

    Ignorarla al leer no basta: en cuanto se anada un evento nuevo dejaria de ser la ultima y pasaria
    a ser una linea rota **en medio**, que es el caso que si debe fallar.

    **Por que truncar y no reescribir.** `§5` dice de C1: *«Nunca: borrarse ni reescribirse»*.
    Regenerar el fichero desde los eventos leidos —aunque el contenido saliera igual— seria
    reescribir el log entero para arreglar su ultima linea, y bastaria que `_canonico` produjera un
    byte distinto del que se escribio para alterar la historia en silencio y romper los hashes.
    Truncar solo puede afectar a la cola: los bytes de los eventos ya cerrados son fisicamente
    inalcanzables. La linea partida no es un evento —es un fragmento de una escritura que nunca
    llego a serlo—, y por eso quitarla no contradice el append-only que C1 exige."""
    ruta = ruta_eventos(directorio)
    bruto = ruta.read_bytes()
    corte, vistas = 0, 0
    for linea in bruto.splitlines(keepends=True):
        if vistas == len(eventos):
            break
        if linea.strip():
            vistas += 1
        corte += len(linea)
    if corte < len(bruto):
        with open(ruta, "r+b") as fh:
            fh.truncate(corte)
            fh.flush()
            os.fsync(fh.fileno())


def _registrar_sin_lock(directorio: pathlib.Path, tipo: str, datos: dict | None) -> dict:
    previos, cola_truncada = _leer_con_cola(directorio)
    if cola_truncada:
        # El descarte es un hecho del sistema y va al propio historial: un log que se repara solo y
        # sin decirlo es un log en el que no se puede confiar.
        _retirar_cola_truncada(directorio, previos)
        previos = [_registrar_sin_lock(directorio, "linea_truncada_descartada",
                                       {"eventos_validos": len(previos)})]
        previos = leer_eventos(directorio)
    evento = {
        "seq": previos[-1]["seq"] + 1 if previos else 1,
        "tipo": tipo,
        "momento": _ahora(),
        "datos": datos or {},
        "hash_anterior": previos[-1]["hash"] if previos else None,
    }
    evento["hash"] = _hash_de(evento)
    ruta = ruta_eventos(directorio)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as fh:
        fh.write(_canonico(evento) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return evento


# Los unicos eventos cuya UNICA via legitima es esta puerta interna. `estado_de_tarea` NO esta:
# tiene un solo escritor, `transicion()`, que escribe dentro del lock y **despues** de validar la
# tabla, la autoridad y el criterio. Dejar que esta funcion lo aceptase era el bypass entero.
_EVENTOS_DE_ESTA_PUERTA = frozenset({"criterio_fijado", "criterio_verificado",
                                     "cuota_observada"})


def _registrar_evento_gobernado(directorio: pathlib.Path, tipo: str, datos: dict) -> dict:
    """Escribe un evento gobernado **desde su puerta**, y **solo los suyos**.

    La primera version aceptaba cualquier `tipo`. Una tercera auditoria independiente escribio con
    ella un `estado_de_tarea` con `valor="COMPLETED"`, sin autoridad ni criterio, y la proyeccion lo
    aplico como bueno con la cadena de hashes intacta: el bypass estaba **un nivel por debajo** de
    donde se habia cerrado la vez anterior.

    Que empiece por `_` no la protege —Python no impone privacidad— y confiar en el guion bajo era
    exactamente la clase de garantia que este proyecto llama «declarada, no real». La proteccion es
    esta lista, no el nombre."""
    if tipo not in _EVENTOS_DE_ESTA_PUERTA:
        raise EventoNoGobernado(
            f"{tipo!r} no se escribe por esta puerta; la suya es {_PUERTA_DE.get(tipo, 'ninguna')}. "
            f"Aqui solo pasan {sorted(_EVENTOS_DE_ESTA_PUERTA)}")
    directorio = pathlib.Path(directorio)
    with lock_estado(directorio):
        return _registrar_sin_lock(directorio, tipo, datos)


def registrar_evento(directorio: pathlib.Path, tipo: str, datos: dict | None = None) -> dict:
    """**C1 · cierra P3.** Anade una linea al log. Nunca reescribe ninguna anterior.

    `seq` monotonico y `hash_anterior` encadenado: firmar cada linea por separado detectaria una
    linea alterada, pero no una linea **eliminada**. La cadena detecta ambas."""
    if tipo in EVENTOS_GOBERNADOS:
        # Cuarta ruta, cerrada. `registrar_evento` es la primitiva del log, y a diferencia de
        # `guardar()` —que escribe lo que le den sin interpretarlo— este evento **produce estado**:
        # la proyeccion lo aplica como bueno. Si se aceptase a pelo, el gobierno de `transicion()`
        # seria decorativo, porque bastaria rodearlo.
        raise EventoNoGobernado(
            f"un evento {tipo!r} crudo fabricaria estado sin gobierno: "
            f"usa la funcion gobernada que le corresponde ({_PUERTA_DE[tipo]})")
    with lock_estado(directorio):
        return _registrar_sin_lock(directorio, tipo, datos)


def verificar_integridad_log(directorio: pathlib.Path) -> dict:
    """Recorre la cadena entera. Devuelve el primer punto de ruptura, no solo un booleano: saber
    *que* linea rompio es la diferencia entre poder investigar y solo saber que algo pasa."""
    eventos, cola_truncada = _leer_con_cola(directorio)
    anterior = None
    for i, evento in enumerate(eventos):
        esperado = i + 1
        if evento.get("seq") != esperado:
            return {"integro": False, "cola_truncada": cola_truncada, "seq": evento.get("seq"),
                    "motivo": f"la secuencia salta: se esperaba {esperado}"}
        if evento.get("hash_anterior") != anterior:
            return {"integro": False, "cola_truncada": cola_truncada, "seq": evento.get("seq"),
                    "motivo": "la cadena no enlaza con el evento anterior"}
        if evento.get("hash") != _hash_de(evento):
            return {"integro": False, "cola_truncada": cola_truncada, "seq": evento.get("seq"),
                    "motivo": "el contenido no coincide con su hash"}
        anterior = evento["hash"]
    return {"integro": True, "eventos": len(eventos), "cola_truncada": cola_truncada,
            "motivo": "cadena completa" + (" (con una cola truncada por descartar)"
                                           if cola_truncada else "")}


# ------------------------------------------------------------------ proyeccion (C2) --

def _base_proyeccion() -> dict:
    """Esqueleto **determinista**. No lleva `actualizado` ni `cuota`: ninguno de los dos deriva del
    log —son observacion del entorno— y meterlos haria que dos proyecciones del mismo log
    difirieran. Una proyeccion que no es funcion pura de su historia no es una proyeccion."""
    return {"version": VERSION, "status": ESTADO_INICIAL_DE_TAREA, "tareas": {},
            "eventos_aplicados": 0, "eventos_ignorados": []}


def _aplicar(proyeccion: dict, evento: dict) -> None:
    tipo = evento.get("tipo")
    datos = evento.get("datos") or {}
    if tipo == "tarea_registrada":
        proyeccion["tareas"].setdefault(datos["id"], {
            "estado": ESTADO_INICIAL_DE_TAREA, "descripcion": datos.get("descripcion", ""),
            "autoridad": None, "causa": "", "seq": evento["seq"]})
    elif tipo == _EVENTO_DE_ESTADO:
        tarea = proyeccion["tareas"].setdefault(datos["id"], {
            "estado": ESTADO_INICIAL_DE_TAREA, "descripcion": "", "autoridad": None,
            "causa": "", "seq": evento["seq"]})
        tarea.update({"estado": datos["valor"], "autoridad": datos.get("autoridad"),
                      "causa": datos.get("causa", ""), "seq": evento["seq"]})
    else:
        proyeccion["eventos_ignorados"].append(evento["seq"])
        return
    proyeccion["eventos_aplicados"] += 1


def proyectar(directorio: pathlib.Path) -> dict:
    """**C2 · `§9.1`.** Reconstruye el estado desde el log. Es el liston que ADR-0023 exige de toda
    proyeccion: *«debe poder eliminarse por completo y regenerarse desde el historial sin alterar el
    comportamiento»*. Borra `estado.json` y vuelve; editalo a mano y **manda el log**."""
    proyeccion = _base_proyeccion()
    for evento in leer_eventos(directorio):
        _aplicar(proyeccion, evento)
    return proyeccion


def estado_de(directorio: pathlib.Path, id_tarea: str) -> str:
    tarea = proyectar(directorio)["tareas"].get(id_tarea)
    return tarea["estado"] if tarea else "UNKNOWN"


# --------------------------------------------------- transiciones gobernadas (C2) --

def validar_transicion(previo: str, valor: str, autoridad: str, causa: str) -> None:
    """**C2 · cierra P4.** Lanza `TransicionInvalida` si no consta que la transicion sea legal.

    El orden importa: autoridad y causa se exigen **antes** de mirar la tabla, porque una transicion
    legal ejecutada por nadie y sin motivo sigue siendo una transicion que nadie puede auditar."""
    if not (autoridad or "").strip():
        raise TransicionInvalida("toda transicion exige autoridad: quien la ordena")
    if not (causa or "").strip():
        raise TransicionInvalida("toda transicion exige causa: por que ocurre")
    if valor not in ESTADOS:
        raise TransicionInvalida(f"estado desconocido: {valor!r}; validos: {ESTADOS}")
    if previo == ESTADO_SIN_REGISTRAR:
        # Una tarea sin estado previo se **crea**, no transiciona: no hay origen contra el que
        # validar. Autoridad y causa ya se han exigido arriba, que es lo que hace auditable el
        # registro exista o no un estado anterior.
        #
        # Pero crear **no es** poder empezar en cualquier estado. La segunda auditoria encontro que
        # este `return` saltaba tambien la tabla y el control humano, asi que cualquier id nunca
        # visto podia aparecer en `COMPLETED` con cualquier cadena por autoridad. Lo delato la
        # asimetria: `transicion()` lo rechazaba —«no se transiciona lo que no existe»— y esta ruta
        # no. Dos rutas al mismo estado con distinto rigor es ALERTA-005.
        #
        # Esta regla vive **solo aqui**. Estuvo un rato duplicada entre `fijar_estado_tarea` y
        # `completar_tarea`, y esa es exactamente la forma de defecto que el `§0` del CHECKPOINT
        # senala tras cinco auditorias: «una regla escrita dos veces».
        if valor not in ESTADOS_CREABLES:
            raise TransicionInvalida(
                f"no se puede crear una tarea directamente en {valor}: no consta ningun estado "
                f"previo, y solo se puede crear en {ESTADOS_CREABLES}")
        return
    if previo not in TRANSICIONES:
        raise TransicionInvalida(f"estado previo desconocido: {previo!r}")
    if previo in ESTADOS_SOLO_HUMANO and autoridad not in AUTORIDADES_HUMANAS:
        # **Antes** del atajo de idempotencia (hallazgo 3 de la auditoria). Colocado despues, un
        # adaptador podia re-afirmar `DECISION_REQUIRED` y reescribir con ello `autoridad` y
        # `causa`: el estado no cambiaba, pero si el registro de **quien** sostiene la espera — que
        # es justo lo que la hace auditable.
        raise TransicionInvalida(
            f"salir de {previo} exige autoridad humana registrada ({AUTORIDADES_HUMANAS}); "
            f"{autoridad!r} no lo es")
    if valor == previo:
        # Re-afirmar el estado en el que ya se esta **no es una transicion**: es idempotencia, la
        # misma que `completar_tarea` ya garantiza. La tabla de `§6` no lista X -> X porque describe
        # el *flujo*, no la repeticion; exigirlo alli romperia registrar dos veces el mismo bloqueo
        # de cuota sin proteger nada — el estado resultante es identico.
        return
    if valor not in TRANSICIONES[previo]:
        permitidos = TRANSICIONES[previo] or ("<ninguno: es final>",)
        raise TransicionInvalida(
            f"transicion prohibida {previo} -> {valor}; desde {previo} solo: {permitidos}")


def transicion(directorio: pathlib.Path, id_tarea: str, valor: str, *,
               autoridad: str, causa: str) -> dict:
    """Leer-validar-escribir **entero dentro del lock**. Validar fuera del lock y escribir dentro
    seria comprobar una precondicion que otro proceso puede invalidar entre medias: el defecto P2
    disfrazado de gobierno."""
    directorio = pathlib.Path(directorio)
    with lock_estado(directorio):
        proyeccion = _base_proyeccion()
        for evento in leer_eventos(directorio):
            _aplicar(proyeccion, evento)
        tarea = proyeccion["tareas"].get(id_tarea)
        if tarea is None:
            raise TransicionInvalida(
                f"la tarea {id_tarea!r} no consta registrada: no se transiciona lo que no existe")
        validar_transicion(tarea["estado"], valor, autoridad, causa)
        if valor == "WAITING_FOR_QUOTA":
            # `§11`, **en el motor y no en un envoltorio**. La leccion de las tres auditorias
            # anteriores era «la puerta va donde pasa todo el mundo», y aun asi puse `esperar_por_
            # cuota()` como envoltorio: `transicion()` seguia aceptando el estado con solo autoridad
            # y causa. Es `ALERTA-005` con otro estado, y la cuarta auditoria lo cerro en un intento.
            observada = cuota_observada_de(directorio, id_tarea)
            if observada is None or observada.get("ventana") in (None, "UNKNOWN") \
                    or not (observada.get("evidencia") or "").strip():
                raise VentanaIndeterminada(
                    f"no se aparca {id_tarea!r} en WAITING_FOR_QUOTA sin una observacion de cuota "
                    f"registrada con ventana determinada y evidencia leida (§11). La via es "
                    f"esperar_por_cuota()")
        if valor == "COMPLETED" and autoridad not in AUTORIDADES_HUMANAS:
            # `§14.bis` regla 3 y criterio `A12`, **en la primitiva**. Una autoridad no humana solo
            # cierra si el criterio mecanico se ejecuto y salio bien; `§14.bis` regla 4 dice que una
            # tarea sin criterio mecanico **no es AUTO**, luego solo puede cerrarla un acto humano.
            if not criterio_superado(directorio, id_tarea):
                raise CriterioNoVerificado(
                    f"no se cierra {id_tarea!r} como COMPLETED con autoridad {autoridad!r}: su "
                    f"criterio de finalizacion no consta ejecutado con exito (§14.bis regla 3). "
                    f"Sin criterio mecanico la tarea no es AUTO y la cierra un humano (regla 4)")
        if valor == "COMPLETED" and autoridad in AUTORIDADES_HUMANAS:
            # El humano si puede cerrar sin criterio —es la regla 4 al derecho—, pero si la tarea
            # TIENE uno fijado, saltarselo seria dejar abierta la ruta que la auditoria encontro:
            # bastaria declararse `ceo` para completar sin ejecutar nada.
            if criterio_fijado_de(directorio, id_tarea) is not None \
                    and not criterio_superado(directorio, id_tarea):
                raise CriterioNoVerificado(
                    f"{id_tarea!r} tiene criterio mecanico fijado y no consta superado. Ni con "
                    f"autoridad {autoridad!r}: un criterio que se puede saltar no es un criterio")
        return _registrar_sin_lock(directorio, _EVENTO_DE_ESTADO, {
            "id": id_tarea, "valor": valor, "previo": tarea["estado"],
            "autoridad": autoridad, "causa": causa})


# ----------------------------------------- lock sobre la ruta antigua (C2 · §9.2) --

def actualizar_estado(destino: pathlib.Path, cambio) -> dict:
    """**Cierra P2 en la ruta antigua.** `flock` alrededor de **leer-modificar-escribir** completo.

    `guardar()` ya era una escritura atomica, y eso es insuficiente: entre el `cargar` y el `guardar`
    de un proceso cabe entero el ciclo de otro, y el segundo pisa al primero *«en silencio»*. La
    atomicidad de la escritura no da atomicidad a la actualizacion.

    El centinela vive **junto al destino**, no junto al modulo: dos estados distintos no deben
    serializarse entre si, y dos procesos sobre el mismo estado si."""
    destino = pathlib.Path(destino)
    with lock_estado(destino.parent):
        estado = cargar(destino) or estado_inicial()
        nuevo = cambio(estado)
        if nuevo is None:
            raise ValueError("la funcion de cambio debe devolver el estado, no None")
        guardar(nuevo, destino)
        return nuevo


# ------------------------------------------- reconciliacion tras caida (A3 · A4) --

# Estados que significan «habia un proceso trabajando». Si nadie los cerro, ese proceso murio.
# Esperar cuota, entorno o una decision **no** es haber muerto: son esperas legitimas y reconciliar
# no las toca, porque marcar FAILED cada espera convertiria cada reinicio en una masacre de tareas
# sanas.
ESTADOS_EN_VUELO = ("WORKING",)


def reconciliar_tras_caida(directorio: pathlib.Path, *, autoridad: str, causa: str) -> list[str]:
    """**A4**: una tarea interrumpida queda `FAILED`, **nunca** `COMPLETED`. **A3**: lo ya cerrado no
    se toca.

    La reconciliacion solo puede concluir FAILED. Concluir COMPLETED seria fabricar evidencia de un
    trabajo que nadie vio terminar — exactamente lo que `interrumpir` existe para impedir: *«un
    COMPLETED falso hace que el siguiente agente de por hecho un trabajo que nunca ocurrio, y nadie
    vuelve a mirarlo»*. Que no haya evidencia no es que el trabajo saliera bien: es que no consta.

    Devuelve los ids reconciliados —vacio si no habia nada que reconciliar—, no un booleano: saber
    *cuales* murieron es lo que permite investigar."""
    directorio = pathlib.Path(directorio)
    reconciliadas = []
    with lock_estado(directorio):
        proyeccion = _base_proyeccion()
        for evento in leer_eventos(directorio):
            _aplicar(proyeccion, evento)
        for id_tarea, tarea in sorted(proyeccion["tareas"].items()):
            if tarea["estado"] in ESTADOS_EN_VUELO:
                validar_transicion(tarea["estado"], "FAILED", autoridad, causa)
                _registrar_sin_lock(directorio, _EVENTO_DE_ESTADO, {
                    "id": id_tarea, "valor": "FAILED", "previo": tarea["estado"],
                    "autoridad": autoridad, "causa": causa, "reconciliada": True})
                reconciliadas.append(id_tarea)
    return reconciliadas
