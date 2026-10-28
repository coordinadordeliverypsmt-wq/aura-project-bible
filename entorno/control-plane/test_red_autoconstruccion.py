"""RED · `D-ORCH-2` (parte determinada) + **primera capacidad de autoconstrucción gobernada**.

## Qué parte de `D-ORCH-2` está decidida, y cuál no

**Decidido, y no admite diseño alternativo** (`§10.3`, citando la constitución):

- *«Su autoridad de aprobación **no es delegable a ningún agente**»* — `1.1:93` `[EJEC]`.
- *«El silencio o la ausencia de objeción **no** constituye aprobación»* — `1.1:85` `[EJEC]`.

De ahí sale `C5` tal como `§5` lo define: *«ReviewerAdapter (interfaz) · pedir revisión y devolver un
veredicto estructurado · **NUNCA: autorizar; ser requisito para operar**»*. Y `§273-277` cierra el
cómo: *«ya define `auditor-consistencia` y `arquitecto-evaluador`. **Se usan esos.** No se crea un
revisor nuevo ni se contrata un proveedor»*. **Eso se implementa.**

**No decidido:** si el veredicto de un modelo puede ser **condición previa** para ejecutar una tarea
`REVIEW`. Es `D-ORCH-2` en su parte estrecha, y `§10.3` dice que *«solo el CEO puede concederla»*.
Se registra, no se inventa.

## Los ocho pasos

`OBSERVAR → DIAGNOSTICAR → PROPONER → AUTORIZAR → EJECUTAR → VERIFICAR → REGISTRAR → CONTINUAR`.

La frontera está en **AUTORIZAR**: AURA propone, y solo ejecuta lo que ya tiene autoridad. La
diferencia entre automatización y autonomía gobernada es exactamente esa: no pedir permiso para cada
operación que ya cae dentro de una autorización existente, y no dárselo nunca para las que no.
"""

from __future__ import annotations

import pathlib

import control_plane as cp
import orquestador as orq
import pytest

