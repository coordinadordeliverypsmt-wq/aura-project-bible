"""G-1 · Ruta Única de Mutación — `ESPEC-G-1` §§1–3, §4.1, §4.2 y la corrección §4.5.

**Alcance aprobado por el CEO el 2026-08-17, y solo ese.** Esta prueba implementa el contrato de
G-1, las tres reglas R-A / R-B / R-C y la resolución de receptor por capas. **NO implementa**
`G-2b`, `R-D` ni el plan `M0–M5`, que el documento describe pero el CEO marcó **NO APROBADOS**.
`test_el_verificador_no_implementa_lo_no_aprobado` lo comprueba por ejecución.

**Qué garantiza G-1** (§2.1): para todo módulo de `aura_skeleton/`, ninguna llamada a una operación
mutante persistente aparece salvo que el módulo figure autorizado en `architecture_manifest.toml`.

**Qué NO garantiza, y el documento lo dice**: la ausencia de rutas alternativas. Un análisis estático
sobre un lenguaje dinámico no puede darlo. Lo que consigue es que la clase de defecto de ALERTA-006
—añadir una ruta que muta esquivando el Motor— **deje de ser silenciosa**.

**Decisión §4.5 (CEO, 2026-08-17): `write` NO se renombra** y queda fuera del emparejamiento por
nombre de R-A. Sigue clasificado como mutante a efectos de R-C. El hueco residual está declarado en
la especificación; aquí se fija que la decisión no se revierte por descuido.
"""

from __future__ import annotations

import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

# Importacion dura, no `importorskip`: si el verificador falta, esto debe FALLAR. Un `skip` haria
# invisible su ausencia y la suite saldria verde sin haber comprobado G-1.
import verificador_g1 as verificador  # noqa: E402, I001


# ================================================== CONTRATO Y MANIFIESTO --


def test_g1_el_manifiesto_declara_la_seccion_de_mutaciones():
    """§3.1 · la entrada del verificador vive en el manifiesto, no en código (D41)."""
    m = verificador.manifiesto()
    assert "mutaciones" in m, "el manifiesto no declara [mutaciones]: G-1 no tiene de dónde leer"
    mut = m["mutaciones"]
    assert "motor" in mut, "falta el módulo del Motor Único"
    assert mut.get("almacen"), "falta al menos un [[mutaciones.almacen]] con su superficie"
    assert "persistencia_autorizada" in mut, "falta la lista de módulos que pueden tocar disco (R-B)"


def test_g1_el_conjunto_de_operaciones_excluye_write_por_nombre():
    """§4.5 · decisión del CEO 2026-08-17. `write` NO se persigue por nombre en R-A —es homónimo de
    `fichero.write()` y hundía la resolución de receptor al 40 %— pero **sigue clasificado como
    mutante** a efectos de R-C. Si alguien lo reintrodujese en R-A, G-1 volvería a ser ruido."""
    ra = verificador.operaciones_de_ra()
    clasificadas = verificador.operaciones_clasificadas_mutantes()
    assert "write" not in ra, "`write` no debe perseguirse por nombre en R-A (ESPEC §4.5)"
    assert "write" in clasificadas, "`write` SIGUE siendo mutante para R-C (ESPEC §4.5)"
    # Las cuatro que §4.4 midio al 100 % de resolucion son el MINIMO exigible.
    assert {"olvidar", "marcar", "crear", "desactivar"} <= ra
    # Y el contrato exacto: R-A persigue las mutantes declaradas MENOS las ambiguas. Se comprueba la
    # REGLA, no una lista congelada: si un almacen declara una operacion mutante nueva —que es
    # justo lo que R-C obliga a hacer—, R-A debe recogerla sin que haya que tocar esta prueba.
    assert ra == clasificadas - verificador.EXCLUIDAS_DE_RA


# =========================================================== LAS TRES REGLAS --


def test_g1_ra_ninguna_operacion_de_almacen_fuera_de_los_modulos_autorizados():
    """**R-A** · el caso de ALERTA-006. Una llamada a `olvidar`/`marcar`/`crear`/`desactivar` desde
    un módulo que no es el Motor ni está exceptuado es una violación."""
    violaciones = verificador.violaciones_ra()
    assert not violaciones, verificador.explicar(violaciones)


