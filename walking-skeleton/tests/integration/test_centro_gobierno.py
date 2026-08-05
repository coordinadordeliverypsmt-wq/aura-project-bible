"""Integracion: el Centro de Gobierno declara el ORIGEN de cada seccion y sus limites.

PRINCIPIO DEL CEO (2026-08-04): ninguna seccion mostrara contenido generado por un origen distinto al
que declara. "Prefiero una ausencia declarada a una capacidad simulada."
"""

import tempfile

import pytest

from aura_skeleton.core.centro_gobierno import AURORA, INEXISTENTE, Seccion, panel, publicar, render
from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea

# NOTA (auditoria independiente, 2026-08-04): las 5 correcciones D-1..D-5 debajo cierran el rechazo
# de la PIEZA 3. D-1/D-5 anaden pruebas donde antes solo habia una IMPLEMENTACION correcta sin RED DE
# GARANTIAS -- el auditor demostro con mutantes concretos (append, .tmp huerfano, escritura directa)
# que las 22 pruebas previas no morian. D-2 corrige una prueba DECORATIVA (comparaba resultados entre
# si, nunca contra la fuente). D-3 es una correccion de DISENO (CEO, via auditoria): el panel debe
# cubrir TODOS los objetivos activos, no solo el primero alfabetico.


def _estado():
    """Estado con bloqueos REALES, reproducidos sin componer el sistema: las pruebas no deben
    ejecutar el Quality Gate para comprobar como se presenta un panel."""
    alm = AlmacenEstadoOperativo(tempfile.mkdtemp() + "/e.jsonl")
    for i, (r, motivo) in enumerate(
        [
            ("qa", "veredicto negativo: 2 garantias ya no protegen nada"),
            ("programador", "detenida: dry-run no viable: un cambio necesita fichero y patron"),
            ("programador", "detenida: dry-run no viable: un cambio necesita fichero y patron"),
            ("documentacion", "ningun ejecutor atiende al responsable 'documentacion'"),
        ],
        1,
    ):
        alm.registrar(
            Tarea(
                objetivo_id="cg",
                tarea_id=f"t-{i}",
                descripcion=r,
                estado="bloqueada",
                responsable=r,
                origen="ceo",
                bloqueos=[motivo],
            )
        )
    return alm


def test_TODA_seccion_declara_su_origen():
    for s in panel(estado=_estado(), objetivo="cg"):
        assert s.origen, f"'{s.titulo}' no declara origen: el contenido no seria interpretable"


def test_una_capacidad_inexistente_NO_se_rellena_con_contenido_ajeno():
    """EL PRINCIPIO: mostrar propuestas que parecen de AURORA y no lo son seria declarado != real
    en la interfaz con la que el CEO decide."""
    secs = {s.titulo: s for s in panel(estado=_estado(), objetivo="cg")}
    for titulo in ("Backlog propuesto", "Cambios sugeridos"):
        assert secs[titulo].origen == INEXISTENTE
        assert secs[titulo].contenido == "", "una capacidad inexistente no puede traer contenido"
        assert secs[titulo].motivo, "debe declarar POR QUE no existe"


def test_una_capacidad_inexistente_SIN_MOTIVO_es_un_error():
    """No basta con declarar la ausencia: hay que decir por que, o el limite no entra al backlog."""
    with pytest.raises(ValueError, match="motivo"):
        Seccion("X", INEXISTENTE)


def test_una_seccion_con_origen_declarado_DEBE_traer_contenido():
    """CONTROL simetrico: declarar AURORA y no traer nada seria la simulacion inversa."""
    with pytest.raises(ValueError, match="contenido"):
        Seccion("X", AURORA, "")


def test_las_recomendaciones_declaran_la_evidencia_que_las_sustenta():
    """No opiniones: cada recomendacion dice de que dato sale."""
    secs = {s.titulo: s for s in panel(estado=_estado(), objetivo="cg")}
    rec = secs["Recomendaciones derivadas"].contenido
    assert "evidencia:" in rec, f"una recomendacion sin evidencia es una opinion: {rec}"
    assert "programador" in rec, "debe señalar al responsable que mas trabajo detiene"


def test_el_panel_hace_VISIBLES_los_limites():
    txt = render(panel(estado=_estado(), objetivo="cg"))
    assert "[CAPACIDAD INEXISTENTE]" in txt, "los limites deben verse, no ocultarse"
    assert txt.count("[AURORA]") >= 5, "y lo que AURORA si produce debe atribuirsele"


def test_CONTROL_sin_datos_no_se_inventan_secciones():
    """Sin estado ni diagnostico solo quedan las capacidades inexistentes declaradas."""
    secs = panel()
    assert all(s.origen == INEXISTENTE for s in secs), "sin datos no puede haber contenido de AURORA"


