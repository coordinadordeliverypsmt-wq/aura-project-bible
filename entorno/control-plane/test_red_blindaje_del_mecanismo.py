"""El mecanismo que decide qué se puede tocar, fuera del alcance de quien lo usa (CEO, 2026-09-20).

QUÉ SE MIDIÓ ANTES DE ESCRIBIR ESTO. `_INTOCABLES` protegía 4 ficheros de los 22 módulos de
producción del plano. Los otros 19 eran escribibles por la puerta del anillo —**incluida
`autoconstruccion.py`, que ES la puerta**—. El mecanismo que decide qué es escribible no se
protegía a sí mismo.

POR QUÉ IMPORTA AUNQUE HOY NO SEA EXPLOTABLE. El anillo no puede alcanzar esos ficheros porque
ningún contrato los nombra y `milestones/` está fuera de su zona: la protección era
**circunstancial**, no estructural. Esta prueba la hace estructural. `orquestador.py:56-58` ya lo
dijo: *«un ejecutor que puede reescribir cualquiera de los tres puede concederse lo que quiera en
la iteracion siguiente»* — el argumento vale igual para los cuatro que se añaden aquí.

QUÉ SE PROTEGE, Y POR QUÉ ESTOS CUATRO Y NO TODO EL PLANO. El criterio es **función de
autoridad**, no cantidad:

  · `autoconstruccion.py` — la puerta física: zona + autorización + intocables + PARADA. Si se
    degrada aquí, ningún otro fichero lo restaura. Además aloja la copia local de
    `AUTORIDADES_HUMANAS`, que `review.habilitar` consulta como si fuera la fuente.
  · `review.py`         — define qué significa «autorizado»: materia reservada, alcance, habilitar.
  · `ciclo_autonomo.py` — `clasificar()` decide AUTO/REVIEW/HUMAN para toda tarea, en ambas vías.
  · `planificador.py`   — ensambla `fichero`/`buscar`/`sustituir`; nada aguas abajo comprueba que la
    tarea se corresponda con un contrato.

**No se protege `observatorio.py`**: es el objetivo del primer incremento autorizado y debe seguir
siendo escribible. Esa es la prueba de control, y es la que impide que este blindaje se convierta
en una parálisis.

LO QUE ESTA PRUEBA NO HACE. No retira PARADA, no ejecuta el incremento, no amplía el alcance y no
concede ninguna autoridad nueva: **restringe**. `_INTOCABLES` solo lo consultan la puerta de
escritura del anillo y el evaluador de contratos —ningún hook de git ni el Quality Gate lo
aplican—, así que ampliarla no le añade fricción al CEO ni al CTO, solo al anillo.
"""

from __future__ import annotations

import pathlib

import autoconstruccion as ac
import orquestador as orq
import pytest

#: Los cuatro que el acta del CEO del 2026-09-20 manda proteger, por función de autoridad.
MECANISMO = ("autoconstruccion.py", "review.py", "ciclo_autonomo.py", "planificador.py")


def _intento_de_reescritura(directorio: pathlib.Path, nombre: str) -> dict:
    """Una propuesta legítima en todo salvo en su destino: autorizada por un humano y con acta.

    El caso interesante no es el intento torpe: es el que pasa TODAS las demás puertas. Si la
    barrera de identidad no existe, este intento escribe.
    """
    objetivo = directorio / nombre
    objetivo.write_text("MARCA = 'original'\n", encoding="utf-8")
    p = ac.proponer(directorio, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                                 "buscar": "MARCA = 'original'",
                                 "sustituir": "MARCA = 'reescrito por el anillo'",
                                 "motivo": "el anillo reescribe el mecanismo que lo gobierna"})
    ac.autorizar(directorio, p["id"], por="ceo", acta="acta de prueba 2026-09-20")
    return p


