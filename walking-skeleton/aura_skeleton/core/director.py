"""Director General: el primer coordinador operativo del Sistema Operativo Interno de AURORA.

QUE ES. Un coordinador SIN logica de negocio propia. Los siete pasos de su ciclo ya existian en el
repositorio y aqui solo se encadenan (validado por evidencia, CEO 2026-08-03):

  1. obtener el estado ......... EstadoOperativo._cargar        (reanuda tras reiniciar)
  2. seleccionar la tarea ...... EstadoOperativo.reanudar        (determinista)
  3. resolver el ejecutor ...... RegistroEjecutores.para         (patron de RegistroAdaptadores)
  4. ejecutar .................. MotorAutomatizacion.ejecutar    (permisos, dry-run, kill switch)
  5. validar el resultado ...... contrato {ejecutada|detenida|error} del motor
  6. persistir el estado ....... EstadoOperativo.actualizar      (append-only)
  7. decidir la siguiente ...... EstadoOperativo.reanudar

QUE NO HACE. No ejecuta nada por su cuenta: **todo despacho pasa por el Motor Unico**, con sus
permisos, su dry-run y su kill switch (ALERTA-005, RN-5). Un coordinador que ejecutara directamente
seria una segunda ruta de ejecucion, que es exactamente el defecto que ALERTA-005 y ALERTA-006 costaron.

QUIEN MANDA. Es el UNICO coordinador. Los agentes especializados son **solo ejecutores**: no crean
trabajo ni tocan el estado global. Por eso el estado se actualiza aqui y no en el ejecutor.
"""

from __future__ import annotations

from .estado_operativo import CLAVE_CONTEXTO, AlmacenEstadoOperativo, Tarea, contexto_de_correccion


class ResponsableDuplicado(Exception):
    """Dos ejecutores declaran el mismo responsable (ambiguedad no resoluble)."""


class RegistroEjecutores:
    """Resuelve QUE ACCION del catalogo atiende a cada responsable.

    Copia deliberada de las dos reglas de `RegistroAdaptadores`, que las gano con ALERTA-005:
    **un responsable, un dueno** (la ambiguedad se rechaza al registrar, no se resuelve por orden de
    insercion en tiempo de ejecucion) y **sin dueno no hay ejecucion, y el hecho se declara**
    (`para()` devuelve None y quien llama produce un fallo explicito, nunca un exito silencioso).
    """

    def __init__(self, ejecutores: dict[str, str] | None = None) -> None:
        self._por_responsable: dict[str, str] = {}
        for responsable, accion in (ejecutores or {}).items():
            self.registrar(responsable, accion)

    def registrar(self, responsable: str, accion: str) -> None:
        if responsable in self._por_responsable:
            raise ResponsableDuplicado(f"'{responsable}' ya tiene ejecutor: {self._por_responsable[responsable]}")
        self._por_responsable[responsable] = accion

    def para(self, responsable: str) -> str | None:
        return self._por_responsable.get(responsable)


class DirectorGeneral:
    """Coordina UNA vuelta del ciclo. El bucle continuo es el incremento siguiente."""

    def __init__(self, estado: AlmacenEstadoOperativo, motor, ejecutores: RegistroEjecutores) -> None:
        self.estado = estado
        self.motor = motor
        self.ejecutores = ejecutores

    async def ciclo(self, objetivo_id: str, trace_id: str = "-") -> Tarea | None:
        """Toma la siguiente tarea del backlog, la despacha, valida y persiste. None si no hay trabajo.

        Devuelve la tarea YA ACTUALIZADA, para que quien llame vea el resultado real y no lo que se
        pretendia hacer (INV-9: no se narra exito sin efecto).
        """
        tarea = self.estado.reanudar(objetivo_id)
        if tarea is None:
            return None

        accion = self.ejecutores.para(tarea.responsable)
        if accion is None:
            # Sin dueno no hay ejecucion Y EL HECHO SE DECLARA: la tarea se bloquea con el motivo,
            # no se descarta ni se reintenta en bucle. Es la leccion de ALERTA-005.
            return self.estado.transitar(
                objetivo_id,
                tarea.tarea_id,
                "bloqueada",
                autoridad="director",
                causa=f"ningun ejecutor atiende al responsable '{tarea.responsable}'",
                bloqueos=[*tarea.bloqueos, f"ningun ejecutor atiende al responsable '{tarea.responsable}'"],
            )

        res = await self.motor.ejecutar(
            accion, dict(tarea.args), trace_id, f"{trace_id}:{tarea.tarea_id}", origen=f"director:{tarea.responsable}"
        )

        # VALIDACION EN DOS NIVELES. El motor dice si la accion PUDO ejecutarse; el ejecutor dice si
        # el resultado es BUENO. Antes solo se miraba el primero, asi que una verificacion en rojo
        # cerraba la tarea como "terminada" con evidencia "ejecutada" —literalmente cierta y
        # completamente engañosa—: AURORA podia auditar y no reaccionar a lo que descubria.
        veredicto = res.get("resultado")
        ok_ejecutor = veredicto.get("ok", True) if isinstance(veredicto, dict) else True
        if res.get("estado") == "ejecutada" and ok_ejecutor:
            siguiente = self._siguiente_distinta(objetivo_id, tarea.tarea_id)
            return self.estado.transitar(
                objetivo_id,
                tarea.tarea_id,
                "terminada",
                autoridad="director",
                causa=f"motor:{accion}:ejecutada",
                evidencias=[*tarea.evidencias, f"motor:{accion}:ejecutada"],
                proxima_accion=siguiente,
            )
        # Un resultado negativo del ejecutor se declara con SU motivo, no con el del motor: "ejecutada"
        # no explicaria por que la tarea no puede darse por hecha.
        motivo = (
            f"{res.get('estado')}: {res.get('motivo', 'sin motivo')}"
            if not (res.get("estado") == "ejecutada")
            else f"veredicto negativo: {(veredicto or {}).get('resumen', 'el ejecutor no lo respalda')}"
        )
        # EL VEREDICTO ESTRUCTURADO VIAJA CON LA TAREA (acta del CEO, 2026-08-15). El director es el
        # unico punto donde coexisten el resultado del ejecutor -con sus datos accionables- y la
        # tarea que se va a bloquear. Hasta aqui se conservaba solo `motivo`, una linea de prosa, y
        # la correccion derivada nacia sin nada que ejecutar.
        #
        # Va en `args` bajo una clave declarada, NO en `evidencias`: el contexto es dato de maquina y
        # la evidencia es texto para una persona -y ademas de la evidencia se deriva el identificador
        # de la tarea, asi que meterlo ahi romperia la deduplicacion-.
        contexto = contexto_de_correccion(veredicto if isinstance(veredicto, dict) else {}, motivo)
        return self.estado.transitar(
            objetivo_id,
            tarea.tarea_id,
            "bloqueada",
            autoridad="director",
            causa=motivo,
            bloqueos=[*tarea.bloqueos, motivo],
            args={**tarea.args, CLAVE_CONTEXTO: contexto},
        )

    def _siguiente_distinta(self, objetivo_id: str, actual: str) -> str:
        """Deja preparada la proxima accion ANTES de terminar, para que el proximo arranque no tenga
        que deducirla. Se excluye la tarea actual: aun figura abierta en la proyeccion en memoria."""
        pendientes = [t for t in self.estado.abiertas(objetivo_id) if t.tarea_id != actual]
        if not pendientes:
            return "sin tareas accionables"
        s = min(pendientes, key=lambda t: t.tarea_id)
        return f"{s.tarea_id}: {s.descripcion or s.proxima_accion or 'continuar'}"