# --- publicar(): la PROYECCION DESECHABLE del panel en disco (ADR-0023, PIEZA 3) ------------------
#
# `publicar` no es una segunda fuente de verdad: es `render(panel(...))` volcado a un fichero para
# que el CEO pueda leerlo sin Claude Code. Por eso el contrato es simetrico al de una proyeccion: el
# fichero no lleva NADA que no pueda derivarse de `secciones`, y borrarlo + regenerarlo no puede
# cambiar el comportamiento del sistema ni el contenido publicado.


def test_publicar_escribe_EXACTAMENTE_el_render_de_las_secciones(tmp_path):
    secciones = panel(estado=_estado(), objetivo="cg")
    ruta = tmp_path / "sub" / "CENTRO-DE-GOBIERNO.md"

    texto = publicar(secciones, ruta)

    assert texto == render(secciones)
    assert ruta.read_text(encoding="utf-8") == render(secciones)


def test_publicar_crea_el_directorio_padre_si_no_existe(tmp_path):
    ruta = tmp_path / "no-existe-todavia" / "CENTRO-DE-GOBIERNO.md"
    assert not ruta.parent.exists()

    publicar(panel(estado=_estado(), objetivo="cg"), ruta)

    assert ruta.exists()


def test_publicar_es_una_PROYECCION_DESECHABLE(tmp_path):
    """ADR-0023: borrar el fichero y volver a publicar debe reproducir EXACTAMENTE la FUENTE
    (`render(secciones)`), no solo coincidir entre si.

    D-2 (auditoria independiente, 2026-08-04): la version anterior comparaba `segundo == primero` y
    nunca contra la fuente. El auditor demostro con un doble que un `publicar()` que IGNORA su
    argumento y siempre escribe "CONSTANTE FABRICADA" pasaria esa comparacion igual: los dos
    resultados coincidirian entre si aunque ninguno reflejara `secciones`. Comparar contra
    `render(secciones)` cierra ese hueco."""
    ruta = tmp_path / "CENTRO-DE-GOBIERNO.md"
    secciones = panel(estado=_estado(), objetivo="cg")
    esperado = render(secciones)

    primero = publicar(secciones, ruta)
    ruta.unlink()
    segundo = publicar(secciones, ruta)

    assert primero == esperado, "publicar() no devolvio la fuente en la primera pasada"
    assert segundo == esperado, "publicar() no devolvio la fuente tras borrar y regenerar"
    assert ruta.read_text(encoding="utf-8") == esperado


def test_publicar_SOBRESCRIBE_no_ACUMULA_al_republicar_sobre_fichero_EXISTENTE(tmp_path):
    """D-1 BLOQUEANTE (auditoria independiente, 2026-08-04): si `publicar()` abriera en modo append
    en vez de sobrescribir, el panel del CEO CRECERIA SIN LIMITE en cada ciclo -- el auditor lo
    reprodujo: 10 lineas -> 20 -> 30 con la suite en verde, porque ninguna prueba anterior republicaba
    sobre un fichero YA EXISTENTE sin borrarlo antes. Esto ademas anularia la mitigacion de espacio en
    disco que el DP exige. Aqui se publica DOS VECES sobre el MISMO fichero, sin `unlink()` de por
    medio, y se compara byte a byte contra la fuente."""
    ruta = tmp_path / "CENTRO-DE-GOBIERNO.md"
    secciones = panel(estado=_estado(), objetivo="cg")
    esperado = render(secciones)

    publicar(secciones, ruta)
    publicar(secciones, ruta)  # SIN unlink(): el caso exacto que explota un `publicar()` en modo append

    contenido = ruta.read_text(encoding="utf-8")
    assert contenido == esperado, "el fichero no coincide con la fuente tras republicar sin borrar"
    assert contenido.count("CENTRO DE GOBIERNO DE AURORA") == 1, (
        "el fichero crecio: republicar ACUMULO contenido en vez de SOBRESCRIBIR"
    )


def test_publicar_NO_deja_ficheros_TMP_huerfanos(tmp_path):
    """D-1/D-5 (auditoria independiente, 2026-08-04): la escritura atomica pasa por un `.tmp` que debe
    desaparecer siempre. Si el reemplazo (`os.replace`) no llega a ejecutarse, ese temporal queda
    huerfano en disco para siempre y el CEO veria residuos de la implementacion junto a su panel."""
    ruta = tmp_path / "CENTRO-DE-GOBIERNO.md"

    publicar(panel(estado=_estado(), objetivo="cg"), ruta)

    huerfanos = list(tmp_path.glob("*.tmp"))
    assert huerfanos == [], f"quedaron ficheros temporales sin limpiar: {huerfanos}"
    assert ruta.exists()


