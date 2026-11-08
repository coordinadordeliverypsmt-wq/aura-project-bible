"""Tres huecos reales en la cadena `oportunidad -> tarea -> contrato -> review -> executor`
(CEO, 2026-09-20). La cadena YA esta medida como completa hasta la quinta puerta de
`review.ejecutar_bajo_review` (correspondencia tarea<->contrato); lo que falta comprobar es lo que
pasa DESPUES de esa puerta, cuando `ac.ejecutar()` toca el disco de verdad.

HUECO 1 · el efecto no se produce. `ac.ejecutar()` relee el fichero tras escribir y exige que
`buscar` haya desaparecido **y** que `sustituir` este presente. Si `sustituir` contiene `buscar`
como subcadena, la primera mitad de esa comprobacion nunca se cumple aunque la escritura sea
perfectamente valida y `es_sustituible()` la hubiera aprobado antes de escribir. Es una forma
honesta de fallar el efecto sin mentir en ningun otro sitio: la tarea es legitima, el contrato la
autoriza letra por letra, y aun asi el efecto declarado no se sostiene al releer.

HUECO 2 · trazabilidad. Tras una ejecucion valida, el log tiene que dejar rastro suficiente para
reconstruir QUE se autorizo y QUE se aplico sin volver a preguntarle a nadie. Se afirma sobre las
claves que `autoconstruccion.ejecutar()` y `control_plane.registrar_propuesta_autorizada()` escriben
de verdad -leyendo su fuente-, no sobre las que deberian escribir.

HUECO 3 · `autoconstruccion.ciclo()` es una segunda puerta de entrada al mismo ejecutor, y hoy no la
usa ningun modulo de produccion (verificado con grep antes de escribir esta prueba). Es una
propiedad de DISEÑO -que nadie la llame- y se fija leyendo el fuente, como
`test_red_motor_autonomia.py::test_el_motor_NO_ejecuta_por_su_cuenta`: si algun dia alguien conecta
`ciclo()` a un llamante real, esta prueba lo detiene antes de que abra una segunda vía sin la quinta
puerta (`review._exigir_correspondencia_con_el_contrato`), que es exactamente la geometria de
ALERTA-005 otra vez.
"""

from __future__ import annotations

import ast
import pathlib

import control_plane as cp
import contrato as ct
import orquestador as orq
import pytest
import review

