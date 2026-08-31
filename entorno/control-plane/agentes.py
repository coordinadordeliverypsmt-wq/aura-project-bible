"""Selección de agente, **failover gobernado** y verificación de efecto — `D-ORCH-3`.

## La regla que sostiene todo lo demás

**AURA no cree al agente.** El agente *afirma*; AURA *verifica el efecto*. Un agente que responde
«archivo creado correctamente» sin crearlo produce `NO_VERIFICADO`, jamás `VERIFIED`.

No es una precaución teórica: la Línea B midió exactamente ese caso. Y aceptar la afirmación
produciría un `COMPLETED` falso, que es lo que hace que el siguiente agente dé por hecho un trabajo
que nunca ocurrió y nadie vuelva a mirarlo.

## Por qué el failover NO es «si Claude falla, usa OpenCode»

Hay que separar **el agente no puede** de **la tarea está mal**:

| Clase | Qué significa | ¿Releva? |
|---|---|---|
| `AGENTE_SIN_CUOTA` | el agente existe pero no puede trabajar ahora | **sí** |
| `AGENTE_NO_DISPONIBLE` | el agente no está instalado o no arranca | **sí** |
| `TAREA_FALLIDA` | el trabajo se hizo y salió mal | **no** |
| `SIN_EFECTO` | dijo que sí y no pasó nada | **no** |
| `RESULTADO_INVALIDO` | devolvió algo que no cumple el contrato | **no** |
| `TIMEOUT` | no se sabe si el agente o la tarea | **no** — ante la duda, no se releva |

Relevar ante `TAREA_FALLIDA` **oculta el fallo** rotando agentes hasta que alguno calle. Por eso
solo las dos primeras justifican el relevo, y la cadena es **finita**: `claude → opencode → fin`.

`TIMEOUT` no releva **a propósito**: no distingue un agente colgado de una tarea que no termina, y
la respuesta segura ante una ambigüedad es no gastar otro agente en ella.

## OpenCode

Agente **secundario, externo y bajo demanda**, según el contrato ya aprobado:
`INSTALAR → VERIFICAR → EJECUTAR → MEDIR → RETIRAR → LIMPIAR → VERIFICAR AUSENCIA`. Sin los tres
últimos pasos, «bajo demanda» es «instalado». Codex está excluido por decisión del CEO y Ollama no
participa en este flujo.
"""

from __future__ import annotations

import dataclasses
import pathlib
import shutil
import time

import control_plane as cp
import orquestador as orq

# ------------------------------------------------------------------ taxonomía --

EXITO = "EXITO"
AGENTE_SIN_CUOTA = "AGENTE_SIN_CUOTA"
AGENTE_NO_DISPONIBLE = "AGENTE_NO_DISPONIBLE"
TAREA_FALLIDA = "TAREA_FALLIDA"
SIN_EFECTO = "SIN_EFECTO"
RESULTADO_INVALIDO = "RESULTADO_INVALIDO"
TIMEOUT = "TIMEOUT"

# Solo estas dos dicen «el agente no puede», que es lo único que justifica gastar otro agente.
_RELEVABLES = (AGENTE_SIN_CUOTA, AGENTE_NO_DISPONIBLE)

# Cadena cerrada y finita. Codex excluido por decisión del CEO; Ollama no participa en este flujo.
CADENA_DE_AGENTES = ("claude", "opencode")

# Contrato del agente externo bajo demanda, ya aprobado. El orden importa y el último paso es
# comprobar que no queda nada.
PASOS_AGENTE_EXTERNO = ("instalar", "verificar", "ejecutar", "medir", "retirar", "limpiar",
                        "comprobar_residuos")

_SENALES_DE_CUOTA = ("spend limit", "quota", "rate limit", "usage limit", "credit")
_SENALES_DE_AUSENCIA = ("command not found", "no such file", "not installed", "executable")