def test_publicar_usa_os_replace_para_la_ESCRITURA_ATOMICA(tmp_path, monkeypatch):
    """D-5 (auditoria independiente, 2026-08-04): la atomicidad NO se puede observar por el contenido
    final -- una escritura directa sobre el destino produce, en el caso feliz, el MISMO fichero que
    escribir-a-temporal-y-reemplazar. Por eso se verifica que la implementacion pasa de verdad por
    `os.replace`, que es la garantia real ante un corte a mitad de escritura (docstring de
    `publicar()`, lineas 145-146): sin esta prueba esa garantia estaba PROCLAMADA pero no protegida."""
    import aura_skeleton.core.centro_gobierno as cg

    llamadas: list[tuple[str, str]] = []
    original = cg.os.replace

    def _espia(origen, destino):
        llamadas.append((str(origen), str(destino)))
        return original(origen, destino)

    monkeypatch.setattr(cg.os, "replace", _espia)

    ruta = tmp_path / "CENTRO-DE-GOBIERNO.md"
    publicar(panel(estado=_estado(), objetivo="cg"), ruta)

    assert llamadas, "publicar() no uso os.replace: la escritura ya no es atomica"
    origen, destino = llamadas[0]
    assert origen.endswith(".tmp"), f"el origen del reemplazo deberia ser el fichero temporal, fue: {origen}"
    assert destino == str(ruta)


# --- D-3: el panel debe CUBRIR TODOS los objetivos activos (auditoria independiente, 2026-08-04) --
#
# DECISION DE DISENO (CEO, via auditoria): un panel que muestra un objetivo y CALLA otro firma como
# [AURORA] una afirmacion falsa -- "sin riesgos activos" cuando OTRO objetivo si tenia tareas
# bloqueadas fue el defecto exacto que reprodujo el auditor eligiendo `activos[0]` (el primero
# alfabetico). La correccion: `panel()` itera TODOS los objetivos recibidos e identifica cada bloque
# con su id cuando hay mas de uno.


def test_panel_CUBRE_TODOS_los_objetivos_activos_y_los_IDENTIFICA(tmp_path):
    """Reproduce la forma exacta del bug que encontro el auditor: con DOS objetivos activos, el
    PRIMERO alfabetico sin riesgos y el SEGUNDO con tareas bloqueadas, `activos[0]` mostraria solo el
    tranquilo y ocultaria el peligroso. Dos secciones "Riesgos activos" sin mas serian ademas
    indistinguibles entre si: cada bloque debe declarar A CUAL objetivo pertenece."""
    alm = AlmacenEstadoOperativo(str(tmp_path / "e.jsonl"))
    alm.registrar(
        Tarea(
            objetivo_id="aaa-sin-riesgo",
            tarea_id="t-1",
            descripcion="ok",
            estado="abierta",
            responsable="qa",
            origen="ceo",
        )
    )
    alm.registrar(
        Tarea(
            objetivo_id="zzz-con-riesgo",
            tarea_id="t-1",
            descripcion="detenida",
            estado="bloqueada",
            responsable="programador",
            origen="ceo",
            bloqueos=["detenida: dry-run no viable: un cambio necesita fichero y patron"],
        )
    )

    secciones = panel(estado=alm, objetivo=["aaa-sin-riesgo", "zzz-con-riesgo"])
    por_titulo = {s.titulo: s.contenido for s in secciones}

    assert "[aaa-sin-riesgo] Riesgos activos" in por_titulo, "el objetivo sin riesgos perdio su identificacion"
    assert "[zzz-con-riesgo] Riesgos activos" in por_titulo, "el objetivo CON riesgos desaparecio del panel"
    assert por_titulo["[aaa-sin-riesgo] Riesgos activos"] == "sin riesgos activos registrados"
    assert "1 tarea(s) detenidas" in por_titulo["[zzz-con-riesgo] Riesgos activos"], (
        "los riesgos reales del segundo objetivo no llegaron al panel"
    )


def test_panel_con_UN_SOLO_objetivo_en_lista_NO_prefija_los_titulos(tmp_path):
    """CONTROL de compatibilidad: con un unico objetivo activo (el caso mas comun hoy) los titulos
    deben seguir siendo los de siempre, sin prefijo -- ninguna de las pruebas anteriores de este
    fichero (que pasan `objetivo="cg"` como cadena) deberia romperse por esta correccion."""
    secciones = panel(estado=_estado(), objetivo=["cg"])
    titulos = {s.titulo for s in secciones}

    assert "Riesgos activos" in titulos
    assert "[cg] Riesgos activos" not in titulos


def test_publicar_CONTROL_el_contenido_CAMBIA_si_el_estado_cambia(tmp_path):
    """CONTROL NEGATIVO: si el contenido publicado no cambiara al cambiar el estado, las pruebas de
    arriba solo demostrarian que `publicar` escribe *algo* en disco, no que escribe el ESTADO REAL."""
    ruta = tmp_path / "CENTRO-DE-GOBIERNO.md"

    publicar(panel(estado=_estado(), objetivo="cg"), ruta)
    con_bloqueos = ruta.read_text(encoding="utf-8")

    vacio = AlmacenEstadoOperativo(str(tmp_path / "vacio.jsonl"))
    publicar(panel(estado=vacio, objetivo="cg"), ruta)
    sin_bloqueos = ruta.read_text(encoding="utf-8")

    assert con_bloqueos != sin_bloqueos, "el panel publicado no reflejo el cambio de estado"
