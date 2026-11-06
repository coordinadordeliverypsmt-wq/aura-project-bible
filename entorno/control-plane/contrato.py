"""`F5` — el evaluador del `CONTRATO-DE-CAPACIDAD`. **Aritmetica sobre campos, no criterio.**

El contrato (`milestones/m3-entry/CONTRATO-DE-CAPACIDAD.md`) define que debe traer una capacidad
para poder construirse. Este modulo lo **aplica**: recibe un contrato y devuelve `IMPLEMENTABLE` o
`BLOQUEADA` con la lista exacta de lo que falta. No decide nada — comprueba.

## Lo que F5 NO hace

No crea capacidades, no completa especificaciones, no decide que significa una capacidad, no inventa
perimetros y **no fabrica ejecutores**. Solo consume capacidades que ya satisfacen el contrato.

## Por que no es una autorizacion global

La evaluacion es **por capacidad**. Las nueve condiciones se comprueban contra los mecanismos que ya
existen —`fuente_verificable()`, `zona_permitida()`, el acta del log, `_EJECUTORES_CONSTRUIDOS`,
`_MATERIA_RESERVADA`—, asi que F5 no añade ninguna puerta nueva: **encadena las que ya estaban**.

La consecuencia importa: el unico ejecutor construido es `eliminar_codigo_muerto` y el acta delega
solo eso, de modo que F5 **no puede producir trabajo fuera de la autoridad vigente**. Amplia lo que
AURA puede emprender por su cuenta, nunca lo que puede tocar.

## El orden importa

Los bloqueos se evaluan **antes** que la implementabilidad: la gobernanza habla primero. Una
capacidad que cumpliera las nueve condiciones y a la vez tocara materia reservada queda bloqueada.

**Solo lectura.** No escribe, no registra eventos, no ejecuta. Una prueba lo fija leyendo el fuente.
"""

from __future__ import annotations

import pathlib
import re

import tomllib

import autoconstruccion as ac
import control_plane as cp
import descubrimiento as des
import orquestador as orq
import planificador as pl
import review as rv

#: Los estados del contrato. `IMPLEMENTABLE` y `BLOQUEADA` son los unicos que este modulo emite: los
#: demas describen el recorrido y los fija el documento, no el evaluador.
DECLARADA, ESPECIFICADA, AUTORIZADA = "DECLARADA", "ESPECIFICADA", "AUTORIZADA"
IMPLEMENTABLE, EJECUTABLE, VERIFICABLE = "IMPLEMENTABLE", "EJECUTABLE", "VERIFICABLE"
COMPLETADA, BLOQUEADA = "COMPLETADA", "BLOQUEADA"

#: Los 15 del contrato. Sin uno solo, la capacidad no es evaluable: es el mismo criterio que
#: `descubrimiento.PIEZAS_OBLIGATORIAS` aplica a una oportunidad.
CAMPOS_OBLIGATORIOS = (
    "id", "nombre", "version", "estado", "intencion", "entradas", "salidas",
    "regla_de_transformacion", "fuentes_de_verdad", "perimetro", "autoridad",
    "ejecutor", "efectos", "verificacion", "trazabilidad")

#: Valor declarado para «esto no lo resuelve una regla». Nombrarlo es mejor que dejarlo vacio: un
#: hueco se confunde con un olvido, y esto es una propiedad de la capacidad.
REQUIERE_INFERENCIA = "REQUIERE_INFERENCIA"

#: **Donde viven los contratos.** Fuera de `entorno/control-plane/` a proposito: `zona_permitida()`
#: devuelve `False` para `milestones/`, asi que AURA **no puede escribir su propio contrato**. La
#: alternativa examinada —una seccion `[capacidad.<id>]` en `politica-orquestador.toml`— quedaba
#: DENTRO de la zona y su proteccion dependia de una guardia; aqui la frontera es estructural. Y
#: ademas separa lo que la arquitectura ya separa: la politica gobierna **acciones del orquestador**,
#: no especifica **que construir**. TOML, no Markdown: el consumo tiene que ser determinista.
CONTRATOS = pathlib.Path(__file__).resolve().parents[2] / "milestones" / "m3-entry" / "capacidades"

#: La raiz del repositorio y el directorio de este plano, para resolver entradas de
#: `fuera_de_alcance` que llegan como ruta relativa (al repo o al plano) en vez de absoluta.
_RAIZ_REPO = pathlib.Path(__file__).resolve().parents[2]
_DIR_PLANO = pathlib.Path(__file__).resolve().parent