# Bloqueos medidos por ejecucion, no supuestos. Se declaran aqui para que nadie los redescubra ni
# los de por resueltos sin acta.
BLOQUEO_CONOCIDO = {
    "opencode": {
        "motivo": "exige clave de proveedor para razonar: «Google Generative AI API key is missing»",
        "medido": "2026-08-26 [EJEC], opencode-ai@1.18.22, `opencode run --dir <d> \"di hola\"`",
        "decision": "D24 prohibe claves de terceros; el CEO prohibe modificar D24",
        "consecuencia": ("el mecanismo de failover funciona y esta probado, pero el agente "
                         "secundario no puede EJECUTAR trabajo LLM sin violar D24. El ciclo "
                         "instalar/verificar/retirar/limpiar si opera y esta verificado."),
    },
}


class AgenteNoAutorizado(RuntimeError):
    """Se pidió un agente que no está en la cadena. Fail-closed: la lista es cerrada."""


class AccionNoAutorizada(RuntimeError):
    """La acción no está en `AUTO`. *«Sin lista aprobada, todo es HUMAN»*."""


class SinEvidencia(RuntimeError):
    """Se intentó cerrar una tarea sin efecto verificado. `COMPLETED` exige evidencia."""


@dataclasses.dataclass
class Respuesta:
    """Lo que devuelve un ejecutor. `afirmacion` es lo que el agente **dice**; no decide nada."""
    exit_code: int | None
    salida: str = ""
    afirmacion: str = ""
    motivo: str = ""


def clasificar(exit_code: int | None, motivo: str = "", efecto_verificado: bool | None = None) -> str:
    """Traduce el desenlace a una de las clases. El orden de comprobación es la política:

    la **indisponibilidad** se mira antes que el fallo, porque un agente sin cuota puede devolver
    cualquier código de salida; y el **efecto** se mira al final, porque solo tiene sentido cuando el
    agente sí llegó a terminar."""
    texto = (motivo or "").lower()
    if any(s in texto for s in _SENALES_DE_CUOTA):
        return AGENTE_SIN_CUOTA
    if "timeout" in texto:
        return TIMEOUT
    if exit_code == 127 or any(s in texto for s in _SENALES_DE_AUSENCIA):
        return AGENTE_NO_DISPONIBLE
    if exit_code not in (0, None):
        return TAREA_FALLIDA
    if efecto_verificado is False:
        return SIN_EFECTO
    if efecto_verificado is True:
        return EXITO
    return RESULTADO_INVALIDO


def justifica_fallback(clase: str) -> bool:
    return clase in _RELEVABLES


def siguiente_agente(actual: str) -> str | None:
    """La cadena se recorre **una vez**. Devolver None es lo que impide el fallback infinito."""
    if actual not in CADENA_DE_AGENTES:
        return None
    i = CADENA_DE_AGENTES.index(actual)
    return CADENA_DE_AGENTES[i + 1] if i + 1 < len(CADENA_DE_AGENTES) else None


def verificar_autorizado(agente: str) -> None:
    if agente not in CADENA_DE_AGENTES:
        raise AgenteNoAutorizado(
            f"{agente!r} no está en la cadena autorizada {CADENA_DE_AGENTES}; "
            f"Codex está excluido por decisión del CEO y Ollama no participa en este flujo")


def disponible(agente: str) -> bool:
    """Se **comprueba**, no se presupone. Un `import` del agente lo convertiría en dependencia."""
    binario = {"claude": "claude", "opencode": "opencode"}.get(agente, agente)
    return shutil.which(binario) is not None


# ------------------------------------------------- verificación externa del efecto --

