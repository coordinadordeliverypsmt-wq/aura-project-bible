"""Development Orchestrator — **C3, C4, C6, C7** del `DP-DEVELOPMENT-ORCHESTRATOR` (F2 + F3).

## Que es, y sobre todo que NO es

Es **infraestructura de desarrollo**, igual que el Control Plane del que es cliente. `§0` del DP:
*«No es AURORA y no le concede ninguna capacidad. La autonomia de AURORA sigue en 0/7 y este DP no la
mueve.»* No importa un solo modulo del producto, y una prueba lo verifica leyendo este fichero.

`§9`: *«El Control Plane sigue siendo la autoridad operacional. El Orchestrator es su cliente.»*

## Lo que puede ejecutar sale de la politica, y solo de ahi

`§25.3` (`D-ORCH-3`) reserva al CEO la lista exacta de acciones automatizables: *«sin lista aprobada,
**todo es HUMAN**»*. El CEO la aprobo el 2026-08-26 y hoy `AUTO` tiene cuatro acciones, nombradas por
el **resultado** que ofrecen y no por la herramienta. `REVIEW` se habilito con `DEC-ORCH-2`, acotado a
`eliminar_codigo_muerto`.

**Este docstring dijo durante cuatro dias que el catalogo estaba vacio, y era falso desde
`D-ORCH-3`.** Lo encontro una auditoria independiente. `INV-9` va en las dos direcciones: no fingir
capacidad que no existe, y no negar la que si — un mensaje falso en una excepcion es lo que alguien
lee justo cuando esta depurando y menos margen tiene para dudar.

Rellenar las listas desde el codigo seguiria siendo conceder autonomia por la puerta de atras, que es
lo que `§10.3` advierte: *«los niveles superiores de autonomia solo se habilitan por politica y
decision del usuario/CEO, nunca automaticamente»*. Por eso `escribir_politica()` existe para negarse.

## Las cuatro prohibiciones de `§5`, hechas codigo

| Componente | Nunca |
|---|---|
| **C3** Orchestrator | decidir politica · editarse a si mismo |
| **C4** WorkerAdapter | ejecutar sin permisos declarados |
| **C6** Policy | ser escrita por C3, C4 o C5 |
| **C7** Presupuesto | inventar cuota |

La ultima no es formalismo: el Control Plane ya documenta que el consumo **no es observable**, asi
que un presupuesto es **un limite que el operador fija**, jamas una medicion de lo que queda.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import tomllib
import uuid

import control_plane as cp

RUTA_POLITICA = pathlib.Path(__file__).resolve().parent / "politica-orquestador.toml"

NIVELES = ("AUTO", "REVIEW", "HUMAN")
NIVEL_POR_DEFECTO = "HUMAN"

# Ficheros que el orquestador no puede tocar **por su propia naturaleza**, no por configuracion: su
# codigo, su politica y la autoridad operacional de la que depende. Un ejecutor que puede reescribir
# cualquiera de los tres puede concederse lo que quiera en la iteracion siguiente.
_INTOCABLES = ("orquestador.py", "politica-orquestador.toml", "control_plane.py", "conftest.py")

# `§7.1`: el sobre lleva punteros, no la historia. Estas restricciones son las permanentes del CEO y
# viajan en **todos** los sobres: no dependen de la tarea.
RESTRICCIONES_PERMANENTES = (
    "no commit", "no push", "no tocar walking-skeleton/",
    "no instalar dependencias", "no usar claves de terceros (D24)",
)


# Modos de permiso que NO anulan la allowlist. Medido `[EJEC]` el 2026-08-30 con `medicion-a11.py`
# contra el binario real: con `--allowedTools Read` y sin `Write`, el fichero **no se crea** en
# `default` ni en `plan`, y **si se crea** en `acceptEdits`. Es decir, `acceptEdits` neutraliza la
# allowlist para las herramientas de edicion.
#
# El `§14` llama a `--allowedTools` *«control primario [EJEC]»* y no menciona que un segundo
# parametro pueda anularlo. Hoy `permisos_de()` devuelve siempre `plan`, asi que el orquestador
# nunca estuvo expuesto — pero nada lo impedia, y una garantia que se sostiene por casualidad no es
# una garantia. `bypassPermissions` estaba prohibido por nombre; este no, y hace lo mismo por otra
# via.
MODOS_QUE_NO_ANULAN_LA_ALLOWLIST = ("plan", "default")


class ModoDePermisoInseguro(RuntimeError):
    """Se intento emitir un sobre con un modo que deja sin efecto la lista de herramientas."""


class PoliticaInmutable(RuntimeError):
    """Alguien intento escribir la politica desde dentro del orquestador (`§5`, C6)."""


class SinPermisosDeclarados(RuntimeError):
    """C4 *«NUNCA: ejecutar sin permisos declarados»*. Fail-closed."""


class EvidenciaNoEstructurada(ValueError):
    """El worker devolvio prosa. `INV-7`: el plan se interpreta en un solo punto y no se
    reinterpreta; una respuesta en lenguaje natural obligaria a interpretarla otra vez."""


# ================================================================= C6 · POLITICA --

def _politica() -> dict:
    with open(RUTA_POLITICA, "rb") as fh:
        return tomllib.load(fh)


def version_de_politica() -> str:
    """Sin version no se puede decir **bajo que reglas** se ejecuto algo, y eso es la mitad de una
    auditoria."""
    return str(_politica().get("version", "desconocida"))


def acciones_de_nivel(nivel: str) -> tuple[str, ...]:
    if nivel not in NIVELES:
        raise ValueError(f"nivel desconocido: {nivel!r}; validos: {NIVELES}")
    seccion = _politica().get(nivel.lower(), {}) or {}
    return tuple(seccion.get("acciones", ()))



def ficha_de(accion: str) -> dict:
    """El contrato completo de una accion AUTO: quien la autoriza, que evidencia exige, que pasa si
    falla y hasta donde puede modificar. Una entrada sin ficha seria una autorizacion sin limites."""
    return dict((_politica().get("auto", {}) or {}).get(accion, {}) or {})


def nivel_de(accion: str) -> str:
    """*«Si no hay regla para una accion, la accion es HUMAN»* (`§10.2`).

    El orden de consulta importa: se busca en AUTO y REVIEW y **se cae** a HUMAN. Buscar primero en
    HUMAN y caer a AUTO seria la misma politica escrita al reves, y con el fallo abierto."""
    for nivel in ("AUTO", "REVIEW"):
        if accion in acciones_de_nivel(nivel):
            return nivel
    return NIVEL_POR_DEFECTO


def escribir_politica(_contenido: dict) -> None:
    """Existe **para negarse**. `§5`: C6 *«NUNCA: ser escrito por C3, C4 o C5»*.

    Tener la puerta cerrada y visible es mejor que no tener puerta: si manana alguien busca como
    cambiar la politica desde el codigo, encuentra este mensaje y no una via alternativa."""
    raise PoliticaInmutable(
        "la politica es un fichero versionado y ningun componente del orquestador puede escribirla "
        f"(§10.2). Para habilitar una accion, el CEO la anade a {RUTA_POLITICA.name} con su acta.")


# ============================================================== C7 · PRESUPUESTO --

class Presupuesto:
    """Topes **por tarea** y **por ciclo** (`§5`, C7).

    No expone «cuanto queda» de nada externo: el Control Plane ya establecio `[EJEC]` que el consumo
    real **no es observable**, y la regla del CEO de 2026-08-04 prohibe publicar un techo que no se
    derive del modelo. Esto es un limite que el operador fija, y solo eso."""

    def __init__(self, por_tarea_usd: float, por_ciclo_usd: float) -> None:
        if por_tarea_usd <= 0 or por_ciclo_usd <= 0:
            raise ValueError("los topes deben ser positivos: un tope de 0 no acota, paraliza")
        self.por_tarea_usd = float(por_tarea_usd)
        self.por_ciclo_usd = float(por_ciclo_usd)

    def permite(self, gastado_en_ciclo: float, coste_previsto: float) -> bool:
        if coste_previsto > self.por_tarea_usd:
            return False
        return (gastado_en_ciclo + coste_previsto) <= self.por_ciclo_usd

    def __repr__(self) -> str:
        return f"Presupuesto(tarea={self.por_tarea_usd}, ciclo={self.por_ciclo_usd})"


PRESUPUESTO_POR_DEFECTO = Presupuesto(por_tarea_usd=0.50, por_ciclo_usd=2.00)


# =========================================================== C4 · WORKERADAPTER --

class WorkerAdapter:
    """Traduce una tarea en el **sobre** de `§7.1` y en la **orden** de `§7.2`, y lee la evidencia
    que vuelve. `§5`: *«NUNCA: ejecutar sin permisos declarados»*.

    **Construir la orden no la lanza.** Lanzarla gasta dinero y pone a trabajar a un agente; eso
    exige una puerta explicita, no un efecto lateral de traducir una tarea. `ejecuciones_reales`
    lleva la cuenta y una prueba comprueba que sigue en cero."""

    def __init__(self) -> None:
        self.ejecuciones_reales = 0

    def huella_de_sobre(self, tarea: dict, presupuesto: Presupuesto | None = None) -> str:
        """`sha256` del sobre canonicalizado. Es la mitad del identificador que dice **que ejecucion
        es esta**, y no solo **de que tarea**."""
        sobre = self.sobre(tarea, presupuesto)
        return hashlib.sha256(
            json.dumps(sobre, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def session_id(self, tarea: dict, presupuesto: Presupuesto | None = None) -> str:
        """`§7.2`: *«El `--session-id` derivado de la tarea es lo que hace la ejecucion
        idempotente»*. Derivado, no aleatorio: dos orquestadores que reciban la misma tarea deben
        producir el mismo id, o el reintento crearia una sesion nueva y perderia la idempotencia.

        **Deriva del SOBRE, no solo del `id`.** El `§13` lo dice con cuatro palabras que son el
        mecanismo entero: *«la misma tarea **con el mismo sobre** produce el mismo identificador»*.
        Derivandolo solo del `id`, dos ejecuciones con permisos, presupuesto, criterio de
        finalizacion o version de politica distintos recibian el **mismo** identificador y el
        orquestador las habria tomado por la misma. Es lo contrario de lo que el mecanismo existe
        para conseguir.

        `uuid5` y no un troceado de `sha256`: el `§13` nombra `uuid5`, y un `uuid5` es recalculable
        desde el contrato —espacio de nombres y version declarados— sin leer esta implementacion."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL,
                              f"aura-orch/{tarea['id']}/{self.huella_de_sobre(tarea, presupuesto)}"))

    def sobre(self, tarea: dict, presupuesto: Presupuesto | None = None) -> dict:
        """`§7.1`, el sobre **minimo suficiente**: *«El sobre no lleva la historia del proyecto.
        Lleva punteros»*. `CHECKPOINT-CONTINUIDAD.md` sigue siendo la autoridad narrativa y el worker
        puede leerlo si lo necesita; inyectarlo «por si acaso» **es** el consumo de contexto que este
        DP existe para reducir."""
        presupuesto = presupuesto or PRESUPUESTO_POR_DEFECTO
        accion = tarea.get("accion", "")
        return {
            "tarea_id": tarea["id"],
            "objetivo": tarea.get("objetivo", ""),
            "contexto_minimo": tarea.get("contexto_minimo", ""),
            "ficheros_relevantes": list(tarea.get("ficheros_relevantes", ())),
            "restricciones": list(RESTRICCIONES_PERMANENTES) + list(tarea.get("restricciones", ())),
            "permisos": self.permisos_de(accion),
            "precondiciones": list(tarea.get("precondiciones", ())),
            "criterio_de_finalizacion": tarea.get("criterio_de_finalizacion", ""),
            "presupuesto": {"max_budget_usd": presupuesto.por_tarea_usd, "max_reintentos": 1},
            "politica": {"version": version_de_politica(), "nivel": nivel_de(accion)},
            "stop": "al cumplir el criterio, PARA. No abras trabajo nuevo.",
        }

    def permisos_de(self, accion: str) -> dict:
        """Los permisos salen de la **politica**, no de la tarea: si viniesen en la tarea, quien la
        redacta se concederia los suyos. Hoy, con `AUTO` vacio, esto devuelve siempre el conjunto
        vacio — y `invocar()` se niega."""
        permisos = ({"allowedTools": [], "permission_mode": "plan"}
                    if nivel_de(accion) != "AUTO"
                    else {"allowedTools": ["Read", "Grep", "Glob"], "permission_mode": "plan"})
        if permisos["permission_mode"] not in MODOS_QUE_NO_ANULAN_LA_ALLOWLIST:
            raise ModoDePermisoInseguro(
                f"{permisos['permission_mode']!r} anula la allowlist: la lista de herramientas "
                f"dejaria de acotar nada. Modos validos: {MODOS_QUE_NO_ANULAN_LA_ALLOWLIST}")
        return permisos

    def orden_de_invocacion(self, tarea: dict, presupuesto_usd: float = 0.50) -> list[str]:
        """La orden literal de `§7.2`, con los flags **verificados en 2.1.233** por el propio DP."""
        sobre = self.sobre(tarea)
        permisos = sobre["permisos"]
        return [
            "claude", "-p", json.dumps(sobre, ensure_ascii=False),
            "--session-id", self.session_id(tarea),
            "--output-format", "json",
            "--allowedTools", ",".join(permisos["allowedTools"]),
            "--permission-mode", permisos["permission_mode"],
            "--max-budget-usd", str(presupuesto_usd),
        ]

    def invocar(self, tarea: dict) -> dict:
        """**Fail-closed.** Traducir una tarea no la lanza: lanzarla gasta dinero y pone a trabajar a
        un agente, y eso exige una autorizacion expresa que hoy no consta. Se niega **siempre**, y
        por dos motivos distintos —sin permisos declarados, o sin autorizacion para ejecutar de
        verdad—, que se distinguen en el mensaje. `INV-9`: no se finge capacidad no construida."""
        accion = tarea.get("accion", "")
        permisos = self.permisos_de(accion)
        if not permisos["allowedTools"]:
            raise SinPermisosDeclarados(
                f"la accion {accion!r} es {nivel_de(accion)} y no tiene permisos declarados. "
                f"Las que si los tienen son {acciones_de_nivel('AUTO')}, y esa lista la fija el CEO "
                f"en la politica (§25.3), nunca este modulo")
        raise SinPermisosDeclarados(
            "ejecutar realmente un worker exige una autorizacion expresa que hoy no consta")

    def leer_evidencia(self, salida: str) -> dict:
        """C4 *«recoger evidencia»*, y estructurada: si volviese prosa, alguien tendria que
        interpretarla, y `INV-7` prohibe reinterpretar el plan."""
        try:
            datos = json.loads(salida)
        except json.JSONDecodeError as exc:
            raise EvidenciaNoEstructurada(
                f"el worker debe devolver JSON conforme al contrato de salida, no prosa: {exc}"
            ) from exc
        if not isinstance(datos, dict):
            raise EvidenciaNoEstructurada(f"la evidencia debe ser un objeto, no {type(datos).__name__}")
        return datos