#: **Nombres de fichero reconocidos como referencia al mecanismo de autoridad, aunque aparezcan
#: como palabra suelta dentro de prosa** (sin `/` delante). `orquestador._INTOCABLES` se consulta en
#: vivo -no se copia- y se completa con los tres ficheros que la propia gobernanza del contrato ya
#: nombra en `etiqueta-observatorio-efecto.toml`: *"review.py, contrato.py, autoconstruccion.py y el
#: resto del mecanismo de autoridad"*. Fuera de este conjunto, una palabra suelta en prosa NO basta
#: para bloquear -evita el falso positivo de tratar cualquier `.py` mencionado al pasar como una
#: prohibicion-, y dentro de el, basta con el nombre -ADR-0003, ante la duda, roja-.
_NOMBRES_AUTORIDAD_RECONOCIDOS = frozenset(orq._INTOCABLES) | {
    "review.py", "contrato.py", "autoconstruccion.py"}

#: Un token de prosa "tiene pinta de fichero" si termina en `/` (directorio), contiene un separador
#: de ruta, o termina en una extension reconocible (`.py`, `.toml`, `.md`, `.json`, `.jsonl`, ...).
#: Palabras sin extension y sin `/` (`permisos`, `kill_switch`, `PARADA`) NO cuentan como referencia
#: a fichero salvo que esten en `_NOMBRES_AUTORIDAD_RECONOCIDOS`: es la frontera declarada entre
#: "interpretar prosa reconocible" y "exigir forma estructurada", documentada en el contrato del
#: incremento en vez de dejarla implicita.
_PATRON_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,6}$")


def _tokens_de_prosa(entrada: str):
    """Los fragmentos separables de una entrada de `fuera_de_alcance`, sin la puntuacion de prosa
    que los rodea (comas, parentesis, espacios). Cada fragmento se evalua por su cuenta como
    posible referencia a fichero o directorio."""
    for fragmento in re.split(r"[,\s()]+", entrada):
        fragmento = fragmento.strip()
        if fragmento:
            yield fragmento


def _token_referencia_fichero(token: str) -> bool:
    return ("/" in token) or token.endswith("/") or bool(_PATRON_EXTENSION.search(token))


def _resolver_relativa(token: str) -> pathlib.Path | None:
    """Resuelve un token relativo probando primero contra la raiz del repositorio y despues
    contra este plano -las dos formas en que un contrato real cita una ruta no absoluta-.
    `None` si el token no resulta en una ruta utilizable."""
    for base in (_RAIZ_REPO, _DIR_PLANO):
        try:
            return (base / token).resolve()
        except OSError:
            continue
    return None


def _invade_fuera_de_alcance(modificable: pathlib.Path, entradas) -> bool:
    """Si `modificable` cae dentro de lo que el propio contrato declaro `fuera_de_alcance`.

    **Fail-closed por diseno (ADR-0003).** Cada entrada puede ser una ruta exacta o prosa con
    nombres de fichero incrustados; nunca se compara por substring -un fichero vecino con nombre
    parecido no se confunde con el citado-, siempre por ruta real resuelta o por segmento de ruta
    completo. Ver el docstring del modulo de pruebas para la justificacion completa de por que la
    prosa se trata asi y no de otra forma."""
    try:
        real = modificable.resolve()
    except OSError:
        real = modificable
    segmentos_reales = {p for p in real.parts}

    for entrada in entradas or []:
        entrada = str(entrada)
        for token in _tokens_de_prosa(entrada):
            if not _token_referencia_fichero(token):
                continue
            if token.endswith("/"):
                nombre_dir = token.rstrip("/")
                if nombre_dir and nombre_dir in segmentos_reales:
                    return True
                continue
            candidato = pathlib.Path(token)
            if candidato.is_absolute():
                try:
                    if candidato.resolve() == real:
                        return True
                except OSError:
                    if candidato == real:
                        return True
                continue
            if "/" in token:
                resuelto = _resolver_relativa(token)
                if resuelto is not None and resuelto == real:
                    return True
                continue
            # Token bare, sin `/`: solo cuenta como referencia si es un nombre reconocido del
            # mecanismo de autoridad. El resto de la prosa sin ruta y sin extension reconocible ya
            # se descarto en `_token_referencia_fichero`; esto descarta el caso restante: un `.py`
            # bare que NO es una autoridad conocida, para no bloquear por una coincidencia de
            # nombre entre dos ficheros distintos que comparten basename por azar.
            if token in _NOMBRES_AUTORIDAD_RECONOCIDOS and real.name == token:
                return True
    return False


