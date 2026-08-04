"""Ejecutor Programador: propone cambios VERIFICABLES, no escribe ficheros.

LA DISTINCION QUE PIDIO EL CEO (2026-08-03). Un agente que "escribe archivos" deja el repositorio en
manos de quien acierte; este propone un cambio y **solo lo conserva si la verificacion lo respalda**.
Si las pruebas fallan, el fichero vuelve byte a byte a su estado anterior. El resultado nunca es "he
escrito": es "he cambiado esto y esto es lo que la verificacion dice al respecto".

REUTILIZA EL PATRON YA PROBADO DE `herramientas/mutar.py`, que resolvio lo dificil hace incrementos:
guardar el original en bytes, exigir que el patron sea UNICO -si aparece N veces se rechaza en vez de
adivinar cual era la buena-, rechazar cambios degenerados y restaurar pase lo que pase (try/finally).
Aqui la condicion se invierte: mutar restaura SIEMPRE; el Programador restaura SOLO SI FALLA.

RUTA GOBERNADA, SIN EXCEPCIONES. La capacidad se despacha por el Motor Unico como cualquier otra, con
permisos, kill switch y auditoria. Queda en LISTA ROJA: altera el arbol de trabajo, y el criterio del
proyecto es "ante la duda, roja" (ADR-0003). Que el cambio sea reversible reduce el daño, no la
necesidad de consentimiento.

LIMITES DELIBERADOS DE ESTA PRIMERA VERSION. Un solo fichero, un solo reemplazo literal, patron unico.
No genera codigo: aplica un cambio que alguien -hoy un humano, mañana un modelo local- ya formulo. La
capacidad que se gana no es "escribir", es **cambiar con red**.
"""

from __future__ import annotations

from pathlib import Path

from .. import observability as obs


class EjecutorProgramador:
    """Adaptador de dominio: aplica un cambio y lo somete a verificacion antes de conservarlo."""

    name = "programador"
    capabilities = ["proponer_cambio"]

    def __init__(self, raiz: str, verificador, capacidad_verificacion: str = "ejecutar_pruebas") -> None:
        # La raiz se fija al construir, NO llega por `args`: nadie puede redirigir el cambio a otro arbol.
        self._raiz = Path(raiz)
        self._verificador = verificador
        self._capacidad = capacidad_verificacion

    async def execute(self, command: str, args: dict, trace_id: str, event_id: str) -> dict:
        if command != "proponer_cambio":
            raise ValueError(f"capacidad no ofrecida por el ejecutor Programador: {command!r}")

        relativa = str(args.get("fichero", ""))
        buscar = str(args.get("buscar", ""))
        sustituir = str(args.get("sustituir", ""))

        rechazo = self._rechazo_previo(relativa, buscar, sustituir)
        if rechazo:
            return {"capacidad": command, "aplicado": False, "verificado": False, "motivo": rechazo}

        ruta = (self._raiz / relativa).resolve()
        if not str(ruta).startswith(str(self._raiz.resolve())):
            # Contencion de ruta: un cambio no puede escapar del arbol de trabajo declarado.
            return {"capacidad": command, "aplicado": False, "verificado": False, "motivo": "ruta fuera del arbol"}

        original = ruta.read_bytes()
        contenido = original.decode("utf-8")
        apariciones = contenido.count(buscar)
        if apariciones != 1:
            # Misma regla que el arnes de mutacion: con el patron repetido se cambiaria la PRIMERA
            # aparicion, que puede ser un comentario. Se rechaza en vez de adivinar.
            motivo = "el patron no aparece" if apariciones == 0 else f"el patron aparece {apariciones} veces: amplialo"
            return {"capacidad": command, "aplicado": False, "verificado": False, "motivo": motivo}

        ruta.write_bytes(contenido.replace(buscar, sustituir, 1).encode("utf-8"))
        try:
            veredicto = await self._verificador.execute(self._capacidad, {}, trace_id, event_id)
        except Exception:
            ruta.write_bytes(original)  # ante cualquier fallo del verificador, el arbol vuelve atras
            raise

        if veredicto.get("ok"):
            obs.log("PROG", "ejecutor-programador", f"cambio CONSERVADO en {relativa}", trace_id, audit=True)
            return {
                "capacidad": command,
                "aplicado": True,
                "verificado": True,
                "fichero": relativa,
                "motivo": veredicto.get("resumen", ""),
            }

        # La verificacion no respalda el cambio: se revierte byte a byte y se declara el motivo.
        ruta.write_bytes(original)
        obs.log(
            "PROG",
            "ejecutor-programador",
            f"cambio REVERTIDO en {relativa}: verificacion en rojo",
            trace_id,
            audit=True,
        )
        return {
            "capacidad": command,
            "aplicado": False,
            "verificado": False,
            "fichero": relativa,
            "motivo": f"revertido: {veredicto.get('resumen', 'la verificacion no paso')}",
        }

    def _rechazo_previo(self, relativa: str, buscar: str, sustituir: str) -> str:
        if not relativa or not buscar:
            return "un cambio necesita fichero y patron a sustituir"
        if buscar == sustituir:
            return "el cambio es degenerado: no cambia nada"
        if not (self._raiz / relativa).is_file():
            return f"el fichero no existe: {relativa}"
        return ""
