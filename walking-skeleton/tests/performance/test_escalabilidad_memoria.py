"""Escalabilidad de la memoria (MA.2a).

Deuda R-1/R-2 medida en la auditoria del 2026-07-21 y cuantificada antes de corregirla:

    100 entradas -> 0,81 ms por escritura
  5.000 entradas -> 15,24 ms por escritura (19x)   | escribirlas todas: 76 segundos

Causa: cada `write` reescribia el JSON COMPLETO, de modo que el coste agregado era cuadratico. Con
~50 turnos diarios, un ano de uso son ~18.000 entradas.

Estas pruebas verifican una PROPIEDAD ALGORITMICA, no un tiempo de reloj: que el TRABAJO por
operacion **no crece con el volumen** (items del corpus tocados, entradas de posteo examinadas,
items serializados por escritura). Medir milisegundos seria fragil —a escala de microsegundos el
jitter del planificador supera la senal y la prueba escama bajo carga— y ademas mentiria: lo que
importa no es que sea rapido hoy, sino que el coste algoritmico siga acotado con anos de historial.

Nota sobre D34: generar datos sinteticos para medir ESCALABILIDAD es legitimo; el volumen es la
variable bajo prueba. Seria ilegitimo usarlos para inferir preferencias, donde lo que importa es el
contenido real.
"""

import pytest

from aura_skeleton.modules import memory as memoria_mod
from aura_skeleton.modules.memory import PersistentMemory


async def _sembrar(mem, desde, hasta):
    for i in range(desde, hasta):
        await mem.write("u", "episodica", f"usuario dijo: entrada {i} sobre tema {i % 50}", {"trace_id": str(i)})


async def _serializaciones_por_escritura(tmp_path, n):
    """Cuenta cuantos items se serializan (json.dumps) durante UNA escritura, con n items ya en
    el historial. Una escritura incremental serializa SOLO el item nuevo (1); reescribir el
    historial completo serializaria los n+1 items. Determinista: no depende del reloj.
    """
    mem = PersistentMemory(str(tmp_path / f"w{n}.json"))
    await _sembrar(mem, 0, n)

    original = memoria_mod.json.dumps
    cuenta = 0

    def _contando(*args, **kwargs):
        nonlocal cuenta
        cuenta += 1
        return original(*args, **kwargs)

    memoria_mod.json.dumps = _contando
    try:
        await mem.write("u", "episodica", "entrada nueva para medir la escritura", {"trace_id": "z"})
    finally:
        memoria_mod.json.dumps = original
    return cuenta


@pytest.mark.asyncio
async def test_la_escritura_no_reserializa_el_historial(tmp_path):
    """R-2 como propiedad ALGORITMICA, no temporal.

    La version anterior media el tiempo por escritura con un umbral de razon; a escala de
    microsegundos y bajo carga de CPU escamaba (misma implementacion: 7 de 8 corridas pasaban).

    Aqui se mide TRABAJO: cuantos items se serializan en UNA escritura. La escritura incremental
    serializa solo el item nuevo (1), sea cual sea el volumen; reescribir el historial completo
    serializaria los n+1 items. Determinista e independiente de la maquina.

    Criterio MAS estricto que el anterior: una implementacion que reescribiera el historial no
    puede pasarlo. Verificado contra la regresion real (reescritura total, pre-MA.2a), que lo dispara.
    """
    serial_peq = await _serializaciones_por_escritura(tmp_path, 200)
    serial_gr = await _serializaciones_por_escritura(tmp_path, 2000)  # 10x el historial

    assert serial_gr <= serial_peq and serial_gr <= 2, (
        f"la escritura serializa mas items al crecer el historial: {serial_peq} -> {serial_gr} "
        f"con 10x de volumen. Sintoma de reescribir el historial completo en cada write (R-2)."
    )


class _ItemsContados(list):
    """Envuelve la lista de items del corpus para contar cuantos toca el recall.

    Delega en `list`; no altera el comportamiento, solo instrumenta los accesos.
    """

    def __init__(self, base):
        super().__init__(base)
        self.visitas = 0

    def __getitem__(self, i):
        self.visitas += 1
        return list.__getitem__(self, i)

    def __iter__(self):
        for x in list.__iter__(self):
            self.visitas += 1
            yield x


class _IndiceContado(dict):
    """Envuelve el indice invertido para contar cuantas entradas de posteo examina el recall."""

    def __init__(self, base):
        super().__init__(base)
        self.entradas = 0

    def get(self, clave, defecto=()):
        posteo = dict.get(self, clave, defecto)
        contador = self

        class _Posteo(list):
            def __iter__(self):
                for x in list.__iter__(self):
                    contador.entradas += 1
                    yield x

        return _Posteo(posteo)