def contrato_de(identificador: str):
    """El contrato de una capacidad, leido de `CONTRATOS/<id>.toml`, o `None` si no lo hay.

    **Una sola fuente y sin respaldo silencioso.** Si el fichero no esta, o esta y no se puede leer,
    la respuesta es `None` —y `None` significa `SIN_CONTRATO`, que bloquea—. Un segundo sitio donde
    mirar convertiria la ausencia en «todavia no he mirado bastante», que es como nacen las fuentes
    de verdad encubiertas que `ADR-0023 §4` describe.

    Un TOML ilegible **no se ignora en silencio**: cuenta como ausente, que es fail-closed. Preferir
    lo contrario seria dejar que un fichero corrupto pase por contrato."""
    ruta = CONTRATOS / f"{identificador}.toml"
    if not ruta.is_file():
        return None
    try:
        return tomllib.loads(ruta.read_text(encoding="utf-8")) or None
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError):
        return None


def operacion_valida(regla) -> bool:
    """Si una `regla_de_transformacion` estructurada declara una operacion **del vocabulario**.

    Una regla puede ser prosa —el caso de `eliminar_codigo_muerto`, cuya transformacion es fija y
    esta en el codigo— o una operacion estructurada. Si es lo segundo, el nombre tiene que estar en
    `autoconstruccion.OPERACIONES`: lo que no esta catalogado no se interpreta."""
    if not isinstance(regla, dict):
        return False
    return regla.get("operacion") in ac.OPERACIONES


def _identificador_de_acta(acta: str) -> str:
    """El IDENTIFICADOR de un acta: lo que va antes del separador. Es su identidad, no su prosa.

    El formato real registrado es `«DR-D · acta del CEO 2026-09-07: K_ESTANCAMIENTO = 100»`, asi que
    el identificador es el primer campo. Se compara eso y no el texto entero porque la prosa puede
    reescribirse y la identidad no.
    """
    return acta.split("·")[0].split(":")[0].strip()


def _acta_consta(acta: str, directorio) -> bool:
    """Si el acta citada existe **en el historial**. Citar un acta que nadie registro es exactamente
    el «declarado != real» que este proyecto lleva once veces pagando.

    **SE COMPARA LA IDENTIDAD, NO UN FRAGMENTO (CEO, 2026-09-16).** Antes esto era
    `acta in str(evento.get("datos", ""))`: una comparacion de SUBSTRING contra el volcado entero del
    evento. Medido: citar `acta = "D"` en un contrato bastaba para acreditar autorizacion, porque esa
    letra aparece dentro de los datos de algun evento. Un trozo de texto no es un acta.

    Ahora se lee el campo ESTRUCTURADO `datos["acta"]` —que ya existia en `review_habilitado` y en
    `propuesta_autorizada`— y se comparan identificadores. No es una autoridad nueva: es la
    comprobacion que esta funcion siempre dijo hacer, haciendose de verdad.
    """
    if not acta:
        return False
    citado = _identificador_de_acta(str(acta))
    if not citado:
        return False
    for evento in cp.leer_eventos(pathlib.Path(directorio)):
        datos = evento.get("datos")
        if not isinstance(datos, dict):
            continue
        registrada = str(datos.get("acta", ""))
        if registrada and _identificador_de_acta(registrada) == citado:
            return True
    return False