def test_g1_rb_ninguna_escritura_directa_a_disco_fuera_de_persistencia_autorizada():
    """**R-B** · que nadie esquive R-A escribiendo el fichero a mano."""
    violaciones = verificador.violaciones_rb()
    assert not violaciones, verificador.explicar(violaciones)


def test_g1_rc_todo_metodo_publico_de_un_almacen_esta_clasificado():
    """**R-C** · *«la que da a G-1 vida útil»*. Sin ella G-1 solo protege contra lo que hoy
    conocemos, y un método nuevo escaparía en silencio — que es cómo nació ALERTA-006."""
    violaciones = verificador.violaciones_rc()
    assert not violaciones, verificador.explicar(violaciones)


# ============================================== CASOS DE CONTROL DEL VERIFICADOR --
#
# Sin estos, un verde de las tres reglas no distingue «no hay violaciones» de «el verificador no
# detecta nada». Se ejercita sobre código sintético, nunca sobre el paquete real.


def test_control_el_verificador_detecta_una_llamada_ilegitima(tmp_path):
    fuente = tmp_path / "modulo_intruso.py"
    fuente.write_text(
        "class X:\n"
        "    def __init__(self, mem: PersistentMemory) -> None:\n"
        "        self.mem = mem\n"
        "    def f(self):\n"
        "        return self.mem.olvidar(lambda i: True)\n",
        encoding="utf-8")
    hallazgos = verificador.analizar_fichero(fuente, autorizado_para=frozenset())
    assert any(h.regla == "R-A" and h.operacion == "olvidar" for h in hallazgos), (
        "el verificador NO detecta una llamada ilegítima: cualquier verde suyo sería decorativo")


def test_control_el_verificador_no_acusa_a_un_modulo_autorizado(tmp_path):
    fuente = tmp_path / "modulo_autorizado.py"
    fuente.write_text(
        "class X:\n"
        "    def __init__(self, mem: PersistentMemory) -> None:\n"
        "        self.mem = mem\n"
        "    def f(self):\n"
        "        return self.mem.olvidar(lambda i: True)\n",
        encoding="utf-8")
    hallazgos = verificador.analizar_fichero(fuente, autorizado_para=frozenset({"olvidar"}))
    assert not [h for h in hallazgos if h.regla == "R-A"], "FP-5: un módulo autorizado no se acusa"


def test_control_la_homonimia_de_write_no_genera_falso_positivo(tmp_path):
    """FP-1 y FP-6 · `f.write()` sobre un fichero abierto no es una mutación de almacén. Es
    exactamente el caso que hundía la resolución al 40 % (§4.4)."""
    fuente = tmp_path / "escribe_fichero.py"
    fuente.write_text(
        "def f(ruta):\n"
        "    with open(ruta, 'w') as fh:\n"
        "        fh.write('hola')\n",
        encoding="utf-8")
    hallazgos = verificador.analizar_fichero(fuente, autorizado_para=frozenset())
    assert not [h for h in hallazgos if h.regla == "R-A"], (
        "`fh.write()` no puede acusarse como mutación de almacén")


def test_control_un_receptor_no_resoluble_no_se_reporta_como_violacion(tmp_path):
    """§3.3 capa 4 · decisión de diseño explícita: **ante la duda, el verificador calla**, y lo
    cuenta. Prefiere un falso negativo declarado y contable a un falso positivo que bloquee el
    desarrollo."""
    fuente = tmp_path / "receptor_opaco.py"
    fuente.write_text(
        "def f(cosa):\n"
        "    return cosa.olvidar(lambda i: True)\n",
        encoding="utf-8")
    hallazgos = verificador.analizar_fichero(fuente, autorizado_para=frozenset())
    assert not [h for h in hallazgos if h.regla == "R-A"], "no se acusa a un receptor no resoluble"
    assert verificador.no_resueltos(fuente) >= 1, "pero SÍ se cuenta: el silencio no es olvido"


