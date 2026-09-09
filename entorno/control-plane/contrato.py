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


def _acta_consta(acta: str, directorio) -> bool:
    """Si el acta citada existe **en el historial**. Citar un acta que nadie registro es exactamente
    el «declarado != real» que este proyecto lleva once veces pagando."""
    if not acta:
        return False
    for evento in cp.leer_eventos(pathlib.Path(directorio)):
        if acta in str(evento.get("datos", "")):
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
    if not modificables:
        bloqueos.append("el perimetro no declara ningun fichero modificable")
    for ruta in modificables:
        p = pathlib.Path(ruta)
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


__all__ = ["evaluar", "contrato_de", "operacion_valida", "CONTRATOS", "CAMPOS_OBLIGATORIOS", "REQUIERE_INFERENCIA",
           "IMPLEMENTABLE", "BLOQUEADA", "DECLARADA", "ESPECIFICADA", "AUTORIZADA",
           "EJECUTABLE", "VERIFICABLE", "COMPLETADA"]