def verificar_efecto(evidencia: dict, afirmacion: str = "") -> dict:
    """**El punto crítico.** Comprueba el mundo, no el texto.

    `afirmacion` se recibe para dejarla en el registro —es útil para investigar—, pero **no
    participa en el veredicto**. Una prueba lo fija recorriendo afirmaciones contradictorias sobre un
    efecto real.

    Una evidencia que no se sabe comprobar da `NO_VERIFICABLE`, nunca `VERIFIED`: ante la duda, no."""
    tipo = (evidencia or {}).get("tipo")
    if tipo == "fichero_existe":
        ruta = pathlib.Path(evidencia["ruta"])
        ok = ruta.exists() and ruta.stat().st_size > 0
        return {"verificado": ok, "resultado": "VERIFIED" if ok else "NO_VERIFICADO",
                "comprobacion": f"existe y no vacío: {evidencia['ruta']}", "afirmacion": afirmacion}
    if tipo == "salida_contiene":
        ok = evidencia.get("patron", "\0") in (evidencia.get("salida") or "")
        return {"verificado": ok, "resultado": "VERIFIED" if ok else "NO_VERIFICADO",
                "comprobacion": f"la salida contiene {evidencia.get('patron')!r}",
                "afirmacion": afirmacion}
    return {"verificado": False, "resultado": "NO_VERIFICABLE",
            "comprobacion": f"no sé comprobar una evidencia de tipo {tipo!r}",
            "afirmacion": afirmacion}


# ------------------------------------------------------------------ trazabilidad --

@dataclasses.dataclass
class Intento:
    """Los nueve campos que el CEO exige. Se registran **todos** los intentos, no solo el que salió
    bien: si solo constara el último, el relevo sería invisible."""
    agente: str
    numero: int
    motivo: str
    exit_code: int | None
    resultado: str
    efecto_verificado: bool
    duracion_s: float
    fallback_usado: bool
    clase: str

    def como_evento(self) -> dict:
        return {"agent": self.agente, "attempt": self.numero, "reason": self.motivo,
                "exit_code": self.exit_code, "result": self.resultado,
                "effect_verified": self.efecto_verificado, "duration": self.duracion_s,
                "fallback_used": self.fallback_usado, "class": self.clase}


def registrar_intento(directorio, id_tarea: str, intento: Intento) -> dict:
    return cp.registrar_evento(pathlib.Path(directorio), "intento_de_agente",
                               {"id": id_tarea, **intento.como_evento()})


def cerrar_tarea(directorio, id_tarea: str, veredicto: dict, autoridad: str) -> str:
    """`COMPLETED` **solo** con efecto verificado. Es el criterio **A12**: no la afirmación del
    worker, sino la comprobación.

    **La regla del criterio mecánico NO se comprueba aquí.** Estuvo aquí, y una auditoría
    independiente demostró que `cp.transicion()` la esquivaba: es la primitiva que usa toda la base,
    incluida esta función. Escribir la misma regla en dos sitios es el defecto que el `§0` del
    CHECKPOINT ya tiene documentado, y en su versión cara: la copia que falta es una ruta abierta.
    Ahora vive **solo en el motor único**, y esta función se limita a lo suyo —¿hay efecto
    verificado?— y deja que el motor decida si además había criterio y si se superó.

    **La comprobación no basta si el worker eligió qué se comprueba.** `verificar_efecto` mira el
    mundo y no el texto, pero mira el trozo de mundo que la evidencia le señala, y esa evidencia
    viene del worker. Una evidencia que se cumple sola —`salida_contiene` con el patrón dentro de la
    salida— pasa esa comprobación siendo falsa la tarea. Por eso, si la tarea tiene un
    `criterio_de_finalizacion` fijado **antes** de invocar (`§14.bis` regla 1), lo único que la
    cierra es el veredicto mecánico de **ese** criterio, ejecutado por el orquestador (regla 3)."""
    if not veredicto.get("verificado"):
        raise SinEvidencia(
            f"no se cierra {id_tarea!r} como COMPLETED: el efecto no está verificado "
            f"({veredicto.get('resultado')}). Una tarea sin evidencia no está hecha")
    cp.transicion(pathlib.Path(directorio), id_tarea, "COMPLETED", autoridad=autoridad,
                  causa=f"efecto verificado: {veredicto.get('comprobacion', '')}")
    return "COMPLETED"


# ------------------------------------------------------------------- ejecutores --