# ============================================================ C3 · ORCHESTRATOR --

# ================================================ §14 · KILL SWITCH --

NOMBRE_PARADA = "PARADA"


def ruta_parada(directorio) -> pathlib.Path:
    """`§14`: *«fichero centinela consultado en cada iteracion»*, replicando `kill_switch.py:29-31`.

    **No es `ruta_centinela()`.** Aquel es el fichero del `flock` que serializa las escrituras del
    Control Plane y **nunca se borra**; este existe solo mientras alguien quiere parar el bucle.
    Confundirlos dejaria el orquestador parado para siempre desde la primera escritura."""
    return pathlib.Path(directorio) / NOMBRE_PARADA


def parada_solicitada(directorio) -> bool:
    """*«Mecanismo fuera de banda»* (Bible 5.3): basta la **presencia** del fichero. No hace falta
    que el orquestador colabore, ni que haya un proceso al que mandar una senal — que es el punto,
    porque el caso que justifica un kill switch es precisamente aquel en que el sistema esta
    comprometido y su colaboracion no vale nada."""
    return ruta_parada(directorio).exists()


# ============================== §14 · TAREA EQUIVALENTE REPETIDA --


def huella_de_tarea(tarea: dict) -> str:
    """La amenaza del `§14` es *«tarea repetitiva»*, no *«id repetido»*: la huella es del **trabajo**
    y por eso el `id` no entra. Los ficheros se ordenan porque barajar la lista no cambia la tarea, y
    si contase el orden bastaria barajarla para reejecutar indefinidamente."""
    canonico = {
        "accion": tarea.get("accion", ""),
        "objetivo": tarea.get("objetivo", ""),
        "ficheros_relevantes": sorted(tarea.get("ficheros_relevantes", ())),
    }
    return hashlib.sha256(
        json.dumps(canonico, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ================= §14 · EXCLUSION MUTUA CON EL ARNES DE MUTACION --

_MARCA_DEL_ARNES = "herramientas.mutar"


def _hay_proceso_con(marca: str) -> bool:
    """Barrido de `/proc` buscando una marca en la linea de ordenes.

    Esta separado de `mutacion_en_curso()` para poder **ejercitarlo de verdad**. Toda prueba que
    toca el ciclo sustituye `mutacion_en_curso` por una constante —hace falta, o el arnes se detecta
    a si mismo—, asi que el cuerpo real no se ejecutaba en ninguna: el mutante que lo vaciaba
    sobrevivia. Con una marca inventada, una prueba puede comprobar el barrido **sin depender de si
    hay un arnes corriendo**, que es justo lo que no se puede saber desde dentro de un arnes."""
    propio = os.getpid()
    try:
        pids = [entrada for entrada in os.listdir("/proc") if entrada.isdigit()]
    except OSError:                                   # sin /proc no hay nada que mirar
        return False
    for pid in pids:
        if int(pid) == propio:
            continue
        try:
            orden = pathlib.Path("/proc", pid, "cmdline").read_bytes()
        except OSError:                               # el proceso murio mientras lo leiamos
            continue
        if marca.encode("utf-8") in orden:
            return True
    return False


def mutacion_en_curso() -> bool:
    """Mientras `herramientas.mutar` corre, el arbol **no contiene el codigo real**: muta los
    ficheros en el sitio. Medir entonces es medir un mutante y reportarlo como si fuera el producto.
    Ya ocurrio (CEO, 2026-08-09) y estuvo a un paso de declarar rota una garantia que estaba sana.

    Se mira `/proc` y no `pgrep`: es la misma informacion sin depender de un binario externo, y un
    control de seguridad que se cae porque falta una herramienta no es un control. Se excluye el
    proceso propio para que consultar no se detecte a si mismo."""
    return _hay_proceso_con(_MARCA_DEL_ARNES)


# ================== §12 · TAREA EJECUTADA DOS VECES --

def registrar_sesion(directorio, id_tarea: str, session_id: str) -> dict:
    """Deja en el log que **esta ejecucion concreta** ocurrio.

    `§13` promete que la doble ejecucion es *«detectable, no una cuestion de disciplina»*, pero un id
    derivado no detecta nada por si solo: hace falta que alguien mire, y que lo que mira **sobreviva
    al proceso**. Por eso vive en el historial y no en un contador en memoria — el caso que `§12`
    cubre es precisamente el proceso que se murio."""
    return cp.registrar_evento(pathlib.Path(directorio), "sesion_ejecutada",
                               {"id": id_tarea, "session_id": session_id})


def sesion_ya_ejecutada(directorio, session_id: str) -> bool:
    return any(e["tipo"] == "sesion_ejecutada" and e["datos"].get("session_id") == session_id
               for e in cp.leer_eventos(pathlib.Path(directorio)))


# ============================= §14.bis · EL CRITERIO DE FINALIZACION ES MECANICO --


class CriterioInvalido(ValueError):
    """El criterio no nombra una capacidad registrada, o no hay ninguno fijado."""


class CriterioAlterado(RuntimeError):
    """`§14.bis` regla 1: *«un criterio anadido o alterado despues es invalido»*."""


def capacidades_verificables() -> tuple[str, ...]:
    """`§14.bis` regla 2. Salen del **catalogo de la politica**, no de una lista escrita aqui: si
    viviesen en este modulo, ampliarlas seria editar codigo en vez de pedir un acta al CEO."""
    return acciones_de_nivel("AUTO")


def criterio_valido(criterio) -> bool:
    return isinstance(criterio, dict) and criterio.get("capacidad") in capacidades_verificables()


def admite_nivel_auto(tarea: dict) -> bool:
    """`§14.bis` regla 4: *«si el criterio no es expresable como comando, la tarea no es AUTO»*."""
    return criterio_valido(tarea.get("criterio_de_finalizacion"))


def huella_de_criterio(criterio: dict) -> str:
    """La calcula el Control Plane: la puerta que escribe el evento no puede aceptar una huella que
    le den, o criterio y huella se separan. Se reexporta para no tener la formula escrita dos veces."""
    return cp.huella_de_criterio(criterio)


def fijar_criterio(directorio, id_tarea: str, criterio: dict) -> dict:
    """`§14.bis` regla 1: lo fija **quien crea la tarea**, y queda en el log **antes** de invocar."""
    if not criterio_valido(criterio):
        raise CriterioInvalido(
            f"{criterio!r} no nombra una capacidad registrada. Las verificables hoy son "
            f"{capacidades_verificables()}, y se nombran por el resultado, nunca por la herramienta")
    return cp.registrar_criterio_fijado(pathlib.Path(directorio), id_tarea, criterio)


def criterio_registrado(directorio, id_tarea: str) -> dict | None:
    """El criterio fijado, o `None` si no hay ninguno. Repetir el **mismo** criterio es idempotencia
    —un reintento del alta no puede invalidar la tarea—; cambiarlo es el vector que la regla 1
    prohibe: ejecutar cualquier cosa y escribir despues el criterio que esa cosa cumple."""
    fijados = [e["datos"] for e in cp.leer_eventos(pathlib.Path(directorio))
               if e["tipo"] == "criterio_fijado" and e["datos"].get("id") == id_tarea]
    if not fijados:
        return None
    if len({f["huella"] for f in fijados}) > 1:
        raise CriterioAlterado(
            f"el criterio de {id_tarea!r} se altero despues de fijarse "
            f"({len(fijados)} versiones): §14.bis regla 1 lo declara invalido")
    return fijados[0]


def criterio_de(directorio, id_tarea: str) -> dict:
    fijado = criterio_registrado(directorio, id_tarea)
    if fijado is None:
        raise CriterioInvalido(f"{id_tarea!r} no tiene criterio de finalizacion fijado")
    return fijado


def verificar_criterio(directorio, id_tarea: str, ejecutor) -> dict:
    """`§14.bis` regla 3: *«lo ejecuta el Orchestrator, no el Worker; la afirmacion del Worker no
    basta **y no se consulta**»*.

    Esa ultima parte es estructural, no una promesa: **no hay parametro por el que la afirmacion del
    Worker pueda entrar**. Es la misma forma de garantia que el `Veredicto` sin campo `autoriza` —lo
    que no existe en el tipo no se pondera mal mas adelante—.

    El veredicto sale atado a la huella de **su** criterio. Sin esa atadura bastaria verificar la
    tarea mas facil del ciclo y reutilizar su veredicto para las demas."""
    fijado = criterio_de(directorio, id_tarea)
    codigo = int(ejecutor(fijado["criterio"]))
    ok = codigo == 0
    veredicto = {"verificado": ok, "resultado": "VERIFIED" if ok else "NO_VERIFICADO",
                 "comprobacion": f"capacidad {fijado['criterio']['capacidad']} -> exit {codigo}",
                 "origen": "criterio_mecanico", "huella_criterio": fijado["huella"]}
    # Queda en el log, no solo en el valor devuelto: el motor unico lo consulta al cerrar, y si el
    # resultado viviera unicamente en la memoria de quien lo ejecuto no habria nada que consultar.
    cp.registrar_criterio_verificado(pathlib.Path(directorio), id_tarea, fijado["huella"], ok,
                                     veredicto["comprobacion"])
    return veredicto


class Orquestador:
    """El **bucle finito** de `§5`: *«leer estado → elegir tarea ejecutable → invocar → registrar»*.

    Finito no es un detalle de implementacion: un bucle sin cota es un demonio, y este DP no autoriza
    ninguno. `max_iteraciones` es obligatorio y tiene tope por defecto.

    *«NUNCA: decidir politica, editarse a si mismo»*. Lo primero se cumple porque la clasificacion
    vive en `nivel_de()`, fuera de esta clase; lo segundo, porque `puede_tocar()` niega su propio
    fichero, su politica y el Control Plane."""

    MAX_ITERACIONES = 25

    def __init__(self, directorio, presupuesto: Presupuesto | None = None) -> None:
        self.directorio = pathlib.Path(directorio)
        self.presupuesto = presupuesto or PRESUPUESTO_POR_DEFECTO
        self.worker = WorkerAdapter()
        self.gastado_en_ciclo = 0.0

    # --- gobierno de coste (C7) ---
    def puede_gastar(self, coste_previsto: float) -> bool:
        return self.presupuesto.permite(self.gastado_en_ciclo, coste_previsto)

    def registrar_gasto(self, coste: float) -> None:
        self.gastado_en_ciclo += float(coste)

    # --- limites duros (C3) ---
    def puede_tocar(self, ruta) -> bool:
        """Su propio codigo, su politica y la autoridad operacional quedan fuera de su alcance."""
        return pathlib.Path(ruta).name not in _INTOCABLES

    def es_ejecutable(self, tarea: dict) -> bool:
        """*«solo tareas AUTO»* (`§20`, F2), **y con criterio mecanico**.

        Las dos condiciones, no una. `§14.bis` regla 4: *«si el criterio no es expresable como
        comando, la tarea no es AUTO»*. Sin esta mitad, el bucle aceptaba tareas sin criterio y todo
        el aparato del `§14.bis` quedaba **inerte** —lo encontro una auditoria independiente, y es el
        defecto que `CLAUDE.md` pone como ejemplo: el mecanismo existe, tiene sus pruebas en verde y
        no esta enchufado al bucle—."""
        return (nivel_de(tarea.get("accion", "")) == "AUTO"
                and admite_nivel_auto(tarea))

    # --- el bucle ---
    def tareas_candidatas(self) -> list[dict]:
        """Lee el estado **del Control Plane**, que es la autoridad operacional (`§9`)."""
        proyeccion = cp.proyectar(self.directorio)
        candidatas = []
        for evento in cp.leer_eventos(self.directorio):
            if evento["tipo"] != "tarea_registrada":
                continue
            datos = evento["datos"]
            tarea = proyeccion["tareas"].get(datos["id"], {})
            if tarea.get("estado") in ("WAITING_FOR_NEXT_TASK", "FAILED"):
                candidatas.append({**datos, "estado": tarea.get("estado")})
        return candidatas

    def ciclo(self, max_iteraciones: int = 10) -> dict:
        """Un ciclo completo y **acotado**. Registra su principio y su final en el log de F1: un
        ciclo que no deja rastro no es auditable, y F1 existe para que lo deje."""
        tope = min(int(max_iteraciones), self.MAX_ITERACIONES)
        if mutacion_en_curso():
            cp.registrar_evento(self.directorio, "medicion_rechazada_por_mutacion", {"tope": tope})
            return {"iteraciones": 0, "ejecutadas": 0, "motivo": "arnés de mutación en curso",
                    "politica": version_de_politica()}
        cp.registrar_evento(self.directorio, "ciclo_iniciado",
                            {"tope": tope, "politica": version_de_politica()})
        iteraciones, ejecutadas, motivo = 0, 0, "sin tareas ejecutables"
        vistas: set[str] = set()
        for _ in range(tope):
            if parada_solicitada(self.directorio):
                motivo = "kill switch activado"
                cp.registrar_evento(self.directorio, "parada_de_emergencia",
                                    {"iteracion": iteraciones, "ejecutadas": ejecutadas})
                break
            iteraciones += 1
            candidatas = [t for t in self.tareas_candidatas() if self.es_ejecutable(t)]
            if not candidatas:
                motivo = "sin tareas ejecutables"
                break
            frescas = [t for t in candidatas if huella_de_tarea(t) not in vistas]
            if not frescas:
                motivo = "tarea equivalente repetida"
                break
            # `§12`: *«Tarea ejecutada dos veces -> mismo --session-id derivado -> detectada; la
            # segunda no se registra»*. La huella de arriba acota **dentro** de un ciclo y por
            # trabajo; esta acota **entre** ciclos y por (tarea + sobre): dos ejecuciones con el
            # mismo sobre son la misma, y con sobres distintos no lo son.
            sin_correr = [t for t in frescas
                          if not sesion_ya_ejecutada(self.directorio, self.worker.session_id(t))]
            if not sin_correr:
                motivo = "sesión ya ejecutada"
                break
            tarea = sin_correr[0]
            vistas.add(huella_de_tarea(tarea))
            if not self.puede_gastar(self.presupuesto.por_tarea_usd):
                motivo = "presupuesto del ciclo agotado"
                break
            try:
                # `§14.bis` regla 1: **antes** de invocar. Fijarlo despues seria el vector que la
                # regla prohibe — ejecutar cualquier cosa y escribir luego el criterio que cumple.
                fijar_criterio(self.directorio, tarea["id"], tarea["criterio_de_finalizacion"])
                self.worker.invocar(tarea)
                # **Despues**, y solo si la invocacion salio adelante. Escribirlo antes marcaba la
                # sesion como ejecutada aunque `invocar()` se negara — y hoy se niega siempre, asi
                # que quemaba toda tarea AUTO en su primer intento sin ejecutar nada. El `§12` habla
                # de la segunda EJECUCION, no del segundo intento.
                registrar_sesion(self.directorio, tarea["id"], self.worker.session_id(tarea))
            except SinPermisosDeclarados as exc:
                motivo = f"sin permisos declarados: {exc}"
                break
            ejecutadas += 1
        cp.registrar_evento(self.directorio, "ciclo_terminado",
                            {"iteraciones": iteraciones, "ejecutadas": ejecutadas, "motivo": motivo})
        return {"iteraciones": iteraciones, "ejecutadas": ejecutadas, "motivo": motivo,
                "politica": version_de_politica()}
