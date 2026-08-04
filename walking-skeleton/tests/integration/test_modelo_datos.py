"""Integracion: el sistema verifica por si mismo su MODELO DE DATOS FUNDAMENTAL.

El principio: la unica informacion persistente con valor semantico es el historial. Todo lo demas
—proyecciones, indices, caches— debe poder borrarse y regenerarse sin alterar el comportamiento.

Este protocolo es GENERICO: no prueba el Estado Operativo, prueba *un componente descrito por cuatro
funciones*. Sirve igual para cualquier componente futuro.

PRIMER CASO DE PRUEBA: la Memoria incumple, y el protocolo debe DETECTARLO (decision del CEO: no se
arregla todavia; se comprueba que la garantia sabe verlo).
"""

import asyncio

from aura_skeleton.core.estado_operativo import AlmacenEstadoOperativo, Tarea
from aura_skeleton.core.modelo_datos import CUMPLE, VIOLA, Componente, informe, verificar
from aura_skeleton.core.reglas import AlmacenReglas, ReglaUsuario
from aura_skeleton.modules.memory import PersistentMemory


def _estado_operativo():
    def operar(a):
        a.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta", responsable="qa"))

    return Componente(
        nombre="Estado Operativo",
        construir=AlmacenEstadoOperativo,
        operar=operar,
        observar=lambda a: [(t.tarea_id, t.estado) for t in a.tareas("o")],
        proyeccion=lambda a: a._tareas,
        retirar=lambda a: a.transitar("o", "t-01", "descartada", autoridad="test", causa="ya no hace falta"),
    )


def _automatizaciones():
    def operar(a):
        a.crear(
            ReglaUsuario(
                rule_id="r1", user_id="u", evento="action.command", condicion={}, accion="copiar_archivo", args={}
            )
        )

    return Componente(
        nombre="Automatizaciones",
        construir=AlmacenReglas,
        operar=operar,
        observar=lambda a: [(r.rule_id, r.estado) for r in a._reglas],
        proyeccion=lambda a: a._reglas,
        retirar=lambda a: a.desactivar("u", "r1"),
    )


def _memoria():
    def operar(m):
        asyncio.run(m.write("u", "semantica", "un hecho cualquiera", {}))
        asyncio.run(m.write("u", "semantica", "otro hecho distinto", {}))

    return Componente(
        nombre="Memoria",
        construir=PersistentMemory,
        operar=operar,
        observar=lambda m: [i["content"] for i in m._items],
        proyeccion=lambda m: m._items,
        # REESCRIBE el fichero desde la proyeccion: aqui se destruye el historial.
        retirar=lambda m: m.olvidar(lambda i: "otro" in i["content"]),
    )


def test_el_estado_operativo_CUMPLE_el_principio(tmp_path):
    v = verificar(_estado_operativo(), str(tmp_path / "e.jsonl"))
    assert v.clasificacion == CUMPLE, f"fallo: {v.fallidas} — {v.detalle}"


def test_las_automatizaciones_CUMPLEN_el_principio(tmp_path):
    """Desactivar anexa una linea nueva en vez de reescribir: es el modelo a imitar."""
    v = verificar(_automatizaciones(), str(tmp_path / "r.jsonl"))
    assert v.clasificacion == CUMPLE, f"fallo: {v.fallidas} — {v.detalle}"


def test_LA_MEMORIA_VIOLA_EL_PRINCIPIO_Y_EL_PROTOCOLO_LO_DETECTA(tmp_path):
    """PRIMER CASO DE PRUEBA (CEO): no se arregla; se verifica que la garantia sepa verlo.

    `PersistentMemory._persist` reescribe el fichero DESDE `self._items`, asi que la proyeccion es la
    fuente de verdad y el historial su volcado: la direccion esta invertida. Es el mismo defecto que
    ALERTA-006 encontro por la via de seguridad.
    """
    v = verificar(_memoria(), str(tmp_path / "m.jsonl"))

    assert v.clasificacion == VIOLA, f"el protocolo NO detecto el incumplimiento conocido: {v}"
    assert "nada vive solo en la proyeccion" in v.fallidas, f"detecto otra cosa: {v.fallidas}"


def test_el_protocolo_es_reutilizable_sin_conocer_el_componente(tmp_path):
    """No hay ramas por tipo: el verificador solo usa las cuatro funciones de la descripcion."""
    veredictos = [
        verificar(_estado_operativo(), str(tmp_path / "a.jsonl")),
        verificar(_automatizaciones(), str(tmp_path / "b.jsonl")),
        verificar(_memoria(), str(tmp_path / "c.jsonl")),
    ]
    assert [v.clasificacion for v in veredictos] == [CUMPLE, CUMPLE, VIOLA]
    txt = informe(veredictos)
    assert "Memoria" in txt and "viola" in txt


def test_un_componente_que_no_persiste_nada_viola_el_principio(tmp_path):
    """CONTROL: sin historial no hay fuente de verdad, por mucho que el comportamiento sea correcto."""
    c = Componente(
        nombre="Volatil",
        construir=lambda ruta: {"datos": []},
        operar=lambda d: d["datos"].append(1),
        observar=lambda d: d["datos"],
        proyeccion=lambda d: d["datos"],
    )
    v = verificar(c, str(tmp_path / "no-existe.jsonl"))
    assert v.clasificacion == VIOLA and "fuente de verdad persistente" in v.fallidas


def test_se_detecta_un_componente_que_NO_reconstruye_igual(tmp_path):
    """La comprobacion 4 necesitaba su propio caso: los tres componentes reales reconstruyen bien.

    Lo detecto la mutacion (M3 sobrevivia). Este componente escribe al historial pero conserva
    ademas un dato SOLO en memoria: al reconstruir, ese dato desaparece y el comportamiento cambia.
    Es exactamente el fallo que el principio quiere impedir.
    """
    from pathlib import Path

    class ConDatoVolatil:
        def __init__(self, ruta):
            self.ruta = Path(ruta)
            self.items = (
                [x for x in self.ruta.read_text(encoding="utf-8").splitlines() if x] if self.ruta.exists() else []
            )
            self.solo_en_memoria = []  # nunca se persiste: se pierde al reconstruir

        def operar(self):
            with open(self.ruta, "a", encoding="utf-8") as f:
                f.write("persistido\n")
            self.items.append("persistido")
            self.solo_en_memoria.append("volatil")

    c = Componente(
        nombre="Con dato volatil",
        construir=ConDatoVolatil,
        operar=lambda x: x.operar(),
        observar=lambda x: x.items + x.solo_en_memoria,
        proyeccion=lambda x: x.items,
    )

    v = verificar(c, str(tmp_path / "v.jsonl"))

    assert v.clasificacion == VIOLA, f"un dato que solo vive en memoria debe detectarse: {v}"
    assert "comportamiento indistinguible" in v.fallidas, f"detecto otra cosa: {v.fallidas}"
