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


def _almacen_con_motor(ruta):
    """F4 tramo 2 (2026-08-25): `AlmacenReglas` ya no escribe sin motor. El componente se construye
    como en produccion; **el principio que esta prueba verifica no cambia**."""
    import asyncio  # noqa: F401  (lo usa `operar`)

    from aura_skeleton.core.automatizacion import MotorAutomatizacion
    from aura_skeleton.core.ejecutor_reglas import EjecutorReglas
    from aura_skeleton.core.permissions import PermissionManager
    from aura_skeleton.core.registro import RegistroAdaptadores

    async def _si(accion, args, trace_id):
        return True

    registro = RegistroAdaptadores()
    almacen = AlmacenReglas(ruta, motor=MotorAutomatizacion(registro, PermissionManager(_si)))
    registro.registrar(EjecutorReglas(almacen))
    return almacen


def _automatizaciones():
    import asyncio

    def operar(a):
        # el verificador es sincrono y `crear` paso a ser corrutina: se ejecuta aqui, en el test.
        asyncio.run(_crear(a))

    async def _crear(a):
        await a.crear(
            ReglaUsuario(
                rule_id="r1", user_id="u", evento="action.command", condicion={}, accion="copiar_archivo", args={}
            )
        )

    return Componente(
        nombre="Automatizaciones",
        construir=_almacen_con_motor,
        operar=operar,
        observar=lambda a: [(r.rule_id, r.estado) for r in a._reglas],
        proyeccion=lambda a: a._reglas,
        # CORREGIDO 2026-08-25. `desactivar` paso a corrutina en F4 y este callback la
        # invocaba SIN esperarla: la retirada nunca ocurria y Python lo denunciaba con
        # `RuntimeWarning: coroutine ... was never awaited`. El verificador es sincrono, asi
        # que la corrutina se ejecuta aqui, igual que ya se hacia en `operar`.
        retirar=lambda a: asyncio.run(a.desactivar("u", "r1")),
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


def test_LA_MEMORIA_YA_CUMPLE_EL_PRINCIPIO(tmp_path):
    """**PREMISA SUPERADA, garantia sustituida** — 2026-08-25, G-7.

    La version anterior se llamaba `test_LA_MEMORIA_VIOLA_EL_PRINCIPIO_Y_EL_PROTOCOLO_LO_DETECTA` y
    empezaba diciendo *«no se arregla; se verifica que la garantia sepa verlo»*. Se arreglo: era lo
    que `DP-D-M-8 §5.2` ordenaba —*«la memoria debe adoptar el patron que las reglas ya usan»*—.
    `olvidar` y `marcar` **anexan** en vez de reescribir, y `_load` proyecta quedandose con la ultima
    linea por clave. La direccion ya no esta invertida: el historial es la fuente y la proyeccion su
    lectura.

    **Que el protocolo sepa detectar un incumplimiento sigue cubierto**, y por casos que no caducan:
    `test_un_componente_que_no_persiste_nada_viola_el_principio` y
    `test_se_detecta_un_componente_que_NO_reconstruye_igual`, ambos con componentes sinteticos. Lo
    que se retira es usar la memoria REAL como ejemplo de defecto, porque ya no lo es.
    """
    v = verificar(_memoria(), str(tmp_path / "m.jsonl"))

    assert v.clasificacion == CUMPLE, f"la memoria deberia cumplir tras G-7: {v.fallidas} — {v.detalle}"


def test_el_protocolo_es_reutilizable_sin_conocer_el_componente(tmp_path):
    """No hay ramas por tipo: el verificador solo usa las cuatro funciones de la descripcion."""
    veredictos = [
        verificar(_estado_operativo(), str(tmp_path / "a.jsonl")),
        verificar(_automatizaciones(), str(tmp_path / "b.jsonl")),
        verificar(_memoria(), str(tmp_path / "c.jsonl")),
    ]
    # ACTUALIZADO 2026-08-25 (G-7): la memoria dejo de ser el ejemplo de incumplimiento. Lo que esta
    # prueba mide —que el verificador no tiene ramas por tipo de componente— NO cambia.
    assert [v.clasificacion for v in veredictos] == [CUMPLE, CUMPLE, CUMPLE]
    txt = informe(veredictos)
    assert "Memoria" in txt and "cumple" in txt


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