def test_control_rc_detecta_un_metodo_publico_sin_clasificar(tmp_path):
    fuente = tmp_path / "almacen_con_metodo_nuevo.py"
    fuente.write_text(
        "class Almacen:\n"
        "    def guardar(self):\n"
        "        pass\n"
        "    def _interno(self):\n"
        "        pass\n",
        encoding="utf-8")
    sin_clasificar = verificador.publicos_sin_clasificar(
        fuente, mutantes=frozenset(), neutros=frozenset())
    assert "guardar" in sin_clasificar, "R-C debe exigir clasificar todo `def` público"
    assert "_interno" not in sin_clasificar, "los privados no entran en R-C"


# ================================================ CRITERIO DE FALLO Y ALCANCE --


def test_g1_el_criterio_de_fallo_no_tiene_severidades():
    """§2.4 · *«una garantía con grados deja de ser una garantía»*. El verificador no clasifica
    hallazgos por severidad: o es violación, o no lo es."""
    assert not hasattr(verificador, "SEVERIDADES")
    campos = verificador.Hallazgo.__dataclass_fields__
    for prohibido in ("severidad", "nivel", "aviso", "warning"):
        assert prohibido not in campos, f"un hallazgo con {prohibido!r} introduce grados"


def test_g1_el_mensaje_de_fallo_dice_que_hacer():
    """§2.4 · el mensaje debe nombrar fichero, línea, operación y **qué hacer**."""
    h = verificador.Hallazgo(regla="R-A", fichero="x.py", linea=1, operacion="olvidar",
                             detalle="prueba")
    texto = verificador.explicar([h])
    for exigido in ("x.py", "1", "olvidar", "R-A"):
        assert exigido in texto
    assert "Motor" in texto or "autoriza" in texto, "el mensaje no dice qué hacer"


def test_g1_el_ambito_excluye_tests_y_arneses():
    """FP-3 y FP-4 · construir un almacén y llamar a `olvidar` en una prueba es legítimo."""
    ambito = {str(p) for p in verificador.ambito()}
    assert not any("/tests/" in p for p in ambito), "FP-3: `tests/` fuera de ámbito"
    assert all("/aura_skeleton/" in p for p in ambito), "el ámbito es el paquete de producción"


# ====================================== LO QUE NO ESTÁ AUTORIZADO A EXISTIR --


def _arbol_del_verificador():
    import ast
    return ast.parse((AQUI / "verificador_g1.py").read_text(encoding="utf-8"))