def sobre_para_externo(tarea: dict) -> dict:
    """El sobre del agente externo: **el trabajo estrictamente necesario**, sin secretos.

    Reutiliza el de `§7.1` y le quita cualquier cosa que huela a credencial. El agente externo no
    recibe acceso innecesario al repositorio ni una sola clave."""
    sobre = orq.WorkerAdapter().sobre(tarea)
    sobre["permisos"] = {"allowedTools": ["Read", "Grep", "Glob", "Bash"],
                         "permission_mode": "plan"}
    sobre["restricciones"] = list(sobre["restricciones"]) + [
        "no instalar nada permanente", "no leer variables de entorno con credenciales"]
    return {k: v for k, v in sobre.items() if "secret" not in k and "key" not in k}


def _no_implementado(nombre):
    def _ejecutor(sobre, **_):
        return Respuesta(exit_code=127, motivo=f"{nombre}: command not found (no instalado)")
    return _ejecutor


# Se sustituyen en las pruebas y en el E2E. Por defecto, ninguno ejecuta nada real: lanzar un agente
# gasta dinero y hace trabajo, y eso exige una puerta explícita (INV-9).
_EJECUTORES = {"claude": _no_implementado("claude"), "opencode": _no_implementado("opencode")}


def ejecutar_tarea(directorio, tarea: dict, autoridad: str, max_intentos: int = 2) -> dict:
    """El circuito: `AUTO → agente → efecto → verificación → cierre`, con relevo gobernado.

    El bucle está acotado por la **longitud de la cadena**, no por un contador arbitrario: el
    fallback no puede durar más que agentes hay."""
    directorio = pathlib.Path(directorio)
    accion = tarea.get("accion", "")
    if orq.nivel_de(accion) != "AUTO":
        raise AccionNoAutorizada(
            f"la acción {accion!r} es {orq.nivel_de(accion)}, no AUTO: el orquestador no la ejecuta")

    # La tarea pasa a WORKING antes de tocarla: la tabla de `§6` no permite ir de pendiente a
    # cerrada, y con razon — una tarea que aparece COMPLETED sin haber estado en curso es
    # indistinguible de una fabricada.
    if cp.estado_de(directorio, tarea["id"]) == "WAITING_FOR_NEXT_TASK":
        cp.transicion(directorio, tarea["id"], "WORKING", autoridad=autoridad,
                      causa=f"el orquestador toma la tarea para la accion {accion!r}")

    permite_fallback = bool(tarea.get("permite_fallback", True))
    # `§14.bis` regla 1: el criterio se fija **antes** de invocar, y lo fija quien crea la tarea.
    # `evidencia_requerida` ya venia de la tarea —no del worker—, pero no quedaba en el log antes de
    # la invocacion, asi que el motor no tenia nada que consultar al cerrar y toda la proteccion del
    # `§14.bis` quedaba inerte para este circuito. Lo encontro una auditoria independiente.
    # La capacidad es la accion, que por la comprobacion de arriba esta en el catalogo `AUTO`.
    orq.fijar_criterio(directorio, tarea["id"], {"capacidad": accion})
    evidencia = tarea.get("evidencia_requerida") or {}
    agente = CADENA_DE_AGENTES[0]
    numero, fallback_usado, ultimo = 0, False, None

    while agente is not None and numero < min(max_intentos, len(CADENA_DE_AGENTES)):
        numero += 1
        verificar_autorizado(agente)
        inicio = time.monotonic()
        try:
            respuesta = _EJECUTORES[agente](sobre_para_externo(tarea))
        except Exception as exc:                       # un ejecutor que revienta es indisponibilidad
            respuesta = Respuesta(exit_code=127, motivo=f"{type(exc).__name__}: {exc}")
        duracion = round(time.monotonic() - inicio, 3)

        veredicto = verificar_efecto(evidencia, afirmacion=respuesta.afirmacion)
        clase = clasificar(respuesta.exit_code, respuesta.motivo,
                           efecto_verificado=veredicto["verificado"])
        registrar_intento(directorio, tarea["id"], Intento(
            agente=agente, numero=numero, motivo=respuesta.motivo, exit_code=respuesta.exit_code,
            resultado=veredicto["resultado"], efecto_verificado=veredicto["verificado"],
            duracion_s=duracion, fallback_usado=fallback_usado, clase=clase))
        ultimo = {"agente": agente, "clase": clase, "resultado": veredicto["resultado"],
                  "veredicto": veredicto, "fallback_usado": fallback_usado, "intentos": numero}

        if clase == EXITO:
            # El efecto se comprobo contra el mundo y contra la evidencia que fijo la tarea: eso es
            # la ejecucion del criterio, y queda registrada para que el motor pueda consultarla.
            cp.registrar_criterio_verificado(
                directorio, tarea["id"], orq.criterio_de(directorio, tarea["id"])["huella"],
                True, veredicto.get("comprobacion", ""))
            cerrar_tarea(directorio, tarea["id"], veredicto, autoridad)
            return {**ultimo, "resultado": "VERIFIED"}
        if not (permite_fallback and justifica_fallback(clase)):
            break
        agente, fallback_usado = siguiente_agente(agente), True

    if cp.estado_de(directorio, tarea["id"]) not in ("UNKNOWN", "COMPLETED"):
        cp.transicion(directorio, tarea["id"], "FAILED", autoridad=autoridad,
                      causa=f"sin efecto verificado tras {numero} intento(s): {ultimo['clase']}")
    return ultimo or {"resultado": "NO_VERIFICADO", "agente": None, "fallback_usado": False}