def evaluar(contrato: dict, *, directorio, tarea: str | None = None) -> dict:
    """`IMPLEMENTABLE` o `BLOQUEADA`, con lo que falta y por que. **Lectura pura.**

    Devuelve `{"estado", "faltantes", "bloqueos"}`. `faltantes` son campos obligatorios ausentes;
    `bloqueos` son condiciones de gobernanza incumplidas. Un contrato puede tener las dos cosas."""
    contrato = contrato or {}

    # **Completada se pregunta primero, y al historial.** No es una cuestion de especificacion —el
    # contrato seguiria siendo perfecto— sino un hecho ya ocurrido, y `ADR-0023` dice donde viven los
    # hechos: *«la unica informacion persistente con valor semantico es el historial de eventos»*.
    #
    # El mecanismo ya existia (`planificador.completada`) y no se duplica: se consulta. Y no se mira
    # el fichero a proposito — un cambio a mano produciria el mismo texto sin ninguna ejecucion
    # gobernada detras, y eso no es haber completado nada.
    if tarea and pl.completada(pathlib.Path(directorio), tarea):
        return {"estado": COMPLETADA, "faltantes": [], "bloqueos": []}

    faltantes = [c for c in CAMPOS_OBLIGATORIOS if not contrato.get(c)]
    bloqueos: list[str] = []

    ejecutor = contrato.get("ejecutor") or {}
    verbo = ejecutor.get("verbo", "")

    # 1 · Gobernanza primero, siempre. Una accion reservada no se evalua: se rechaza.
    if verbo and rv.es_materia_reservada(verbo):
        bloqueos.append(f"{verbo!r} es materia reservada al CEO (D22)")

    # 2 · Sin regla determinista no hay que construir, hay que decidir.
    regla = contrato.get("regla_de_transformacion")
    if regla == REQUIERE_INFERENCIA:
        bloqueos.append("la regla de transformacion exige inferencia: lo decide un humano")
    elif isinstance(regla, dict) and not operacion_valida(regla):
        bloqueos.append(f"{regla.get('operacion')!r} no esta en el vocabulario {ac.OPERACIONES}")

    # 3 · Toda entrada tiene que poder ir a mirarse.
    for entrada in contrato.get("entradas") or []:
        if not des.fuente_verificable(str(entrada.get("fuente", ""))):
            bloqueos.append(f"la entrada {entrada.get('nombre')!r} cita una fuente que no existe")

    # 4 · El perimetro manda, y lo dice `zona_permitida`, no el contrato.
    perimetro = contrato.get("perimetro") or {}
    modificables = perimetro.get("modificables") or []
    fuera_de_alcance = perimetro.get("fuera_de_alcance") or []
    if not modificables:
        bloqueos.append("el perimetro no declara ningun fichero modificable")
    for ruta in modificables:
        p = pathlib.Path(ruta)
        # **`fuera_de_alcance` se comprueba siempre, no en `elif`.** Un contrato que se contradice
        # a si mismo -el mismo fichero en `modificables` y en `fuera_de_alcance`- tiene que
        # bloquearse por esa contradiccion en concreto, y no solo cuando ademas falle alguna otra
        # comprobacion. Antes de este incremento el campo no se leia nunca: cero apariciones de
        # `fuera_de_alcance` en este modulo.
        if _invade_fuera_de_alcance(p, fuera_de_alcance):
            bloqueos.append(f"{ruta} esta declarado fuera de alcance por el propio contrato")
        if not p.is_file():
            bloqueos.append(f"{ruta} no existe: un perimetro no se declara sobre lo que no esta")
        elif p.name in orq._INTOCABLES:
            # **La barrera no se copia: se consulta.** `orquestador._INTOCABLES` ya es la autoridad
            # —*«su codigo, su politica y la autoridad operacional... un ejecutor que puede
            # reescribir cualquiera de los tres puede concederse lo que quiera en la iteracion
            # siguiente»*—. Tener aqui una segunda lista con la misma politica era la copia que este
            # proyecto ya ha pagado: dos guardias tapandose, y ninguna al descubierto cuando falla.
            bloqueos.append(f"{p.name} es intocable para el orquestador: no entra en un perimetro")
        elif not ac.zona_permitida(p):
            bloqueos.append(f"{ruta} esta fuera de la zona permitida")

    # 5 · El acta tiene que constar en el historial, y el verbo estar en su alcance.
    autoridad = contrato.get("autoridad") or {}
    if not _acta_consta(autoridad.get("acta", ""), directorio):
        bloqueos.append(f"el acta {autoridad.get('acta')!r} no consta en el historial")
    elif verbo and not rv.en_alcance(pathlib.Path(directorio), verbo):
        bloqueos.append(f"{verbo!r} esta fuera del alcance que el acta habilito")

    # 6 · `INV-9`: no se finge capacidad no construida.
    if verbo and verbo not in rv._EJECUTORES_CONSTRUIDOS:
        bloqueos.append(f"no existe ejecutor construido para {verbo!r} (INV-9)")

    # 7 · Irreversible es rojo (ADR-0003: ante la duda, roja).
    if not (contrato.get("efectos") or {}).get("reversible"):
        bloqueos.append("el efecto no se declara reversible")

    # 8 · Sin prueba no hay forma de saber si salio bien.
    verificacion = contrato.get("verificacion") or {}
    pruebas = verificacion.get("pruebas_minimas") or []
    if not pruebas:
        bloqueos.append("no se declara ninguna prueba minima")
    for prueba in pruebas:
        if not pathlib.Path(prueba).is_file():
            bloqueos.append(f"la prueba {prueba} no existe")

    estado = BLOQUEADA if (faltantes or bloqueos) else IMPLEMENTABLE
    return {"estado": estado, "faltantes": faltantes, "bloqueos": bloqueos}


