"""Autorizacion humana **desde la conversacion**: el chat registra una decision, no ejecuta nada.

## Lo que este modulo NO hace, y es lo primero que hay que decir

No ejecuta. No concede permisos. No abre ninguna zona. Lo unico que puede provocar es que una
solicitud que YA estaba en el buzon pase de `pendiente` a `aprobada`. Todo lo demas sigue exactamente
igual: la accion se vuelve a evaluar en el motor unico, con su `dry-run`, y la huella se **recalcula
sobre lo que se va a ejecutar de verdad**. Si el mundo cambio entre la aprobacion y la ejecucion, la
huella es otra, la aprobacion no le sirve y se vuelve a preguntar.

Por eso `chat -> autorizacion` no equivale a `chat -> ejecucion`, y no es una promesa: es una
consecuencia de donde esta escrita la puerta.

## Por que NO hacia falta un modelo nuevo

Ya existia entero:

    accion de lista roja  ->  `hitl_diferido` deniega y ANEXA la solicitud al buzon
    buzon                 ->  `AlmacenDecisiones`: un fichero por huella, `pendiente`
    el CEO responde       ->  `aprobar(huella)`
    el motor despierta    ->  `reabrir_aprobadas()` devuelve la tarea al backlog
    el motor ejecuta      ->  vuelve a preguntar; ahora la huella tiene veredicto

Lo que faltaba era **la superficie**. El propio `aprobar()` lo anticipaba: *«en produccion lo hace el
CEO editando el fichero; este metodo existe para que las pruebas ejerciten el mismo camino y para una
futura interfaz»*. Esto es esa interfaz, y por eso no se toca el circuito.

## Reconocer una autorizacion es decir que NO casi siempre

Una autorizacion mal reconocida abre una accion de lista roja que nadie pidio. La asimetria del dano
manda: **ante la duda, no autoriza**. Tres guardas, en orden, y basta que una se active:

1. **Una pregunta nunca autoriza.** `«¿Puedes ejecutar X?»` pregunta por una capacidad; `«Puedes
   ejecutar X»` da permiso. La diferencia esta en el signo, y es toda la diferencia.
2. **Lo condicional nunca autoriza.** `«creo que podrias»`, `«quiza»`, `«si te parece»`: quien
   matiza no ha decidido todavia.
3. **Hace falta un VERBO de autorizacion explicito.** `«Trabaja en X»` es una orden de trabajo, no un
   permiso — y no esta en la lista, a proposito.

Y una cuarta guarda que sale gratis y vale por las tres: **hace falta un identificador que exista de
verdad**. `«haz lo que consideres»` no nombra nada, asi que no hay nada que autorizar. Un
identificador que no resuelve contra el estado real no autoriza nada; se dice que no se encuentra.
"""

from __future__ import annotations

import re
import unicodedata

#: Los verbos que SI conceden. Lista positiva y cerrada: lo que no esta aqui no autoriza, y anadir
#: algo obliga a escribirlo, que es la unica forma de que la lista no crezca sola.
VERBOS_DE_AUTORIZACION = (
    "autorizo",
    "autorizado",
    "autoriza ",
    "apruebo",
    "aprobado",
    "aprueba ",
    "puedes ejecutar",
    "puedes proceder",
    "procede con",
    "adelante con",
    "doy el visto bueno",
    "le doy el visto bueno",
    "tienes mi permiso",
)

#: Lo condicional no decide. Quien matiza esta pensando en voz alta, no autorizando.
CONDICIONALES = (
    "creo que", "quiza", "quizas", "tal vez", "podrias", "podria", "si quieres", "si te parece",
    "supongo", "imagino", "me parece que", "deberias", "a lo mejor", "no se si",
)


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


#: Un identificador de decision tal y como los produce el sistema: o bien `D-ORCH-6` / `D-INT-1`
#: -las decisiones de gobernanza-, o bien un prefijo de huella en hexadecimal, que es como el propio
#: registro las nombra desde siempre (`huella[:8]`). No se inventa una identidad nueva.
_RE_DECISION = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b")
_RE_HUELLA = re.compile(r"\b[0-9a-f]{6,64}\b")


def identificador_en(texto: str) -> str | None:
    """El identificador nombrado en la frase, o `None` si no nombra ninguno."""
    encontrado = _RE_DECISION.search(texto)
    if encontrado:
        return encontrado.group(0)
    encontrado = _RE_HUELLA.search(texto)
    return encontrado.group(0) if encontrado else None


def es_autorizacion(texto: str) -> str | None:
    """El identificador que se autoriza, o `None` si la frase no es una autorizacion inequivoca.

    Devuelve el identificador en lugar de un booleano a proposito: una autorizacion sin objeto no es
    una autorizacion, asi que las dos preguntas —«¿autoriza?» y «¿el que?»— se responden juntas o no
    se responden."""
    if "?" in texto or "¿" in texto:
        return None
    t = _normalizar(texto)
    if any(c in t for c in CONDICIONALES):
        return None
    if not any(v in t for v in VERBOS_DE_AUTORIZACION):
        return None
    return identificador_en(texto)


def resolver(identificador: str, pendientes: list, aprobadas: list) -> tuple[dict | None, str]:
    """Que decision del buzon nombra ese identificador. Devuelve `(decision, motivo)`.

    Casa por prefijo de huella o por identificador de tarea, y **exige que sea unico**: si dos
    solicitudes empiezan igual, no se elige una — se dice que es ambiguo. Adivinar cual queria el
    usuario seria autorizar una accion de lista roja por su cuenta."""
    aguja = identificador.strip().lower()
    candidatas = [d for d in list(pendientes) + list(aprobadas)
                  if str(d.get("huella", "")).startswith(aguja)
                  or str(d.get("tarea", "")).lower() == aguja]
    if not candidatas:
        return None, "no encontrada"
    huellas = {d.get("huella") for d in candidatas}
    if len(huellas) > 1:
        return None, "ambiguo"
    return candidatas[0], "encontrada"


__all__ = ["es_autorizacion", "identificador_en", "resolver",
           "VERBOS_DE_AUTORIZACION", "CONDICIONALES"]