# ------------------------------------------------------------- continuidad --

def tareas_auto_pendientes(directorio) -> list[dict]:
    """Trabajo **ya registrado** cuya acción está en `AUTO`. AURA no inventa tareas: si nadie
    registró nada, no hay nada que hacer."""
    directorio = pathlib.Path(directorio)
    proyeccion = cp.proyectar(directorio)
    pendientes = []
    for evento in cp.leer_eventos(directorio):
        if evento["tipo"] != "tarea_registrada":
            continue
        datos = evento["datos"]
        estado = (proyeccion["tareas"].get(datos["id"]) or {}).get("estado")
        if estado == "WAITING_FOR_NEXT_TASK" and orq.nivel_de(datos.get("accion", "")) == "AUTO":
            pendientes.append(datos)
    return pendientes


def continuidad(directorio, autoridad: str, max_tareas: int = 10) -> dict:
    """**El modo que permite que el trabajo no se detenga cuando el agente principal se queda sin
    cuota.**

    Detecta la indisponibilidad, conserva la tarea, registra el motivo, activa el agente secundario
    autorizado, verifica el efecto y pasa a la siguiente. Tres límites deliberados:

    - **No inventa tareas.** Solo ejecuta lo que ya está registrado y está en `AUTO`.
    - **Es finita.** `max_tareas` acota la cola; un bucle nocturno sin tope es un demonio.
    - **Se detiene si ningún agente puede seguir.** Vaciar la cola marcando FAILED cuando el
      problema es el agente y no las tareas destruiría trabajo pendiente por un motivo ajeno a él.
      Se para en la primera y **deja el motivo escrito**, que es lo que permite retomar sin volver a
      investigar.
    """
    directorio = pathlib.Path(directorio)
    intentadas = completadas = 0
    fallback_usado = False
    motivo = "sin tareas AUTO pendientes"
    cp.registrar_evento(directorio, "continuidad_iniciada",
                        {"max_tareas": max_tareas, "politica": orq.version_de_politica()})
    for tarea in tareas_auto_pendientes(directorio)[:max_tareas]:
        intentadas += 1
        resultado = ejecutar_tarea(directorio, tarea, autoridad=autoridad)
        fallback_usado = fallback_usado or bool(resultado.get("fallback_usado"))
        if resultado.get("resultado") == "VERIFIED":
            completadas += 1
            motivo = "cola AUTO agotada"
            continue
        if justifica_fallback(resultado.get("clase", "")):
            motivo = (f"ningun agente disponible ({resultado.get('clase')}): la cola se conserva "
                      f"para cuando vuelva la capacidad")
            break
        motivo = f"la tarea {tarea['id']!r} no verifico su efecto: {resultado.get('clase')}"
    informe = {"intentadas": intentadas, "completadas": completadas,
               "fallback_usado": fallback_usado, "motivo": motivo}
    cp.registrar_evento(directorio, "continuidad_terminada", informe)
    return informe