def _misma_ruta(a, b) -> bool:
    try:
        return pathlib.Path(str(a)).resolve() == pathlib.Path(str(b)).resolve()
    except OSError:
        return pathlib.Path(str(a)) == pathlib.Path(str(b))


def corresponde_tarea_a_contrato(tarea, contrato) -> bool:
    """`OBJETIVO 4.2`. Si una TAREA (con la forma que `planificador.a_tarea()` produce hoy:
    `fichero`, `operacion`, `buscar`, `sustituir`) es consistente con lo que un CONTRATO concreto
    autoriza. **Funcion pura, fallo cerrado (ADR-0003): ante cualquier ambiguedad, `False`.**

    **Lo que esto NO resuelve por si solo:** no descubre CUAL contrato autorizo una tarea. No hace
    falta que lo descubra: desde el 2026-09-20 `planificador.a_tarea()` traslada el identificador en
    `tarea["contrato"]`, y `review._exigir_correspondencia_con_el_contrato()` —quinta puerta de
    `ejecutar_bajo_review`, antes de cualquier escritura— lo usa para cargar el contrato citado y
    llamar a esta funcion. Esta decide, y quien pregunta aporta el candidato. Lo que SI hace: dado
    un contrato candidato, decide si la tarea se mantiene
    DENTRO de lo que ese contrato autorizo -mismo fichero, dentro del perimetro y no en
    `fuera_de_alcance`, misma operacion y mismos textos `buscar`/`sustituir` cuando la regla los
    declara-. Sirve para verificar la tarea contra el contrato que se afirma que la autoriza; no para
    descubrir esa autoria por su cuenta."""
    if not isinstance(tarea, dict) or not isinstance(contrato, dict):
        return False

    fichero_tarea = tarea.get("fichero")
    if not fichero_tarea:
        return False

    perimetro = contrato.get("perimetro") or {}
    modificables = perimetro.get("modificables") or []
    if not modificables or not any(_misma_ruta(fichero_tarea, m) for m in modificables):
        return False
    if _invade_fuera_de_alcance(pathlib.Path(str(fichero_tarea)),
                                perimetro.get("fuera_de_alcance") or []):
        return False

    regla = contrato.get("regla_de_transformacion")
    # `REQUIERE_INFERENCIA` (o ausencia de regla): nadie ejecuta lo que exige decision humana.
    if regla is None or regla == REQUIERE_INFERENCIA:
        return False

    operacion_tarea = tarea.get("operacion") or "eliminar_codigo_muerto"

    if isinstance(regla, dict):
        if not operacion_valida(regla):
            return False
        return (operacion_tarea == regla.get("operacion")
                and tarea.get("buscar") == regla.get("buscar")
                and tarea.get("sustituir") == regla.get("sustituir"))

    # Regla en prosa: hoy solo existe para `eliminar_codigo_muerto` (la transformacion fija que
    # `es_eliminable()`/`quitar_simbolo()` ya implementan). Una tarea de eliminacion no lleva texto
    # de sustitucion; si lo lleva, no es la operacion que la regla en prosa describe, sin importar
    # el nombre que la tarea declare.
    return (operacion_tarea == "eliminar_codigo_muerto"
            and not tarea.get("buscar") and not tarea.get("sustituir"))


__all__ = ["evaluar", "contrato_de", "operacion_valida", "corresponde_tarea_a_contrato",
           "CONTRATOS", "CAMPOS_OBLIGATORIOS", "REQUIERE_INFERENCIA",
           "IMPLEMENTABLE", "BLOQUEADA", "DECLARADA", "ESPECIFICADA", "AUTORIZADA",
           "EJECUTABLE", "VERIFICABLE", "COMPLETADA"]