ACCION = "implementar_incremento_especificado"


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    """Igual que en `test_red_review_enchufado.py` y `test_red_tarea_atada_a_su_contrato.py`: sin
    esto, una mutacion en curso en OTRA sesion contaminaria estas pruebas via `orq.mutacion_en_curso`."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _contrato_toml(objetivo: pathlib.Path, identificador: str, buscar: str, sustituir: str) -> str:
    """Mismo esqueleto que `test_red_tarea_atada_a_su_contrato.py::_contrato_toml`: los 15 campos
    obligatorios de `contrato.CAMPOS_OBLIGATORIOS`, con la regla de transformacion como unica parte
    que cambia entre pruebas."""
    return f'''
id = "{identificador}"
nombre = "capacidad de prueba"
version = "1"
estado = "AUTORIZADA"
intencion = "ejercitar la cadena completa hasta el ejecutor"
regla_de_transformacion = {{ operacion = "sustituir_texto", buscar = """{buscar}""", sustituir = """{sustituir}""" }}

[[entradas]]
nombre = "fichero"
fuente = "{objetivo}"
formato = "py"

[[salidas]]
resultado = "etiqueta cambiada"
destino = "{objetivo}"

[fuentes_de_verdad]
autoridad = ["{objetivo}"]
referencia = []

[perimetro]
modificables = ["{objetivo}"]
fuera_de_alcance = []

[autoridad]
nivel = "REVIEW"
acta = "DR-E"
parte_de_aura = "aplicar"
parte_del_ceo = "autorizar"

[ejecutor]
verbo = "{ACCION}"

[efectos]
permitidos = ["sustituir una cadena"]
prohibidos = []
reversible = true

[verificacion]
invariantes = ["INV-9"]
pruebas_minimas = ["{objetivo}"]
criterio_de_aceptacion = "la cadena cambio"
evidencia = "cambio_aplicado"

[trazabilidad]
especificacion = "fixture"
autorizacion = "DR-E"
'''


def _montaje(tmp_path, monkeypatch, *, identificador, contenido, buscar, sustituir):
    """REVIEW habilitado para el verbo de evolucion, un fichero real y un contrato que autoriza
    exactamente ese `buscar`/`sustituir` sobre ese fichero. Mismo patron de montaje que
    `test_red_tarea_atada_a_su_contrato.py::_montaje`."""
    objetivo = tmp_path / "observable.py"
    objetivo.write_text(contenido, encoding="utf-8")

    capacidades = tmp_path / "capacidades"
    capacidades.mkdir()
    (capacidades / f"{identificador}.toml").write_text(
        _contrato_toml(objetivo, identificador, buscar, sustituir), encoding="utf-8")
    monkeypatch.setattr(ct, "CONTRATOS", capacidades)

    review.habilitar(tmp_path, alcance=(ACCION,), por="ceo", acta="DR-E del CEO")
    return objetivo


def _tarea(objetivo, identificador, buscar, sustituir) -> dict:
    return {"id": "T-EC", "accion": ACCION, "simbolo": "", "forma": "funcion",
            "fichero": str(objetivo), "operacion": "sustituir_texto",
            "buscar": buscar, "sustituir": sustituir, "contrato": identificador}


def _ejecutar(tmp_path, tarea):
    return review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura",
                                       autoridad="orquestador", verificacion=lambda raiz: True)


# ============================================================ HUECO 1 · EL EFECTO NO SE PRODUCE --


def test_sustitucion_cuyo_texto_nuevo_CONTIENE_el_patron_buscado_revierte_BYTE_A_BYTE(tmp_path, monkeypatch):
    """`ac.ejecutar()` (linea 626): `efecto = (buscar not in tras_el_cambio) and (sustituir in
    tras_el_cambio)`. Si `sustituir` = "ETIQUETA_2" y `buscar` = "ETIQUETA", tras escribir
    "ETIQUETA_2 = 1" la subcadena "ETIQUETA" SIGUE apareciendo -dentro de "ETIQUETA_2"-, asi que la
    primera mitad de la comprobacion es `False` sin que nadie haya mentido en ningun otro sitio:
    `es_sustituible()` aprueba la escritura de antemano (el patron aparece una sola vez, el resultado
    compila) y el contrato autoriza exactamente ese `buscar`/`sustituir`. El efecto declarado
    simplemente no se sostiene al releer, y el ejecutor tiene que revertir."""
    identificador, buscar, sustituir = "capacidad-hueco1", "ETIQUETA", "ETIQUETA_2"
    objetivo = _montaje(tmp_path, monkeypatch, identificador=identificador,
                        contenido="ETIQUETA = 1\n", buscar=buscar, sustituir=sustituir)
    antes = objetivo.read_bytes()

    resultado = _ejecutar(tmp_path, _tarea(objetivo, identificador, buscar, sustituir))

    assert resultado["efecto_verificado"] is False, (
        "el patron seguia presente tras el cambio y el efecto se dio por bueno")
    assert resultado["ejecutado"] is False, "un efecto no verificado no puede contar como ejecutado"
    assert resultado["revertido"] is True
    assert objetivo.read_bytes() == antes, (
        "la reversion no dejo el fichero BYTE A BYTE como estaba antes de escribir")


# ============================================================ HUECO 2 · TRAZABILIDAD --


def test_una_ejecucion_valida_deja_rastro_de_autorizacion_Y_de_cambio_en_el_log(tmp_path, monkeypatch):
    """Se afirma sobre lo que el codigo escribe DE VERDAD, leido de sus dos puntos de escritura:
    `control_plane.registrar_propuesta_autorizada()` (evento `propuesta_autorizada`, con
    `autorizada_por` empezando por `REVIEW:` cuando la autoridad es el circuito) y
    `autoconstruccion.ejecutar()` (evento `cambio_aplicado`, linea 656: el `registro` que construye
    lleva `id`, `fichero`, `efecto_verificado`, `verificacion_sana`, `revertido` y `autoridad`).
    Sin este rastro, reconstruir QUE se autorizo y QUE se aplico exigiria confiar en la memoria de
    quien ejecuto, que es justo lo que el log existe para no tener que hacer."""
    identificador, buscar, sustituir = "capacidad-hueco2", '"activo"', '"finalizado"'
    objetivo = _montaje(tmp_path, monkeypatch, identificador=identificador,
                        contenido=f"ETIQUETA = {buscar}\n", buscar=buscar, sustituir=sustituir)

    resultado = _ejecutar(tmp_path, _tarea(objetivo, identificador, buscar, sustituir))
    assert resultado["ejecutado"] is True, "el camino de control no se ejecuto: no hay nada que trazar"

    eventos = cp.leer_eventos(tmp_path)

    autorizaciones = [e for e in eventos
                      if e["tipo"] == "propuesta_autorizada"
                      and e["datos"].get("id") == resultado["propuesta"]]
    assert len(autorizaciones) == 1, "la propuesta ejecutada no consta autorizada en el log"
    assert autorizaciones[0]["datos"]["autorizada_por"].startswith(cp.PREFIJO_REVIEW), (
        "la autorizacion no declara que vino del circuito de REVIEW")

    cambios = [e for e in eventos
              if e["tipo"] == "cambio_aplicado" and e["datos"].get("id") == resultado["propuesta"]]
    assert len(cambios) == 1, "la ejecucion no dejo un cambio_aplicado en el log"
    datos = cambios[0]["datos"]
    for clave in ("id", "fichero", "efecto_verificado", "verificacion_sana", "revertido", "autoridad"):
        assert clave in datos, f"cambio_aplicado no lleva {clave!r}: la trazabilidad esta incompleta"
    assert datos["fichero"] == str(objetivo)
    assert datos["efecto_verificado"] is True
    assert datos["verificacion_sana"] is True
    assert datos["revertido"] is False
    assert datos["autoridad"] == "orquestador"


# ============================================================ HUECO 3 · SIN CAMINO ALTERNATIVO --


def _modulos_de_produccion(raiz: pathlib.Path):
    """Todo `.py` del plano salvo las pruebas y este mismo fichero: el universo que «produccion»
    cubre. `conftest.py` entra -no es una prueba, es soporte de fixtures- pero no le hace dano:
    no importa `autoconstruccion` ni menciona `ciclo`."""
    for ruta in sorted(raiz.glob("*.py")):
        if ruta.name.startswith("test_") or ruta.name == pathlib.Path(__file__).name:
            continue
        yield ruta


def test_autoconstruccion_ciclo_no_tiene_llamante_de_produccion():
    """`review.py` (docstring de `_exigir_correspondencia_con_el_contrato`) declara la deuda: hoy
    `ac.ciclo()` no tiene ningun llamante de produccion, y por eso la quinta puerta -que vive en
    `ejecutar_bajo_review`, no en `ejecutar`- cubre las dos vias reales sin necesitar una copia
    dentro de `ciclo()`. Esta prueba fija ese hecho leyendo el CODIGO, no la prosa: al estilo de
    `test_red_motor_autonomia.py::test_el_motor_NO_ejecuta_por_su_cuenta`, que advierte exactamente
    de este error -un detector que busca palabras en el fuente entero se encuentra a si mismo en un
    comentario que habla del problema-. Aqui se resuelve mirando solo las llamadas reales: se sigue
    el alias de `import autoconstruccion [as X]` / `from autoconstruccion import ciclo` y se busca un
    `ast.Call` que invoque `ciclo` a traves de ese alias, no la palabra `ciclo` en cualquier sitio
    -que tambien aparece en `Orquestador.ciclo()`, un metodo completamente distinto."""
    raiz = pathlib.Path(__file__).resolve().parent
    culpables = []
    for ruta in _modulos_de_produccion(raiz):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
        alias_del_modulo = set()
        ciclo_importado_directo = False
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    if alias.name == "autoconstruccion":
                        alias_del_modulo.add(alias.asname or "autoconstruccion")
            elif isinstance(nodo, ast.ImportFrom) and nodo.module == "autoconstruccion":
                if any(alias.name == "ciclo" for alias in nodo.names):
                    ciclo_importado_directo = True
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            func = nodo.func
            if (isinstance(func, ast.Attribute) and func.attr == "ciclo"
                    and isinstance(func.value, ast.Name) and func.value.id in alias_del_modulo):
                culpables.append(f"{ruta.name}:{nodo.lineno}")
            elif isinstance(func, ast.Name) and func.id == "ciclo" and ciclo_importado_directo:
                culpables.append(f"{ruta.name}:{nodo.lineno}")

    assert not culpables, (
        f"autoconstruccion.ciclo() gano un llamante de produccion sin su propia quinta puerta: "
        f"{culpables}")