def test_el_verificador_no_implementa_lo_no_aprobado():
    """El CEO marcó `G-2b`, `R-D` y `M0–M5` como NO APROBADOS el 2026-08-17. Que aparezcan descritos
    en el documento histórico no los autoriza.

    La comprobación es **sobre el AST, no sobre el texto**. Una versión anterior buscaba las cadenas
    en el fuente y fallaba al encontrarlas en el propio descargo del verificador —el mismo autoengaño
    que ya costó cuatro pruebas mal escritas en este proyecto—. Lo que importa no es si el nombre se
    menciona: es si hay código que lo implemente."""
    import ast

    arbol = _arbol_del_verificador()

    # R-D prohibiría `getattr` sobre almacenes. No está aprobada: no puede haber detección de
    # `getattr` en ninguna forma.
    llamadas = {n.func.id for n in ast.walk(arbol)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "getattr" not in llamadas, "R-D NO está aprobada: el verificador no inspecciona getattr"

    definidos = {n.name for n in ast.walk(arbol)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    constantes = {n.targets[0].id for n in ast.walk(arbol)
                  if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    for simbolo in definidos | constantes:
        bajo = simbolo.lower()
        assert "getattr" not in bajo, f"{simbolo!r} implementaría R-D"
        assert "g2b" not in bajo and "g_2b" not in bajo, f"{simbolo!r} implementaría G-2b"
        assert "migrar" not in bajo and "migracion" not in bajo, f"{simbolo!r} implementaría M0-M5"


def test_el_verificador_no_toca_produccion():
    """G-1 no añade ni una línea a `aura_skeleton/`: vive en la capa de pruebas, como el verificador
    de manifiesto que ya existe."""
    assert (AQUI / "verificador_g1.py").exists()
    assert "tests" in str(AQUI), "el verificador de G-1 vive en tests/, no en producción"


# =================== CAPA 5 · resolución inter-módulo por conjunto de tipos --
#
# Enmienda `ESPEC-G-1 §3.3` aprobada por el CEO el 2026-08-18 (`D-G1-4`). Las capas 1–3 son
# intra-fichero y no alcanzan al caso real de este proyecto: un atributo **inyectado** cuya clase
# concreta la fija la composición, en otro módulo.
#
# **El éxito de esta capa NO es que G-1 quede verde.** Es que deje de estar ciega: que las cuatro
# rutas de ALERTA-006 pasen de invisibles a detectadas y clasificadas.


def test_capa5_determina_el_conjunto_de_tipos_de_un_atributo_inyectado():
    """`ModeloUsuario._memoria` no se anota ni se construye: se recibe. La evidencia está en
    `composicion.py`, que lo alimenta desde `_memoria_por_nivel()` — y esa función tiene **dos**
    `return` con dos clases distintas."""
    conjunto, _ = verificador.tipos_posibles("ModeloUsuario", "_memoria")
    assert conjunto == {"SemanticMemory", "PersistentMemory"}


def test_capa5_resuelve_un_conjunto_de_un_solo_tipo():
    """`Orchestrator.automatizaciones` viene de una construcción visible y única."""
    conjunto, _ = verificador.tipos_posibles("Orchestrator", "automatizaciones")
    assert conjunto == {"AlmacenReglas"}


def test_capa5_un_tipo_sin_el_metodo_mutante_no_vuelve_gobernada_la_llamada():
    """Prohibición 2 de la enmienda. `SemanticMemory` **no implementa** `olvidar` ni `marcar`; eso
    no convierte la llamada en gobernada — es una **incompatibilidad real** y se registra."""
    _, evidencia = verificador.tipos_posibles("ModeloUsuario", "_memoria")
    faltantes = verificador.tipos_sin_operacion("ModeloUsuario", "_memoria", "olvidar")
    assert "SemanticMemory" in faltantes
    assert any("SemanticMemory" in str(e) for e in evidencia)


def test_capa5_no_asume_un_tipo_cuando_la_evidencia_no_lo_demuestra():
    """Prohibición 1. Una clase que nadie construye ni inyecta no tiene conjunto, y sin conjunto la
    capa 4 sigue mandando: **calla**."""
    conjunto, _ = verificador.tipos_posibles("ClaseQueNadieConstruye", "_lo_que_sea")
    assert conjunto is None, "sin evidencia no se inventa un conjunto"


def test_capa5_la_evidencia_queda_disponible_para_auditoria():
    """Prohibición 4 · el verificador debe poder explicar **por qué** resolvió cada receptor."""
    _, evidencia = verificador.tipos_posibles("Orchestrator", "automatizaciones")
    assert evidencia, "la resolución sin evidencia no es auditable"
    assert any("composicion.py" in str(e) for e in evidencia)


def test_capa5_no_reintroduce_los_falsos_positivos_conocidos(tmp_path):
    """CASO DE CONTROL. La capa 5 no puede reabrir FP-1/FP-6: `str.replace` y los homónimos siguen
    sin acusarse, y un receptor opaco sigue callando."""
    fuente = tmp_path / "homonimos.py"
    fuente.write_text(
        "def f(texto, cosa):\n"
        "    texto = texto.replace('a', 'b')\n"
        "    return cosa.olvidar(lambda i: True)\n",
        encoding="utf-8")
    hallazgos = verificador.analizar_fichero(fuente, autorizado_para=frozenset())
    assert not hallazgos, "la capa 5 no puede introducir falsos positivos"


def test_las_cuatro_rutas_de_alerta_006_aparecen_como_violacion():
    """**La prueba que mide el objetivo del CEO.** Antes de la capa 5, R-A devolvía CERO violaciones
    y las cuatro rutas quedaban como receptores no resolubles. Deben aparecer las cuatro, con su
    fichero, su línea y su operación."""
    violaciones = verificador.violaciones_ra()
    encontradas = {(h.fichero, h.operacion) for h in violaciones}
    esperadas = {
        ("aura_skeleton/core/modelo_usuario.py", "olvidar"),
        ("aura_skeleton/core/modelo_usuario.py", "marcar"),
        ("aura_skeleton/core/orchestrator.py", "crear"),
        ("aura_skeleton/core/orchestrator.py", "desactivar"),
    }
    assert esperadas <= encontradas, (
        f"G-1 sigue ciega a ALERTA-006. Falta detectar: {sorted(esperadas - encontradas)}")