@pytest.mark.parametrize("nombre", MECANISMO)
def test_el_anillo_no_puede_reescribir_el_mecanismo_que_lo_gobierna(tmp_path, nombre):
    """RED el 2026-09-20: los cuatro se reescribían con una propuesta autorizada corriente."""
    d = pathlib.Path(tmp_path)
    p = _intento_de_reescritura(d, nombre)

    with pytest.raises(Exception) as exc:  # noqa: B017 — el tipo lo fija la implementacion
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)

    assert "intocable" in str(exc.value).lower(), (
        f"{nombre}: se detuvo, pero por otra razon distinta de la identidad: {exc.value}"
    )
    assert (d / nombre).read_text(encoding="utf-8") == "MARCA = 'original'\n", (
        f"{nombre} decide la autoridad del anillo y el propio anillo lo reescribio"
    )


@pytest.mark.parametrize("nombre", MECANISMO)
def test_los_cuatro_constan_en_la_barrera(nombre):
    """La barrera se consulta, no se copia: se afirma sobre la tupla real, no sobre una lista local."""
    assert nombre in orq._INTOCABLES, f"{nombre} no esta protegido en orquestador._INTOCABLES"


def test_CONTROL_el_objetivo_del_primer_incremento_SIGUE_siendo_escribible(tmp_path):
    """Sin esto, el blindaje sería indistinguible de una parálisis.

    `observatorio.py` es el destino de OP-100cc3d4e29a bajo el acta DR-E. Protegerlo por error
    dejaría el contrato vigente sin efecto posible, y un blindaje que impide el trabajo autorizado
    no es un blindaje: es una avería.
    """
    d = pathlib.Path(tmp_path)
    objetivo = d / "observatorio.py"
    objetivo.write_text("ETIQUETA = 'antes'\n", encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "ETIQUETA = 'antes'", "sustituir": "ETIQUETA = 'despues'",
                        "motivo": "el incremento autorizado debe seguir siendo posible"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-09-20")

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)

    assert r["efecto_verificado"] is True, "el incremento autorizado dejo de poder aplicarse"
    assert r["revertido"] is False, "el incremento autorizado se revirtio"
    assert objetivo.read_text(encoding="utf-8") == "ETIQUETA = 'despues'\n"


def test_CONTROL_un_fichero_ordinario_del_plano_sigue_siendo_trabajable(tmp_path):
    """La barrera es por IDENTIDAD, no por zona: el resto del plano sigue abierto al trabajo."""
    d = pathlib.Path(tmp_path)
    objetivo = d / "un_modulo_cualquiera.py"
    objetivo.write_text("X = 1\n", encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "X = 1", "sustituir": "X = 2", "motivo": "trabajo ordinario"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-09-20")

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)

    assert r["revertido"] is False and objetivo.read_text(encoding="utf-8") == "X = 2\n"


def test_la_proteccion_se_aplica_por_NOMBRE_RESUELTO_no_por_la_ruta_escrita(tmp_path):
    """Un symlink con nombre inocente que apunta al mecanismo no puede colarse.

    `ejecutar` resuelve la ruta antes de comparar. Sin esa resolucion, bastaria un enlace llamado
    `inocente.py` para escribir en `review.py` — la barrera miraria el nombre equivocado.
    """
    d = pathlib.Path(tmp_path)
    real = d / "review.py"
    real.write_text("MARCA = 'original'\n", encoding="utf-8")
    enlace = d / "inocente.py"
    try:
        enlace.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("el sistema de ficheros no permite enlaces simbolicos")

    p = ac.proponer(d, {"fichero": str(enlace), "operacion": "sustituir_texto",
                        "buscar": "MARCA = 'original'", "sustituir": "MARCA = 'por el enlace'",
                        "motivo": "alcanzar el mecanismo por un nombre inocente"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-09-20")

    with pytest.raises(Exception) as exc:  # noqa: B017
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)

    assert "intocable" in str(exc.value).lower(), f"el enlace se detuvo por otra razon: {exc.value}"
    assert real.read_text(encoding="utf-8") == "MARCA = 'original'\n", (
        "se alcanzo `review.py` a traves de un enlace con nombre inocente"
    )