async def _trabajo_de_recall(tmp_path, n):
    """Trabajo del recall con n items en el corpus, para la consulta 'xyzzy tema'.

    Devuelve (items del corpus tocados, entradas de posteo examinadas). Determinista:
    no depende del reloj ni de la carga de la maquina.
    """
    mem = PersistentMemory(str(tmp_path / f"m{n}.json"))
    await _sembrar(mem, 0, n)
    await mem.write("u", "semantica", "aguja xyzzy unica", {"trace_id": "needle"})  # 'xyzzy': 1 doc
    items = _ItemsContados(mem._items)
    mem._items = items
    indice = _IndiceContado(mem._indice)
    mem._indice = indice
    items.visitas = 0
    indice.entradas = 0
    await mem.recall("u", "xyzzy tema")  # 'xyzzy' selectivo (1 doc) + 'tema' ubicuo (todo el corpus)
    return items.visitas, indice.entradas


@pytest.mark.asyncio
async def test_el_recall_no_recorre_el_corpus_ni_examina_terminos_ubicuos(tmp_path):
    """R-1 como propiedad ALGORITMICA, no temporal.

    La version anterior media tiempos a escala de microsegundos con un umbral de razon; bajo
    carga de CPU el jitter del planificador superaba la senal y la volvia escamosa (misma
    implementacion y misma data: la razon medida oscilo entre 1,8x y 9,0x segun la carga).

    Aqui se mide TRABAJO, no reloj, y es determinista e independiente de la maquina:
      (1) el recall NO recorre los N items del corpus  -> se apoya en el indice;
      (2) el recall SALTA los terminos ubicuos         -> no examina la lista de posteo que
          abarca todo el corpus.
    Con 10x de historial, ambas magnitudes se mantienen constantes.

    Es un criterio MAS estricto que el anterior: una implementacion que recorriera el corpus
    no puede pasarlo, aunque por azar fuera rapida en una medicion concreta. Verificado contra
    dos regresiones reales: el barrido lineal previo a MA.2a dispara (1); quitar el salto de
    terminos ubicuos dispara (2).
    """
    items_peq, posteo_peq = await _trabajo_de_recall(tmp_path, 300)
    items_gr, posteo_gr = await _trabajo_de_recall(tmp_path, 3000)  # 10x el corpus

    # (1) No recorre el corpus: solo materializa los <=k (k=3) mejores, sin crecer con el volumen.
    assert items_gr <= items_peq and items_gr <= 3, (
        f"el recall toca mas items del corpus al crecer: {items_peq} -> {items_gr} con 10x de "
        f"historial. Sintoma de recorrer el corpus en vez de apoyarse en el indice (R-1)."
    )
    # (2) Salta el termino ubicuo: no examina su lista de posteo, que abarca todo el corpus.
    assert posteo_gr <= posteo_peq and posteo_gr <= 3, (
        f"el recall examina mas entradas de posteo al crecer: {posteo_peq} -> {posteo_gr} con "
        f"10x de historial. Sintoma de no saltar el termino ubicuo (R-1)."
    )


@pytest.mark.asyncio
async def test_el_historial_sobrevive_al_reinicio_con_volumen(tmp_path):
    """La optimizacion no puede costar la persistencia: es la garantia de M1."""
    ruta = str(tmp_path / "m.json")
    mem = PersistentMemory(ruta)
    await _sembrar(mem, 0, 500)

    otra = PersistentMemory(ruta)  # simula reinicio
    hits = await otra.recall("u", "tema 25")

    assert hits, "el historial no sobrevivio al reinicio"
    assert any("tema 25" in h["content"] for h in hits)


@pytest.mark.asyncio
async def test_el_recall_sigue_siendo_correcto_con_volumen(tmp_path):
    """CONTROL: una optimizacion que devolviera resultados peores no seria una mejora."""
    mem = PersistentMemory(str(tmp_path / "m.json"))
    await _sembrar(mem, 0, 1000)
    await mem.write("u", "semantica", "prefiere la luz tenue por la noche", {"trace_id": "x"})

    hits = await mem.recall("u", "luz tenue")

    assert hits, "no encontro un recuerdo que existe"
    assert "tenue" in hits[0]["content"], f"el mejor resultado no es el relevante: {hits[0]['content']!r}"