import autoconstruccion as ac


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    """El `§14` obliga al ciclo a negarse mientras `herramientas.mutar` corre, y el arnes se lanza
    como `python -m herramientas.mutar`: al mutar, el propio arnes aparece en `/proc` y el bucle se
    niega en TODAS las pruebas, no solo en las que miden esa garantia.

    No es un falso positivo del control: es el control funcionando. Estas pruebas trabajan sobre un
    `tmp_path` sintetico y **no miden el arbol real**, asi que lo declaran. Las pruebas de la
    garantia lo vuelven a poner a `True` en su cuerpo, y ganan por ser mas especificas."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)



# ================================================== C5 · ReviewerAdapter (definido) --


def test_c5_el_veredicto_NO_tiene_campo_de_autorizacion():
    """`§10.3`: *«el `Veredicto` carece de campo de autorización»*. Si lo tuviera, un modelo podría
    rellenarlo, y `1.1:93` dice que esa autoridad **no es delegable a ningún agente**."""
    v = ac.Veredicto(revisor="auditor-consistencia", objeciones=(), resumen="sin objeciones")
    campos = set(v.__dataclass_fields__)
    for prohibido in ("autorizado", "aprobado", "permitido", "autoriza", "aprueba"):
        assert prohibido not in campos, f"el veredicto no puede llevar {prohibido}"
    assert not hasattr(v, "aprobar")


def test_c5_ningun_veredicto_produce_una_autorizacion():
    """Ni el más favorable. La autorización solo la crea un acto humano registrado."""
    for objeciones in ((), ("una objeción",), ("dos", "objeciones")):
        v = ac.Veredicto(revisor="arquitecto-evaluador", objeciones=objeciones, resumen="x")
        assert ac.autoriza(v) is False, "ningún veredicto autoriza nada, nunca"


def test_c5_el_silencio_NO_es_aprobacion():
    """`1.1:85`. Una revisión que no llega no puede valer como visto bueno — que es la forma más
    silenciosa de saltarse la autoridad."""
    assert ac.autoriza(None) is False
    assert ac.autoriza(ac.SIN_RESPUESTA) is False


def test_c5_el_revisor_NO_es_requisito_para_operar():
    """`§5`: C5 *«NUNCA: ser requisito para operar»*. Sin revisor, el trabajo `AUTO` sigue."""
    assert ac.revisor_disponible() in (True, False)
    tarea = {"id": "T-1", "accion": "ejecutar_pruebas"}
    assert ac.puede_ejecutarse_sin_revisor(tarea) is True


def test_c5_usa_los_revisores_QUE_YA_EXISTEN():
    """`§273-277`: *«Se usan esos. No se crea un revisor nuevo ni se contrata un proveedor»*."""
    assert set(ac.REVISORES) <= {"auditor-consistencia", "arquitecto-evaluador"}
    for nombre in ac.REVISORES:
        assert (pathlib.Path(ac.RAIZ_AGENTES) / f"{nombre}.md").exists(), f"{nombre} no existe"


# ============================================ LOS OCHO PASOS Y LA FRONTERA DE AUTORIDAD --


def test_el_ciclo_declara_los_ocho_pasos_en_orden():
    assert ac.PASOS == ("observar", "diagnosticar", "proponer", "autorizar",
                        "ejecutar", "verificar", "registrar", "continuar")


def test_observar_y_diagnosticar_NO_modifican_nada(tmp_path):
    """Los dos primeros pasos son lectura pura. Si observar cambiara algo, el diagnóstico describiría
    un estado que él mismo creó."""
    d = pathlib.Path(tmp_path)
    objetivo = d / "sujeto.py"
    objetivo.write_text("def viva():\n    return 1\n\n\ndef _muerta():\n    return 2\n", encoding="utf-8")
    antes = objetivo.read_bytes()
    hallazgos = ac.observar([objetivo])
    ac.diagnosticar(hallazgos)
    assert objetivo.read_bytes() == antes


def test_observar_detecta_una_necesidad_tecnica_REAL(tmp_path):
    """No inventa trabajo: encuentra código muerto que está ahí de verdad."""
    d = pathlib.Path(tmp_path)
    objetivo = d / "sujeto.py"
    objetivo.write_text("def usada():\n    return _auxiliar()\n\n\ndef _auxiliar():\n    return 1\n"
                        "\n\ndef _nunca_llamada():\n    return 2\n", encoding="utf-8")
    hallazgos = ac.observar([objetivo])
    nombres = {h["simbolo"] for h in hallazgos}
    assert "_nunca_llamada" in nombres
    assert "_auxiliar" not in nombres, "está viva: la llama `usada`"
    assert "usada" not in nombres, "las públicas no se tocan: pueden usarse desde fuera"


def test_observar_no_inventa_hallazgos_donde_no_los_hay(tmp_path):
    """**Caso de control.** Si `observar` encontrara algo en un fichero limpio, todo lo demás sería
    ruido."""
    d = pathlib.Path(tmp_path)
    limpio = d / "limpio.py"
    limpio.write_text("def a():\n    return _b()\n\n\ndef _b():\n    return 1\n", encoding="utf-8")
    assert ac.observar([limpio]) == []


def test_proponer_NO_es_autorizar(tmp_path):
    """La frontera. Una propuesta es una petición, y `1.1:85` ya dice que el silencio no la concede."""
    d = pathlib.Path(tmp_path)
    propuesta = ac.proponer(d, {"simbolo": "_x", "fichero": "f.py", "motivo": "código muerto"})
    assert propuesta["estado"] == "PROPUESTA"
    assert propuesta.get("autorizada") is False
    assert ac.esta_autorizada(d, propuesta["id"]) is False


def test_ejecutar_una_propuesta_SIN_autorizacion_es_imposible(tmp_path):
    d = pathlib.Path(tmp_path)
    objetivo = d / "s.py"
    objetivo.write_text("def _m():\n    return 1\n", encoding="utf-8")
    propuesta = ac.proponer(d, {"simbolo": "_m", "fichero": str(objetivo), "motivo": "muerto"})
    with pytest.raises(ac.SinAutorizacion):
        ac.ejecutar(d, propuesta, autoridad="orquestador")
    assert objetivo.read_text(encoding="utf-8") == "def _m():\n    return 1\n", "intacto"


def test_solo_una_AUTORIDAD_HUMANA_autoriza_una_propuesta(tmp_path):
    d = pathlib.Path(tmp_path)
    propuesta = ac.proponer(d, {"simbolo": "_m", "fichero": "s.py", "motivo": "muerto"})
    for no_humano in ("orquestador", "auditor-consistencia", "worker", "aura"):
        with pytest.raises(ac.SinAutorizacion, match="humana"):
            ac.autorizar(d, propuesta["id"], por=no_humano, acta="me autorizo yo")
    ac.autorizar(d, propuesta["id"], por="ceo", acta="acta del CEO 2026-08-26")
    assert ac.esta_autorizada(d, propuesta["id"]) is True


def test_la_autorizacion_exige_ACTA(tmp_path):
    """*«Solo la aprobación explícita del CEO»* — sin constancia de dónde, no es explícita."""
    d = pathlib.Path(tmp_path)
    p = ac.proponer(d, {"simbolo": "_m", "fichero": "s.py", "motivo": "muerto"})
    with pytest.raises(ac.SinAutorizacion, match="acta"):
        ac.autorizar(d, p["id"], por="ceo", acta="")


# ============================================ ZONAS PROHIBIDAS — la frontera dura --


def test_AURA_no_puede_tocar_gobernanza_ni_con_autorizacion(tmp_path):
    """Ni autorizada. Modificar D24, la Bible, un ADR o el roadmap **no es una tarea técnica**: es un
    cambio de gobierno, y el CEO lo hace por acta, no encargándoselo a un ejecutor."""
    d = pathlib.Path(tmp_path)
    for prohibido in ("acta.md", "docs/libro-01-gobernanza-y-metodo/1.1-constitucion.md",
                      "adr/0003-politica.md", "ROADMAP.md", "CLAUDE.md"):
        assert ac.zona_permitida(prohibido) is False, f"{prohibido} debe estar fuera de alcance"
        p = ac.proponer(d, {"simbolo": "x", "fichero": prohibido, "motivo": "y"})
        ac.autorizar(d, p["id"], por="ceo", acta="aunque el CEO lo autorizara")
        with pytest.raises(ac.ZonaProhibida):
            ac.ejecutar(d, p, autoridad="ceo")


def test_el_producto_tampoco_entra_en_esta_primera_capacidad():
    """*«No utilizar una tarea peligrosa como primera demostración»*. El plano de desarrollo sí."""
    assert ac.zona_permitida("walking-skeleton/aura_skeleton/core/permissions.py") is False
    assert ac.zona_permitida("entorno/control-plane/orquestador.py") is True


# ============================================ EJECUCIÓN VERIFICADA Y REVERSIBLE --


def test_el_cambio_es_REVERSIBLE_y_se_revierte_si_la_verificacion_falla(tmp_path):
    """*«pequeña, reversible y completamente verificable»*. Si tras el cambio las pruebas no pasan,
    el cambio se deshace: dejar el árbol roto es peor que no haber hecho nada."""
    d = pathlib.Path(tmp_path)
    objetivo = d / "s.py"
    fuente = "def _muerta():\n    return 1\n"
    objetivo.write_text(fuente, encoding="utf-8")
    p = ac.proponer(d, {"simbolo": "_muerta", "fichero": str(objetivo), "motivo": "muerto"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta")
    resultado = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda: False)
    assert resultado["revertido"] is True
    assert objetivo.read_text(encoding="utf-8") == fuente, "el árbol vuelve a como estaba"


def test_un_cambio_verificado_se_CONSERVA_y_queda_registrado(tmp_path):
    d = pathlib.Path(tmp_path)
    objetivo = d / "s.py"
    objetivo.write_text("def viva():\n    return 1\n\n\ndef _muerta():\n    return 2\n",
                        encoding="utf-8")
    p = ac.proponer(d, {"simbolo": "_muerta", "fichero": str(objetivo), "motivo": "muerto"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta")
    resultado = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda: True)
    assert resultado["revertido"] is False and resultado["efecto_verificado"] is True
    texto = objetivo.read_text(encoding="utf-8")
    assert "_muerta" not in texto and "def viva" in texto
    tipos = [e["tipo"] for e in cp.leer_eventos(d)]
    assert "propuesta_registrada" in tipos and "cambio_aplicado" in tipos
    assert cp.verificar_integridad_log(d)["integro"] is True


def test_AURA_no_declara_exito_sin_comprobar_el_efecto(tmp_path):
    """El punto crítico otra vez: no basta con que el borrado «se haya hecho». Se relee el fichero.

    **Premisa endurecida el 2026-08-31 (segunda barrera).** Antes, proponer un símbolo inexistente
    dejaba que el ejecutor corriera, escribiera el fichero sin cambios y reportara
    `efecto_verificado=False`. Ahora **ni siquiera llega a tocarlo**: `es_eliminable()` se niega antes,
    porque el símbolo no consta en el fichero.

    Las dos garantías siguen vivas y son distintas: *no se declara éxito sin comprobar el efecto*
    —que es lo que esta prueba medía— y *no se escribe un fichero para descubrir después que no había
    nada que borrar*, que es lo que la barrera añade. Se comprueban las dos."""
    d = pathlib.Path(tmp_path)
    objetivo = d / "s.py"
    objetivo.write_text("def _m():\n    return 1\n", encoding="utf-8")
    original = objetivo.read_text(encoding="utf-8")
    p = ac.proponer(d, {"simbolo": "_no_existe_en_el_fichero", "fichero": str(objetivo),
                        "motivo": "muerto"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta")
    with pytest.raises(ac.NoEliminable):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda: True)
    assert objetivo.read_text(encoding="utf-8") == original, "no se toca lo que no hay que tocar"

    # Y la garantía original, con un símbolo que **sí** existe: el efecto se comprueba releyendo.
    real = ac.proponer(d, {"simbolo": "_m", "fichero": str(objetivo), "motivo": "muerto"})
    ac.autorizar(d, real["id"], por="ceo", acta="acta")
    resultado = ac.ejecutar(d, real, autoridad="ceo", verificacion=lambda: True)
    assert resultado["efecto_verificado"] is True
    assert "_m" not in objetivo.read_text(encoding="utf-8")


# ============================================ CICLO COMPLETO Y ENCADENADO --


def test_el_ciclo_completo_encadena_los_ocho_pasos(tmp_path):
    d = pathlib.Path(tmp_path)
    objetivo = d / "s.py"
    objetivo.write_text("def viva():\n    return 1\n\n\ndef _m1():\n    return 2\n"
                        "\n\ndef _m2():\n    return 3\n", encoding="utf-8")
    informe = ac.ciclo(d, [objetivo], autoridad_humana="ceo", acta="acta del CEO",
                       verificacion=lambda: True, max_cambios=5)
    assert informe["observados"] == 2
    assert informe["propuestos"] == 2
    assert informe["autorizados"] == 2
    assert informe["aplicados"] == 2
    texto = objetivo.read_text(encoding="utf-8")
    assert "_m1" not in texto and "_m2" not in texto and "def viva" in texto


def test_el_ciclo_SIN_autoridad_humana_llega_hasta_PROPONER_y_se_detiene(tmp_path):
    """**La frontera de autonomía, medida.** Sin acta, AURA observa, diagnostica y propone — y para.
    Eso es exactamente lo que debe pasar, y por eso no es un fallo."""
    d = pathlib.Path(tmp_path)
    objetivo = d / "s.py"
    objetivo.write_text("def _m():\n    return 1\n", encoding="utf-8")
    informe = ac.ciclo(d, [objetivo], autoridad_humana=None, acta="", verificacion=lambda: True)
    assert informe["propuestos"] == 1
    assert informe["autorizados"] == 0 and informe["aplicados"] == 0
    assert informe["detenido_en"] == "autorizar"
    assert "_m" in objetivo.read_text(encoding="utf-8"), "nada se tocó"


def test_el_ciclo_es_FINITO(tmp_path):
    d = pathlib.Path(tmp_path)
    objetivo = d / "s.py"
    objetivo.write_text("".join(f"def _m{i}():\n    return {i}\n\n\n" for i in range(10)),
                        encoding="utf-8")
    informe = ac.ciclo(d, [objetivo], autoridad_humana="ceo", acta="a",
                       verificacion=lambda: True, max_cambios=3)
    assert informe["aplicados"] <= 3


def test_D_ORCH_2_registra_lo_que_NO_esta_decidido(tmp_path):
    """La parte estrecha de `D-ORCH-2` no se inventa: se registra y se sigue con lo demás."""
    d = pathlib.Path(tmp_path)
    decision = ac.registrar_decision_pendiente(d)
    assert decision["id"] == "D-ORCH-2"
    assert decision["estado"] == "DECISION_REQUIRED"
    assert "REVIEW" in decision["pregunta"]
    assert cp.verificar_integridad_log(d)["integro"] is True


def test_la_gobernanza_se_rechaza_AUNQUE_este_en_zona_permitida(tmp_path):
    """El caso que de verdad distingue las dos comprobaciones: un fichero de gobernanza **dentro**
    de una zona blanca. La lista blanca sola lo dejaría pasar, y un mutante que quitaba el filtro de
    gobernanza sobrevivía porque todas las rutas de prueba caían fuera de la zona por otro motivo.

    Las dos reglas son independientes y ambas deben sostenerse: *estar en zona permitida* no
    convierte a un ADR en código.

    La zona blanca de esta prueba **se declara** (`raiz=d`). Antes no hacía falta porque
    `zona_permitida` aceptaba cualquier ruta bajo `/tmp/` sin condiciones, y esa comodidad era un
    agujero en el guardarrail de producción: 17 pruebas —esta incluida— creían ejercitar la regla
    real y ejercitaban la excepción."""
    d = pathlib.Path(tmp_path)
    for nombre in ("CLAUDE.md", "ROADMAP.md", "acta-d24.md", "CHECKPOINT-CONTINUIDAD.md"):
        dentro = d / nombre
        dentro.write_text("contenido", encoding="utf-8")
        assert ac.zona_permitida(str(dentro), raiz=d) is False, (
            f"{nombre} está en zona blanca pero sigue siendo gobernanza")

    for subdir in ("adr", "docs", "decisiones"):
        (d / subdir).mkdir(exist_ok=True)
        dentro = d / subdir / "cualquier-cosa.md"
        dentro.write_text("x", encoding="utf-8")
        assert ac.zona_permitida(str(dentro), raiz=d) is False, f"{subdir}/ es gobernanza esté donde esté"

    # y el control: un fichero normal en la misma zona sí pasa
    normal = d / "modulo.py"
    normal.write_text("x", encoding="utf-8")
    assert ac.zona_permitida(str(normal), raiz=d) is True
