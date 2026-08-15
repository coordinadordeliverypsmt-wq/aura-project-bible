"""Centro de Gobierno: la interfaz oficial entre el CEO y AURORA.

PRINCIPIO DE TRAZABILIDAD DE ORIGEN (CEO, 2026-08-04):
**Ninguna seccion mostrara contenido generado por un origen distinto al que declara.**
Si la produce AURORA, se identifica como tal. Si procede del CEO, como decision del CEO. Si procede de
APUS-5 u otra asistencia externa, como aportacion externa. Y si la capacidad no existe, se muestra
"capacidad inexistente" con el motivo REGISTRADO POR EL SISTEMA.

"Prefiero una ausencia declarada a una capacidad simulada." Un Centro de Gobierno que se rellenara con
criterio ajeno mostraria propuestas que parecen de AURORA y no lo son: el patron declarado != real en
el peor sitio posible, la interfaz con la que el CEO decide.

LIMITE MEDIDO EXPERIMENTALMENTE (2026-08-04). AURORA resolvio por si sola 14 de las 16 secciones
—18 vueltas de su propio ciclo, sin intervencion externa—. Las 2 restantes (backlog propuesto y
cambios sugeridos) se bloquearon con `capacidad inexistente`: requieren FORMULAR algo que no esta en
el historial. No es un defecto de plataforma; coincide con todos los analisis previos de dependencia.

ESTE MODULO es andamiaje construido por APUS-5 —el continente—; el CONTENIDO lo produce AURORA.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .decisiones import _MARCA_ESCALADA

AURORA = "AURORA"
CEO = "decision del CEO"
MENTORIA = "mentoria externa (APUS-5)"
INEXISTENTE = "capacidad inexistente"


@dataclass
class Seccion:
    """Una seccion del panel. `origen` es obligatorio: sin el, el contenido no es interpretable."""

    titulo: str
    origen: str
    contenido: str = ""
    motivo: str = ""  # obligatorio cuando el origen es INEXISTENTE

    def __post_init__(self) -> None:
        if self.origen == INEXISTENTE and not self.motivo:
            raise ValueError(f"'{self.titulo}': una capacidad inexistente debe declarar su motivo")
        if self.origen != INEXISTENTE and not self.contenido:
            raise ValueError(f"'{self.titulo}': una seccion con origen declarado debe traer contenido")


def panel(
    diagnostico=None,
    garantias=None,
    ima=None,
    dependencia=None,
    estado=None,
    objetivo: str | list[str] | None = None,
    decisiones=None,
) -> list[Seccion]:
    """Ensambla el panel con lo que AURORA sabe producir HOY. Lo que no, se declara ausente."""
    secciones: list[Seccion] = []

    def _aurora(titulo: str, contenido: str) -> None:
        secciones.append(Seccion(titulo, AURORA, contenido))

    if diagnostico is not None:
        _aurora("Estado actual", diagnostico.get("resumen", "sin resumen"))
        _aurora("Alertas", _alertas(diagnostico))

    if estado is not None and objetivo is not None:
        # D-3 (auditoria independiente, 2026-08-04): mostrar UN objetivo activo y callar el resto
        # firma como [AURORA] una afirmacion falsa — "sin riesgos activos" cuando OTRO objetivo si
        # tenia tareas bloqueadas. `objetivo` admite un id suelto (compatibilidad: un unico bloque,
        # sin prefijo, igual que antes) o una coleccion; con mas de uno, cada bloque queda IDENTIFICADO
        # con su objetivo para que ninguno desaparezca sin avisar ("prefiero una ausencia declarada a
        # una capacidad simulada").
        objetivos = [objetivo] if isinstance(objetivo, str) else list(objetivo)
        multiple = len(objetivos) > 1
        for obj_id in objetivos:
            prefijo = f"[{obj_id}] " if multiple else ""
            tareas = estado.tareas(obj_id)
            abiertas = [t for t in tareas if t.estado in ("abierta", "en_curso")]
            bloqueadas = [t for t in tareas if t.estado == "bloqueada"]
            siguiente = estado.reanudar(obj_id)
            _aurora(f"{prefijo}Que esta haciendo", f"{len(abiertas)} tarea(s) accionables de {len(tareas)}")
            _aurora(f"{prefijo}Que hara despues", siguiente.descripcion if siguiente else "sin trabajo accionable")
            _aurora(f"{prefijo}Que esta bloqueado", _bloqueos(bloqueadas))
            _aurora(
                f"{prefijo}Progreso", f"{sum(1 for t in tareas if t.estado == 'terminada')}/{len(tareas)} terminadas"
            )
            _aurora(f"{prefijo}Backlog activo", "; ".join(f"{t.tarea_id}:{t.descripcion}" for t in abiertas) or "vacio")
            _aurora(f"{prefijo}Riesgos activos", _riesgos(bloqueadas))
            _aurora(f"{prefijo}Recomendaciones derivadas", _recomendaciones(bloqueadas, tareas))

    # EL BUZON, VISIBLE (acta del CEO, 2026-08-10). Pieza 2 hizo que AURORA pida permiso por escrito
    # en vez de autodenegarselo, y 017 que escale cuando deja de insistir; pero ninguna de las dos
    # cosas llegaba AQUI, que es la interfaz oficial. El CEO tenia que acordarse de mirar ficheros
    # JSON sueltos: AURORA pedia permiso por un canal que el CEO no mira.
    #
    # Es LECTURA. No decide, no aprueba, no ejecuta: los permisos, el motor y ADR-0003 no se tocan.
    # Va DESPUES del bloque del estado operativo para no alterar el orden de las secciones que el
    # orquestador ya filtra por sufijo de titulo al responder "¿en que estas trabajando?".
    if decisiones is not None:
        _aurora("Decisiones pendientes", _pendientes(decisiones))
    if estado is not None and objetivo is not None:
        _aurora("Escaladas al CEO", _escaladas(estado, objetivo))

    if garantias is not None:
        _aurora("Garantias", f"{garantias.get('vigentes')}/{garantias.get('declaradas')} vigentes")
    if ima is not None:
        med = [d for d in ima if d.medible]
        _aurora("Metricas · IMA", f"{sum(d.logrado for d in med)}/{sum(d.total for d in med)} en dimensiones medibles")
    if dependencia is not None:
        _aurora("Metricas · Dependencia", "; ".join(_dep(i) for i in dependencia))

    # LIMITE MEDIDO: AURORA no puede formular lo que no esta en el historial. Se declara, no se rellena.
    secciones.append(
        Seccion("Backlog propuesto", INEXISTENTE, motivo="requiere formular trabajo no derivable del historial")
    )
    secciones.append(
        Seccion(
            "Cambios sugeridos", INEXISTENTE, motivo="requiere formular cambios; la generacion depende del modelo local"
        )
    )
    return secciones


def _pendientes(decisiones) -> str:
    """Lo que AURORA espera que el CEO autorice, con el efecto previsto DELANTE.

    Sin la previsualizacion el CEO aprobaria a ciegas, y ADR-0003 dice que eso no satisface el
    consentimiento informado. Se muestran los 12 primeros caracteres de la huella porque es lo que
    identifica el fichero del buzon: con eso el CEO localiza la decision y actua sobre ella.

    Una ausencia de decisiones es informacion util, no una seccion vacia: significa que AURORA no
    espera nada del CEO ahora mismo.
    """
    pendientes = decisiones.pendientes()
    if not pendientes:
        return "ninguna: AURORA no espera ninguna autorizacion"
    lineas = [
        f"{d.get('huella', '')[:12]} · {d.get('accion', '?')} · efecto: {d.get('previsualizacion') or 'sin previsualizacion'}"
        f" · tarea {d.get('tarea') or 'sin tarea'}"
        for d in pendientes
    ]
    return f"{len(pendientes)} esperando tu decision:\n" + "\n".join(f"  - {ln}" for ln in lineas)


def _escaladas(estado, objetivo: str | list[str]) -> str:
    """Tareas en las que AURORA DEJO DE INSISTIR (capacidad 017).

    Se distinguen de una tarea bloqueada cualquiera: una bloqueada esperando aprobacion aun se va a
    reintentar; una escalada no. Confundirlas haria creer al CEO que AURORA se rindio cuando sigue
    trabajando -o al reves, que sigue intentandolo cuando ya paro-.
    """
    objetivos = [objetivo] if isinstance(objetivo, str) else list(objetivo)
    escaladas = [
        t
        for obj_id in objetivos
        for t in estado.tareas(obj_id)
        if t.estado == "bloqueada" and any(_MARCA_ESCALADA in b for b in t.bloqueos)
    ]
    if not escaladas:
        return "ninguna: AURORA no ha agotado los reintentos de ninguna tarea"
    return f"{len(escaladas)} tarea(s) sin mas reintentos:\n" + "\n".join(
        f"  - {t.tarea_id}: {t.descripcion} ({t.intentos} intentos)" for t in escaladas
    )


def _alertas(d: dict) -> str:
    dom = d.get("incidencia_dominante")
    return f"incidencia dominante: {dom[0]} ({dom[1]}x)" if dom else "sin incidencias"


def _bloqueos(bloqueadas) -> str:
    from .autodiagnostico import clasificar_bloqueo

    if not bloqueadas:
        return "nada bloqueado"
    cats: dict[str, int] = {}
    for t in bloqueadas:
        for b in t.bloqueos:
            c = clasificar_bloqueo(b)
            cats[c] = cats.get(c, 0) + 1
    return "; ".join(f"{c}: {n}" for c, n in sorted(cats.items(), key=lambda kv: -kv[1]))


def _riesgos(bloqueadas) -> str:
    return f"{len(bloqueadas)} tarea(s) detenidas" if bloqueadas else "sin riesgos activos registrados"


def _recomendaciones(bloqueadas, tareas) -> str:
    """Derivadas SOLO de hechos. Cada una declara la evidencia que la sustenta."""
    if not bloqueadas:
        return "sin recomendaciones: no hay trabajo detenido"
    por_resp: dict[str, int] = {}
    for t in bloqueadas:
        por_resp[t.responsable] = por_resp.get(t.responsable, 0) + 1
    resp, n = max(por_resp.items(), key=lambda kv: (kv[1], kv[0]))
    pct = round(100.0 * n / len(bloqueadas))
    return (
        f"desbloquear '{resp}' liberaria {n} de {len(bloqueadas)} tareas detenidas ({pct}%) "
        f"— evidencia: {n} tarea(s) bloqueadas con ese responsable en el historial"
    )


def _dep(i) -> str:
    if i.estado != "medible":
        return f"{i.nombre}: NO_MEDIBLE"
    if i.denominador is None:
        return f"{i.nombre}: {i.numerador}"
    return f"{i.nombre}: {i.porcentaje}%"


def publicar(secciones: list[Seccion], ruta: str | os.PathLike[str]) -> str:
    """Vuelca `render(secciones)` en `ruta` para que el CEO lo lea sin Claude Code (PIEZA 3).

    PROYECCION DESECHABLE (ADR-0023): el fichero no lleva estado propio, solo lo que ya esta en
    `secciones`. Borrarlo y volver a publicar da EXACTAMENTE lo mismo — si no fuera asi, el fichero
    seria una segunda fuente de verdad y reabriria el patron "declarado != real".

    ESCRITURA ATOMICA (fichero temporal + `os.replace`): un corte a mitad de escritura no puede dejar
    en disco un panel a medias que el CEO lea como si fuera completo.
    """
    texto = render(secciones)
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    provisional = destino.with_name(destino.name + ".tmp")
    provisional.write_text(texto, encoding="utf-8")
    os.replace(provisional, destino)
    return texto


def render(secciones: list[Seccion]) -> str:
    """El panel, con el ORIGEN de cada seccion siempre visible."""
    filas = ["CENTRO DE GOBIERNO DE AURORA", "=" * 74]
    for s in secciones:
        if s.origen == INEXISTENTE:
            filas.append(f"{s.titulo:<28} [CAPACIDAD INEXISTENTE] {s.motivo}")
        else:
            filas.append(f"{s.titulo:<28} [{s.origen}] {s.contenido}")
    return "\n".join(filas)
