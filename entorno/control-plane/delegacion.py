"""Delegar una misión acotada a un subagente — la pieza 19 (CEO, 2026-09-21).

QUÉ FALTABA, EXACTAMENTE. El inventario de `DP-DELEGACION-A-SUBAGENTES.md` midió que **18 de las 19
piezas ya existían**: autoridad delegada (`REVIEW:<revisor>`), presupuesto (`TOPE_DE_REINTENTOS`,
`MAX_TAREAS`), plazo con muerte del grupo de procesos (`verificador._matar_arbol`), cadena finita
(`agentes.siguiente_agente`), trazabilidad (log encadenado), sandbox (`zona_permitida`), auditoría
(las cinco puertas). Lo único ausente era **instanciar un subagente con misión propia**. Esto es
eso, y nada más.

LA DISTINCIÓN QUE SOSTIENE TODO EL MÓDULO: **delegar no es crear autoridad.**

`crear_autoridad` es materia reservada a `D22` y sigue siéndolo — este módulo no la toca ni la
necesita. Una delegación aquí **no inventa un permiso**: toma uno que el CEO ya concedió —las
capacidades de `[auto]` en `politica-orquestador.toml`, derivadas de la lista verde de `ADR-0003`
por acta `D4`, todas de efecto **lectura**— y lo presta, acotado y con fecha de caducidad, a una
ejecución concreta. Si la capacidad no consta ya autorizada, no hay nada que prestar y la misión se
rechaza. **Una delegación nunca puede conceder más de lo que su origen ya tenía.**

POR QUÉ SOLO LECTURA, Y POR QUÉ ESO NO ES UNA LIMITACIÓN DECORATIVA. El catálogo `[auto]` se filtró
a propósito por efecto: *«una acción AUTO que escribiera sería autonomía de escritura concedida sin
acta»*. Delegar escritura a un subagente exigiría un acta nueva, y este módulo **no la fabrica**:
`_capacidad_autorizada` lee la política y se niega si el tipo no es `lectura`. Ampliarlo es decisión
del CEO, no una constante que alguien pueda subir.

LO QUE ESTE MÓDULO **NO** HACE, Y CONVIENE QUE SE LEA AQUÍ:

- No modifica `TODO_LO_DELEGABLE`. Ese eje gobierna qué **escritura** puede delegar un acta a
  `REVIEW`; este gobierna qué **lectura** puede prestarse a una ejecución acotada. Son ejes
  distintos y cruzarlos sería exactamente la ampliación que nadie autorizó.
- No modifica `_MATERIA_RESERVADA` ni `ESTADOS_SOLO_HUMANO`; los **consulta** para negarse.
- No retira `PARADA`. La consulta dos veces —al delegar y al ejecutar— porque un permiso concedido
  antes de que alguien pare el sistema no puede valer después.
- No crea un segundo log, ni un segundo sandbox, ni una segunda auditoría: usa los que hay.

EL LÍMITE QUE ESTA CAPACIDAD **NO** RESUELVE, Y QUE HAY QUE LEER ANTES DE USARLA.

Una auditoría adversarial (2026-09-21) demostró, ejecutándolo, que **`ejecutar_pruebas` implica
ejecución de código arbitrario**. No es un defecto de este módulo: es lo que hace pytest. Cualquier
fichero `test_*.py` dentro del sandbox se ejecuta como Python real, y desde ahí se puede leer y
escribir **fuera** del sandbox, porque el aislamiento que hay aquí es de *variables de entorno y de
rutas en la línea de órdenes*, no de sistema operativo. No hay contenedor, ni namespaces, ni usuario
distinto, ni límites del kernel.

**Qué significa en la práctica.** El perímetro de este módulo acota *qué ficheros se le nombran a la
herramienta*, no *qué hace el código que esos ficheros contienen*. Por eso la regla de uso es:

> **El contenido del sandbox debe venir de una fuente tan fiable como el propio plano.** Delegar
> `ejecutar_pruebas` sobre ficheros que un tercero controla equivale a darle ejecución con los
> privilegios del proceso.

Hoy eso se cumple —el sandbox lo prepara quien delega, dentro del repositorio—, y por eso la
capacidad es utilizable. Pero es una **condición de uso, no una garantía del código**, y se dice
aquí porque la diferencia entre ambas cosas es la que este proyecto lleva ocho incidentes
aprendiendo. Cerrarla de verdad exigiría aislamiento de sistema operativo, que es diseño nuevo y
decisión del CEO: queda registrado como `DECISION_REQUIRED` en el expediente del DP.

LIFECYCLE FINITO, QUE ES LA OTRA MITAD DE LA SEGURIDAD. Una delegación nace con `expira_en` y con
**un solo uso**. Gastado o caducado, no vuelve: no existe forma de renovarla desde dentro. Es lo que
impide que una misión se convierta en una autorización permanente, que es como una delegación se
degrada en una cesión de soberanía.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import subprocess
import sys
import time

import aislamiento as ais
import control_plane as cp
import orquestador as orq
import review as rv
import verificador as vf

#: Un subagente no crea subagentes. La cadena tiene **un** eslabón y se comprueba en las dos
#: puertas —al delegar y al ejecutar—, porque comprobarla solo al crear dejaría pasar una
#: delegación fabricada a mano con la profundidad ya gastada.
PROFUNDIDAD_MAXIMA = 1

#: Plazo por defecto de una misión. No es el de la batería entera (`verificador.LIMITE_S = 600`):
#: una misión delegada es una unidad de trabajo pequeña, y un plazo largo convierte el presupuesto
#: en una formalidad.
LIMITE_S_POR_DEFECTO = 120.0

#: Vida de la credencial. Corta a propósito: el intervalo entre delegar y ejecutar es de segundos,
#: y todo lo que sobre es ventana para reutilizar una credencial que ya cumplió su propósito.
VIGENCIA_S = 300.0

#: Las misiones que **de verdad** tienen ejecutor construido. `INV-9`: no se finge capacidad. Una
#: capacidad puede estar autorizada en la política y no estar construida aquí; en ese caso se
#: rechaza citando el motivo, en vez de devolver un resultado inventado.
MISIONES_CONSTRUIDAS = ("ejecutar_pruebas", "verificar_calidad")

#: **Sin confinamiento del sistema operativo no se delega.** Fail-closed y a proposito: una
#: auditoria demostro que sin el, `ejecutar_pruebas` da ejecucion de codigo arbitraria y el sandbox
#: es solo una lista de rutas. Ejecutar declarando un aislamiento que no existe seria `INV-9` con
#: consecuencias de seguridad. Si algun dia hay que correr sin Landlock, que sea un acto explicito
#: —cambiar esta constante y decirlo—, nunca un silencio.
EXIGIR_AISLAMIENTO = True

_EVENTO_DELEGADA = "mision_delegada"
_EVENTO_EJECUTADA = "mision_ejecutada"
_EVENTO_RECHAZADA = "mision_rechazada"
_EVENTO_RESULTADO = "mision_resuelta"
_EVENTO_REVOCADA = "delegacion_revocada"

#: Lo que ve el proceso hijo. **Se construye, no se hereda** — misma razón que en `verificador`:
#: un entorno heredado trae `PYTEST_ADDOPTS` y con él la capacidad de convertir cualquier medición
#: en un verde vacío.
_ENTORNO_MINIMO = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")

#: La marca que un proceso delegado lleva puesta. **Esto nació de un ataque que funcionó**
#: (2026-09-21): `Mision.profundidad` la declara quien construye la misión, así que el código que
#: corría dentro de una misión podía hacer `import delegacion` y pedir otra con `profundidad=0`.
#: La comprobación funcionaba perfectamente y no servía de nada, porque el dato en el que confiaba
#: se lo daba el atacante. Ahora la profundidad real viaja en el entorno del subproceso y se hereda:
#: un proceso que ya está dentro de una misión no puede declarar que no lo está.
_VAR_PROFUNDIDAD = "AURA_DELEGACION_PROFUNDIDAD"
_VAR_EN_CURSO = "AURA_DELEGACION_EN_CURSO"


def profundidad_heredada() -> int:
    """La profundidad del proceso actual, leída del entorno. Cero si nadie nos delegó."""
    import os
    try:
        return max(0, int(os.environ.get(_VAR_PROFUNDIDAD, "0")))
    except (TypeError, ValueError):
        # Un valor corrupto no concede: ante la duda, se asume que ya estamos dentro (ADR-0003).
        return PROFUNDIDAD_MAXIMA


def _entorno_del_subagente(delegacion: "Delegacion") -> dict:
    """Lo que ve el proceso hijo: el mínimo, más su propia marca de profundidad."""
    import os
    entorno = {k: os.environ[k] for k in _ENTORNO_MINIMO if k in os.environ}
    entorno["PYTHONDONTWRITEBYTECODE"] = "1"
    entorno[_VAR_PROFUNDIDAD] = str(delegacion.profundidad)
    entorno[_VAR_EN_CURSO] = str(delegacion.id)
    return entorno


class MisionRechazada(PermissionError):
    """La misión no puede delegarse. Es la respuesta por defecto: este módulo falla cerrado."""


class DelegacionInvalida(PermissionError):
    """La credencial no sirve: caducada, revocada, ya gastada o manipulada."""


class PerimetroViolado(PermissionError):
    """La misión intenta salir de su sandbox."""


# ============================================================ LAS PIEZAS --


@dataclasses.dataclass(frozen=True)
class Mision:
    """Lo que se pide, acotado. Inmutable: una misión que pudiera editarse tras autorizarse sería
    el vector de «declarado ≠ real» aplicado a la propia autorización."""
    capacidad: str
    sandbox: str
    argumentos: tuple[str, ...] = ()
    limite_s: float = LIMITE_S_POR_DEFECTO
    profundidad: int = 0

    @property
    def id(self) -> str:
        return _huella("mision", self.capacidad, self.sandbox,
                       "|".join(self.argumentos), str(self.limite_s), str(self.profundidad))


@dataclasses.dataclass(frozen=True)
class Delegacion:
    """La credencial: de un solo uso, con caducidad y atada a UNA misión.

    `huella` no es decorativa: liga la credencial al contenido exacto de la misión. Cambiar el
    sandbox o la capacidad después de delegar produce una huella distinta y `ejecutar` la rechaza —
    es lo que impide que una autorización legítima se reutilice para otra cosa."""
    id: str
    mision_id: str
    capacidad: str
    sandbox: str
    autoridad_origen: str
    acta: str
    expira_en: float
    profundidad: int
    huella: str


@dataclasses.dataclass(frozen=True)
class Resultado:
    """Lo que el subagente devuelve, ya **verificado contra el mundo**, no creído.

    `ok` no es lo que el subagente afirme: es lo que AURA comprueba. Es el patrón que `agentes.py`
    ya fija — *«AURA no cree al agente. El agente afirma; AURA verifica el efecto»*."""
    delegacion_id: str
    capacidad: str
    ok: bool
    motivo: str
    evidencia: dict
    agotado: bool = False


# ============================================================ UTILIDADES --


def _huella(*partes: str) -> str:
    return hashlib.sha256("\x1f".join(partes).encode("utf-8")).hexdigest()[:16]


def _ahora() -> float:
    return time.time()


def _dentro_del_sandbox(sandbox, ruta) -> bool:
    """La comparación es sobre la ruta **resuelta**, así que `..` y los enlaces simbólicos se
    deshacen antes de juzgar. Es la misma regla que `autoconstruccion.zona_permitida`, y existe
    porque un sandbox que confía en el texto de la ruta no es un sandbox."""
    try:
        base = pathlib.Path(sandbox).resolve(strict=False)
        objetivo = pathlib.Path(ruta).resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return objetivo == base or base in objetivo.parents


def _exigir_ruta_de_verdad(directorio, capacidad: str, caja: pathlib.Path, argumento) -> None:
    """Un argumento de una misión es una RUTA, y tiene que serlo de verdad.

    **Esto nació de un ataque que funcionó** (2026-09-21). Los argumentos se pasaban tal cual a la
    línea de órdenes de la herramienta, y `ruff` —como casi toda herramienta— interpreta como
    **opción** lo que empieza por `-`. Una misión con el argumento `--exit-zero` devolvía
    `ok=True, codigo=0` sobre un árbol sucio: la capacidad declaraba «calidad verificada» sin haber
    verificado nada. Es «declarado ≠ real», esta vez inyectado desde la misión. `--help` hacía lo
    mismo por otra vía.

    El perímetro no lo detectaba, y es instructivo por qué: `caja / "--exit-zero"` es nominalmente
    una ruta **dentro** del sandbox. Comprobar la contención no basta si lo que pasa por ahí nunca
    fue una ruta.

    Tres condiciones, y las tres hacen falta:

    1. **No empieza por `-`.** Corta la inyección de opciones en la raíz, antes de que dependa de
       cómo parsee cada herramienta.
    2. **Existe.** Una ruta que no existe no es trabajo: o es un error, o es un intento de que la
       herramienta la interprete de otra manera.
    3. **Está dentro del sandbox, ya resuelta.** Lo de siempre: `..` y los enlaces se deshacen
       antes de juzgar.
    """
    texto = str(argumento)
    if not texto.strip():
        _rechazar(directorio, capacidad, "un argumento vacio no es una ruta")
    if texto.startswith("-"):
        _rechazar(directorio, capacidad,
                  f"el argumento {texto!r} parece una OPCION, no una ruta: una mision no compone "
                  f"la linea de ordenes de la herramienta")
    if "\x00" in texto:
        _rechazar(directorio, capacidad, "un argumento con byte nulo no es una ruta")
    destino = caja / texto
    if not _dentro_del_sandbox(caja, destino):
        _rechazar(directorio, capacidad, f"el argumento {texto!r} apunta fuera del sandbox")
    if not destino.exists():
        _rechazar(directorio, capacidad,
                  f"el argumento {texto!r} no existe dentro del sandbox")


def _capacidad_autorizada(capacidad: str) -> dict:
    """La ficha de la capacidad en `[auto]`, o `{}` si no consta.

    Aquí es donde este módulo se ata a una autoridad que **ya existía**: si el CEO no la puso en la
    política con su acta, no hay nada que delegar. Se consulta `orquestador.ficha_de`, que es la
    lectura única de la política — duplicar aquí el acceso al TOML habría creado una segunda fuente
    de verdad sobre qué está autorizado, que es justo lo que `INV-7` prohíbe."""
    try:
        return orq.ficha_de(capacidad)
    except Exception:                                           # pragma: no cover - politica rota
        return {}


# ============================================================ DELEGAR --


def _rechazar(directorio, capacidad: str, motivo: str) -> None:
    cp.registrar_evento(pathlib.Path(directorio), _EVENTO_RECHAZADA,
                        {"capacidad": capacidad, "motivo": motivo})
    raise MisionRechazada(motivo)


def delegar(directorio, mision: Mision, autoridad: str, acta: str) -> Delegacion:
    """Convierte una misión en una credencial de un solo uso, o se niega y deja constancia.

    **Todas las comprobaciones son previas y ninguna es opcional.** El orden importa: `PARADA`
    primero, porque si alguien paró el sistema no hay nada más que discutir."""
    directorio = pathlib.Path(directorio)
    capacidad = str(mision.capacidad or "").strip()

    if orq.parada_solicitada(directorio):
        _rechazar(directorio, capacidad, "kill switch activado")

    if not capacidad:
        _rechazar(directorio, capacidad, "la mision no declara capacidad")

    # `D22` manda sobre todo lo demas y no admite excepcion: ni con acta, ni con REVIEW encendido.
    if rv.es_materia_reservada(capacidad):
        _rechazar(directorio, capacidad,
                  f"{capacidad!r} es materia reservada a D22: no se delega")

    if capacidad not in MISIONES_CONSTRUIDAS:
        _rechazar(directorio, capacidad,
                  f"no existe ejecutor construido para {capacidad!r}; los que hay son "
                  f"{MISIONES_CONSTRUIDAS}. INV-9: no se finge capacidad")

    ficha = _capacidad_autorizada(capacidad)
    if not ficha:
        _rechazar(directorio, capacidad,
                  f"{capacidad!r} no consta autorizada en la politica: una delegacion no puede "
                  f"conceder lo que su origen no tenia")
    if str(ficha.get("tipo", "")).strip() != "lectura":
        _rechazar(directorio, capacidad,
                  f"{capacidad!r} no es de efecto lectura: delegar escritura exige acta del CEO")

    if EXIGIR_AISLAMIENTO and not ais.DISPONIBLE:
        _rechazar(directorio, capacidad,
                  "este kernel no ofrece Landlock: sin confinamiento del sistema de ficheros, una "
                  "mision delegada podria leer y escribir fuera de su sandbox (INV-9: no se finge "
                  "aislamiento)")

    if not str(autoridad or "").strip():
        _rechazar(directorio, capacidad, "la delegacion no declara autoridad de origen")
    if not str(acta or "").strip():
        _rechazar(directorio, capacidad, "la delegacion no cita acta: no hay permiso, hay intencion")

    # La profundidad EFECTIVA es la mayor entre la que la mision declara y la que este proceso
    # heredo. Fiarse solo de lo declarado fue el agujero: un subagente pedia `profundidad=0` desde
    # dentro de su propia mision y la cota no se enteraba.
    profundidad = max(int(mision.profundidad), profundidad_heredada())
    if profundidad >= PROFUNDIDAD_MAXIMA:
        _rechazar(directorio, capacidad,
                  f"profundidad {profundidad} alcanza el maximo {PROFUNDIDAD_MAXIMA}: "
                  f"un subagente no crea subagentes")

    caja = pathlib.Path(mision.sandbox)
    if not caja.is_dir():
        _rechazar(directorio, capacidad, f"el sandbox {mision.sandbox!r} no es un directorio")

    for argumento in mision.argumentos:
        _exigir_ruta_de_verdad(directorio, capacidad, caja, argumento)

    delegacion = Delegacion(
        id=_huella("delegacion", mision.id, autoridad, acta, str(_ahora())),
        mision_id=mision.id, capacidad=capacidad, sandbox=str(caja.resolve(strict=False)),
        autoridad_origen=str(autoridad), acta=str(acta),
        expira_en=_ahora() + VIGENCIA_S, profundidad=profundidad + 1,
        huella=mision.id)
    cp.registrar_evento(directorio, _EVENTO_DELEGADA, {
        "delegacion": delegacion.id, "mision": mision.id, "capacidad": capacidad,
        "sandbox": delegacion.sandbox, "autoridad_origen": delegacion.autoridad_origen,
        "acta": delegacion.acta, "profundidad": delegacion.profundidad,
        "expira_en": delegacion.expira_en})
    return delegacion


# ============================================================ VIGENCIA Y REVOCACION --


def revocar(directorio, delegacion_id: str, por: str, motivo: str = "") -> None:
    """Matar una credencial antes de que caduque. Deja rastro: revocar en silencio seria
    indistinguible de que nunca hubiera existido."""
    cp.registrar_evento(pathlib.Path(directorio), _EVENTO_REVOCADA,
                        {"delegacion": str(delegacion_id), "por": str(por),
                         "motivo": str(motivo or "sin motivo declarado")})


def emision_de(directorio, delegacion_id: str) -> dict:
    """Lo que el HISTORIAL dice de esta credencial, que es lo único que cuenta.

    **Esto nació de un ataque que funcionó** (2026-09-21). `Delegacion` es un `dataclass` sin firma
    ni secreto, y su `huella` se calcula con campos públicos: cualquiera podía construir una a mano
    —o resucitar una caducada con `dataclasses.replace`— y `ejecutar` la aceptaba, porque solo
    comprobaba su consistencia **interna**. Una credencial que se valida a sí misma no valida nada.

    La corrección no añade criptografía: usa la regla que este proyecto ya tiene. `ADR-0023` dice
    que **el historial de eventos es la única fuente de verdad y todo lo demás es proyección**. Una
    `Delegacion` es proyección; el evento `mision_delegada` es el hecho. Si el hecho no consta, la
    credencial no existe, por muy bien formada que venga."""
    for evento in cp.leer_eventos(pathlib.Path(directorio)):
        if evento["tipo"] == _EVENTO_DELEGADA and evento["datos"].get("delegacion") == delegacion_id:
            return dict(evento["datos"])
    return {}


def esta_revocada(directorio, delegacion_id: str) -> bool:
    return any(e["tipo"] == _EVENTO_REVOCADA and e["datos"].get("delegacion") == delegacion_id
               for e in cp.leer_eventos(pathlib.Path(directorio)))


def usos_de(directorio, delegacion_id: str) -> int:
    return sum(1 for e in cp.leer_eventos(pathlib.Path(directorio))
               if e["tipo"] == _EVENTO_EJECUTADA and e["datos"].get("delegacion") == delegacion_id)


def vigente(directorio, delegacion: Delegacion) -> tuple[bool, str]:
    """Las cuatro razones por las que una credencial deja de servir. Se devuelven **con motivo**:
    un `False` pelado obliga a adivinar, y lo que no se puede auditar no se puede corregir."""
    emitida = emision_de(directorio, delegacion.id)
    if not emitida:
        return False, ("la credencial no consta emitida en el historial: no basta con estar bien "
                       "formada, tiene que haber un acto que la respalde (ADR-0023)")
    # Los campos que deciden se leen del HECHO registrado, no del objeto que trae el llamante.
    # Sin esto, `dataclasses.replace` bastaba para resucitar una credencial caducada o subirle la
    # profundidad: el dato que manda tiene que ser el que quedo escrito al concederla.
    for campo, valor in (("mision", delegacion.mision_id), ("capacidad", delegacion.capacidad),
                         ("sandbox", delegacion.sandbox)):
        if emitida.get(campo) != valor:
            return False, (f"la credencial no coincide con lo que se emitio: {campo} registrado "
                           f"{emitida.get(campo)!r}, presentado {valor!r}")
    if float(emitida.get("expira_en", 0)) != float(delegacion.expira_en):
        return False, "la caducidad no es la que se registro al emitir la credencial"
    if int(emitida.get("profundidad", -1)) != int(delegacion.profundidad):
        return False, "la profundidad no es la que se registro al emitir la credencial"
    if esta_revocada(directorio, delegacion.id):
        return False, "la delegacion fue revocada"
    if _ahora() > delegacion.expira_en:
        return False, "la delegacion caduco"
    if usos_de(directorio, delegacion.id) >= 1:
        return False, "la delegacion ya se gasto: es de un solo uso"
    if delegacion.profundidad > PROFUNDIDAD_MAXIMA:
        return False, f"profundidad {delegacion.profundidad} excede el maximo {PROFUNDIDAD_MAXIMA}"
    return True, ""


# ============================================================ EJECUTAR --


def _confinador_de(mision: Mision):
    """El confinamiento de una misión, construido en **un solo sitio**.

    Lo descubrió el mutante `AI-M2` al sobrevivir: cada capacidad cableaba su propio `preexec_fn`,
    así que olvidarlo en una rama era posible y ninguna prueba de la otra rama se enteraba. Un
    control de seguridad que hay que acordarse de conectar en cada sitio **se acabará olvidando en
    alguno** — es la misma lección de ALERTA-005, la puerta va donde pasa todo el mundo.

    Ahora las dos capacidades pasan por aquí, y quitar el confinamiento de una lo quita de las dos:
    el mutante ya no puede degradar media capacidad."""
    return ais.preparar(mision.sandbox)


def _ejecutar_pruebas(mision: Mision, delegacion: "Delegacion") -> Resultado:
    """Ejecucion **real**, reutilizando el verificador que ya existe. No se duplica el arnes: la
    unica diferencia es el plazo, que aqui lo fija la mision."""
    # La marca viaja por el entorno del PROCESO, que es lo que `verificador` propaga a su hijo.
    # Se pone y se quita alrededor de la llamada: dejarla puesta contaminaria al proceso padre.
    import os
    previo = {k: os.environ.get(k) for k in (_VAR_PROFUNDIDAD, _VAR_EN_CURSO)}
    os.environ[_VAR_PROFUNDIDAD] = str(delegacion.profundidad)
    os.environ[_VAR_EN_CURSO] = str(delegacion.id)
    try:
        informe = vf.ejecutar_pruebas(list(mision.argumentos), mision.sandbox,
                                      limite_s=mision.limite_s,
                                      confinar=_confinador_de(mision))
    finally:
        for clave, valor in previo.items():
            if valor is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = valor
    return Resultado(
        delegacion_id="", capacidad=mision.capacidad, ok=informe.sano,
        motivo="" if informe.sano else "la bateria no quedo sana",
        agotado=informe.agotado,
        evidencia={"ejecutadas": informe.ejecutadas, "fallidas": informe.fallidas,
                   "errores": informe.errores, "omitidas": informe.omitidas,
                   "codigo": informe.codigo, "aislamiento": ais.descripcion()})


def _ejecutar_verificar_calidad(mision: Mision, delegacion: "Delegacion") -> Resultado:
    """Ejecucion **real** de `ruff`, local y sin red. La linea de ordenes se **construye** aqui a
    partir de rutas: nunca se compone desde texto libre de la mision, que es la regla del CEO sobre
    capacidades —se nombran por el resultado y no ejecutan ordenes arbitrarias del sistema—."""
    entorno = _entorno_del_subagente(delegacion)
    rutas = [str(r) for r in (mision.argumentos or ["."])]
    try:
        proceso = subprocess.Popen(
            # `--` cierra las opciones: todo lo que va despues es una ruta, diga lo que diga.
            # Es la segunda capa — `_exigir_ruta_de_verdad` ya rechaza lo que empiece por `-` —, y
            # esta aqui porque una defensa que depende de una sola comprobacion depende de que esa
            # comprobacion nunca se toque.
            [sys.executable, "-m", "ruff", "check", "--no-cache", "--", *rutas],
            cwd=str(mision.sandbox), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, env=entorno, start_new_session=True,
            preexec_fn=_confinador_de(mision))
    except OSError as error:
        return Resultado("", mision.capacidad, False, f"no se pudo lanzar el verificador: {error}",
                         {})
    try:
        salida, _ = proceso.communicate(timeout=mision.limite_s)
        agotado, codigo = False, proceso.returncode
    except subprocess.TimeoutExpired:
        vf._matar_arbol(proceso)
        try:
            salida, _ = proceso.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            salida = "(no se pudo leer la salida tras matar el proceso)"
        agotado, codigo = True, None
    return Resultado(
        delegacion_id="", capacidad=mision.capacidad, ok=(not agotado and codigo == 0),
        motivo="" if (not agotado and codigo == 0) else "el verificador de calidad no dio limpio",
        agotado=agotado, evidencia={"codigo": codigo, "salida": (salida or "")[-2000:],
                                    "aislamiento": ais.descripcion()})


_EJECUTORES = {
    "ejecutar_pruebas": _ejecutar_pruebas,
    "verificar_calidad": _ejecutar_verificar_calidad,
}


def ejecutar(directorio, delegacion: Delegacion, mision: Mision) -> Resultado:
    """Ejecuta la misión bajo su credencial, o se niega. Deja rastro en los dos casos.

    **`PARADA` se consulta aquí otra vez**, y no es redundancia: entre delegar y ejecutar puede
    haber pasado cualquier cosa, y un permiso concedido antes de que un humano pare el sistema no
    puede valer después. El subagente no participa en esa comprobación — no puede, y ese es el
    punto de un mecanismo fuera de banda."""
    directorio = pathlib.Path(directorio)

    if orq.parada_solicitada(directorio):
        raise DelegacionInvalida("kill switch activado: ninguna delegacion se ejecuta")

    # La credencial tiene que corresponder a ESTA mision. Sin esto, una autorizacion legitima
    # podria reutilizarse para una mision distinta — cambiar el sandbox despues de autorizar.
    if delegacion.huella != mision.id or delegacion.mision_id != mision.id:
        raise DelegacionInvalida(
            "la credencial no corresponde a esta mision: la mision cambio despues de autorizarse")

    # **La reserva va bajo lock y ANTES de ejecutar** (2026-09-21).
    #
    # Nacio de un ataque que funciono: comprobar la vigencia, ejecutar, y registrar el consumo al
    # final deja una ventana del tamano de la ejecucion entera. Cinco llamadas concurrentes con la
    # misma credencial pasaban las cinco la comprobacion de «no gastada» y el log acababa con cinco
    # usos de una credencial de un solo uso. El `flock` de `registrar_evento` protege la escritura
    # puntual, no el ciclo comprobar -> decidir -> consumir.
    #
    # Reservar primero tiene un coste que conviene declarar: si el proceso muere a mitad de la
    # ejecucion, el uso queda gastado y la mision no se reintenta. Es deliberado — ante la duda,
    # roja (ADR-0003): gastar un uso de mas es reparable pidiendo otra credencial; ejecutar dos
    # veces algo que se autorizo una sola vez, no.
    ok, motivo = vigente(directorio, delegacion)
    if not ok:
        raise DelegacionInvalida(motivo)

    # Reserva optimista con desempate por `seq`. **No se toma un lock alrededor**: `registrar_evento`
    # ya toma `lock_estado` por dentro, y envolverlo en otro produce un interbloqueo — `flock` no es
    # reentrante. Se midio: la bateria entera se colgo.
    #
    # El patron es: escribir la reserva (atomica de por si) y DESPUES mirar quien llego primero. El
    # `seq` del log es monotonico y unico, asi que el desempate es determinista y no depende de
    # relojes ni de suerte. El que no sea el primero aborta sin ejecutar.
    reserva = cp.registrar_evento(directorio, _EVENTO_EJECUTADA, {
        "delegacion": delegacion.id, "mision": delegacion.mision_id,
        "capacidad": delegacion.capacidad, "fase": "reservada"})
    reservas = [e for e in cp.leer_eventos(directorio)
                if e["tipo"] == _EVENTO_EJECUTADA and e["datos"].get("delegacion") == delegacion.id]
    if reservas and reservas[0].get("seq") != reserva.get("seq"):
        raise DelegacionInvalida(
            "la delegacion ya se gasto: otra ejecucion la reservo antes (es de un solo uso)")

    if not _dentro_del_sandbox(delegacion.sandbox, mision.sandbox):
        raise PerimetroViolado("la mision apunta fuera del sandbox que se autorizo")
    for argumento in mision.argumentos:
        if not _dentro_del_sandbox(delegacion.sandbox, pathlib.Path(mision.sandbox) / argumento):
            raise PerimetroViolado(f"el argumento {argumento!r} apunta fuera del sandbox")

    ejecutor = _EJECUTORES.get(delegacion.capacidad)
    if ejecutor is None:                                        # pragma: no cover - fail closed
        raise DelegacionInvalida(f"sin ejecutor construido para {delegacion.capacidad!r}")

    try:
        bruto = ejecutor(mision, delegacion)
        resultado = dataclasses.replace(bruto, delegacion_id=delegacion.id)
    except vf.ArnesEnCurso as error:
        resultado = Resultado(delegacion.id, delegacion.capacidad, False, str(error), {})
    except Exception as error:                                  # pragma: no cover - defensa
        resultado = Resultado(delegacion.id, delegacion.capacidad, False,
                              f"el subagente reviento: {type(error).__name__}", {})

    # El resultado, ya con su evidencia. El uso ya se consumio arriba: esto informa de COMO fue,
    # no de que ocurriera. Separarlo es lo que permite que un proceso muerto a mitad deje igual el
    # uso gastado.
    cp.registrar_evento(directorio, _EVENTO_RESULTADO, {
        "delegacion": delegacion.id, "mision": delegacion.mision_id,
        "capacidad": delegacion.capacidad, "ok": bool(resultado.ok),
        "motivo": resultado.motivo, "agotado": bool(resultado.agotado),
        "evidencia": resultado.evidencia})
    return resultado


# ============================================================ EL CICLO COMPLETO --


def delegar_y_ejecutar(directorio, mision: Mision, autoridad: str, acta: str) -> Resultado:
    """El ciclo de extremo a extremo: delegar → ejecutar → verificar → revocar.

    **La credencial se revoca siempre al terminar**, aunque ya estuviera gastada. Es cinturón y
    tirantes a propósito: el uso único la cierra por contabilidad y la revocación la cierra por
    declaración, y las dos dejan rastro distinto en el historial."""
    delegacion = delegar(directorio, mision, autoridad, acta)
    try:
        return ejecutar(directorio, delegacion, mision)
    finally:
        revocar(directorio, delegacion.id, por=autoridad, motivo="mision terminada")


def historial_de(directorio, delegacion_id: str) -> list[dict]:
    """Todo lo que le pasó a una delegación, en orden. La trazabilidad no se declara: se lee."""
    interesa = (_EVENTO_DELEGADA, _EVENTO_EJECUTADA, _EVENTO_RESULTADO,
                _EVENTO_REVOCADA)
    return [e for e in cp.leer_eventos(pathlib.Path(directorio))
            if e["tipo"] in interesa and e["datos"].get("delegacion") == delegacion_id]


__all__ = ["Mision", "Delegacion", "Resultado", "MisionRechazada", "DelegacionInvalida",
           "PerimetroViolado", "PROFUNDIDAD_MAXIMA", "MISIONES_CONSTRUIDAS", "VIGENCIA_S",
           "delegar", "ejecutar", "delegar_y_ejecutar", "revocar", "esta_revocada", "vigente",
           "usos_de", "historial_de"]
