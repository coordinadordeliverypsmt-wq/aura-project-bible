"""Ciclo `instalar -> ejecutar -> retirar` de un agente externo — D-CP-1.

Implementa el **§4** de `CONTRATO-AGENTE-EXTERNO-BAJO-DEMANDA.md`, que hasta hoy estaba declarado
*«conceptual — no implementado, no ejecutado»*. **No amplía el contrato**: cada regla de aquí sale de
una cláusula suya, y las dos barreras duras se aplican ANTES de tocar la máquina.

**Qué NO es** (§7 del contrato): ni un Orchestrator, ni un scheduler, ni un router de proveedores, ni
una autorización automática. Invitar a un externo **sigue siendo una decisión del CEO**; esto solo
ejecuta correctamente la invitación cuando ya está decidida.

**Por qué el ejecutor de comandos se inyecta:** los tres caminos que de verdad importan —que falle la
instalación, que falle la ejecución y que **falle la retirada**— no se pueden provocar a voluntad
contra un instalador real. Inyectarlo permite probarlos de forma determinista sin renunciar al ciclo
real, que se ejerce aparte contra el sistema.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

#: Las cuatro razones que el §2 admite, con el vocabulario del propio contrato. No se amplían aquí:
#: cualquier otra cosa —incluido «el agente principal falló»— no basta para invitar a nadie.
RAZONES_VALIDAS = (
    "incapacidad tecnica",
    "segunda opinion",
    "auditoria",
    "recuperacion",
)

#: Tipos de carga que pueden salir de la máquina mientras `AURA_APPROVED` esté vacío (§3).
_SINTETICO = "fixture_sintetico"


class CicloBloqueado(Exception):
    """Una barrera del contrato detuvo el ciclo antes de tocar el sistema."""


@dataclass
class Ejecucion:
    """Una orden ejecutada, con su resultado. Es la unidad de evidencia del ciclo (§4)."""

    paso: str
    orden: tuple[str, ...]
    codigo: int
    salida: str = ""
    ok: bool = field(init=False)

    def __post_init__(self) -> None:
        self.ok = self.codigo == 0


def _normalizar(texto: str) -> str:
    return " ".join(str(texto).lower().replace("í", "i").replace("ó", "o").replace("á", "a").split())


def necesidad_determinada(estado: dict) -> tuple[bool, str]:
    """§2 · ¿procede invitar a un externo? **Fail-closed en los dos sentidos.**

    Exige `AGENTE_EXTERNO_REQUIRED` **y** que su motivo sea una de las cuatro razones que el contrato
    enumera. La comprobación es contra el vocabulario canónico de §2, no una interpretación libre:
    *«un fallo del agente principal NO es, por sí solo, motivo suficiente»*, porque —dice el
    contrato— *«casi siempre significa que hay que corregir el trabajo, no cambiar de trabajador»*.
    """
    necesidad = (estado or {}).get("AGENTE_EXTERNO_REQUIRED")
    if not isinstance(necesidad, dict):
        return False, ("no hay AGENTE_EXTERNO_REQUIRED declarado: invitar a un externo exige que la "
                       "necesidad este explicitamente determinada (contrato §2)")
    motivo = _normalizar(necesidad.get("motivo", ""))
    if not motivo:
        return False, "AGENTE_EXTERNO_REQUIRED sin motivo: determinado pero no justificado (§2)"
    if not any(r in motivo for r in RAZONES_VALIDAS):
        return False, ("el motivo no encaja en ninguna de las cuatro razones del §2; en particular, "
                       "un fallo del agente principal no es motivo suficiente por si solo")
    return True, necesidad.get("motivo", "")


def politica_de_datos_permite(carga: dict, aprobados: list) -> bool:
    """§3 · *«ningun externo recibe codigo confidencial de AURA»* mientras no haya `AURA_APPROVED`.

    Sin `tipo` declarado se rechaza: lo que no se sabe que es, no sale de la maquina.
    """
    tipo = (carga or {}).get("tipo")
    if tipo == _SINTETICO:
        return True
    if tipo == "codigo_de_aura":
        return bool(aprobados)
    return False


def _ejecutor_real(paso: str, orden: tuple[str, ...]) -> Ejecucion:
    """Ejecuta de verdad. Sin `shell=True`: la orden es una lista, nunca una cadena interpretada."""
    p = subprocess.run(list(orden), capture_output=True, text=True, timeout=900)
    return Ejecucion(paso=paso, orden=orden, codigo=p.returncode,
                     salida=(p.stdout + p.stderr)[-2000:])


#: Órdenes por agente. Se declaran aquí, explícitas: el ciclo NO construye comandos a partir de datos
#: de entrada, que es como se cuelan las inyecciones.
AGENTES = {
    # AÑADIDO 2026-08-25 · el CEO extendio el marco bajo demanda a Codex para D-CP-1.bis. Es una
    # entrada de DATOS en el registro de agentes: el ciclo no cambia.
    "codex": {
        "instalar": ("npm", "install", "-g", "@openai/codex"),
        "retirar": ("npm", "uninstall", "-g", "@openai/codex"),
        "comprobar": ("bash", "-lc", "command -v codex"),
        "limpiar": ("bash", "-lc", "rm -rf ~/.codex ~/.config/codex ~/.cache/codex"),
        "comprobar_residuos": ("bash", "-lc",
                               "ls -d ~/.codex ~/.config/codex ~/.cache/codex 2>/dev/null "
                               "| wc -l | grep -qv '^0$'"),
    },
    "opencode": {
        "instalar": ("npm", "install", "-g", "opencode-ai@1.18.22"),
        "retirar": ("npm", "uninstall", "-g", "opencode-ai"),
        "comprobar": ("bash", "-lc", "command -v opencode"),
        # §4 · `limpiar residuos`. Rutas DECLARADAS, nunca construidas a partir de datos de entrada:
        # un `rm -rf` cuyo destino venga de fuera es como se borra lo que no se queria borrar.
        "limpiar": ("bash", "-lc",
                    "rm -rf ~/.config/opencode ~/.cache/opencode ~/.local/share/opencode ~/.opencode"),
        "comprobar_residuos": ("bash", "-lc",
                               "ls -d ~/.config/opencode ~/.cache/opencode ~/.local/share/opencode "
                               "~/.opencode 2>/dev/null | wc -l | grep -qv '^0$'"),
    },
}


def esta_instalado(nombre: str, ejecutor=_ejecutor_real) -> bool:
    """Le pregunta AL SISTEMA. Fiarse de una variable propia haria invisible un residuo real."""
    return ejecutor("comprobar", AGENTES[nombre]["comprobar"]).ok


def ciclo(estado: dict, carga: dict, aprobados: list, ejecutor=_ejecutor_real,
          nombre: str = "opencode", orden_de_trabajo: tuple[str, ...] | None = None) -> dict:
    """El §4 completo: necesidad -> politica -> instalar -> ejecutar -> retirar -> **verificar**.

    Devuelve un registro con la evidencia de cada paso. **La ultima palabra no la tiene la orden de
    desinstalar, sino la comprobacion posterior**: que `npm uninstall` devuelva 0 no demuestra que el
    agente se haya ido, y declarar COMPLETED sin comprobarlo seria fabricar trazabilidad.
    """
    procede, motivo = necesidad_determinada(estado)
    if not procede:
        raise CicloBloqueado(motivo)
    if not politica_de_datos_permite(carga, aprobados):
        raise CicloBloqueado(
            f"politica de datos (§3): una carga de tipo {carga.get('tipo')!r} no puede enviarse a un "
            f"externo mientras AURA_APPROVED este vacio")

    ordenes = AGENTES[nombre]
    registro: dict = {"agente": nombre, "motivo": motivo, "evidencia": [], "retirado": False,
                      "residuo": True, "fallo": None}

    instalacion = ejecutor("instalar", ordenes["instalar"])
    registro["evidencia"].append(instalacion)
    if not instalacion.ok:
        # Fail-closed: si no se pudo instalar, no hay nada que ejecutar ni que retirar.
        registro["fallo"] = "instalacion"
        registro["residuo"] = False
        return registro

    trabajo = ejecutor("ejecutar", orden_de_trabajo or (nombre, "run", carga.get("tarea", "")))
    registro["evidencia"].append(trabajo)
    if not trabajo.ok:
        # Un fallo del trabajo NO justifica dejarlo instalado: se retira igual.
        registro["fallo"] = "ejecucion"

    retirada = ejecutor("retirar", ordenes["retirar"])
    registro["evidencia"].append(retirada)

    # §4 · desinstalar Y limpiar. AÑADIDO 2026-08-25: el primer ciclo real dejo tres directorios en
    # HOME con el ejecutable ya ausente. `npm uninstall` retira el paquete, no el rastro.
    limpieza = ejecutor("limpiar", ordenes["limpiar"])
    registro["evidencia"].append(limpieza)

    comprobacion = ejecutor("comprobar", ordenes["comprobar"])
    registro["evidencia"].append(comprobacion)
    residuos = ejecutor("comprobar_residuos", ordenes["comprobar_residuos"])
    registro["evidencia"].append(residuos)

    # Residuo es CUALQUIERA de las dos cosas: que el ejecutable siga respondiendo, o que queden
    # directorios. Mirar solo lo primero es lo que habria declarado COMPLETED con rastro en disco.
    registro["residuo"] = comprobacion.ok or residuos.ok
    registro["retirado"] = not comprobacion.ok
    return registro


def resultado_del_ciclo(registro: dict) -> str:
    """`COMPLETED` solo si el agente **ya no esta**. Cualquier otra cosa se nombra por su fallo."""
    if registro.get("fallo") == "instalacion":
        return "FALLO_INSTALACION"
    if registro.get("residuo"):
        return "RESIDUO"
    if registro.get("fallo") == "ejecucion":
        return "FALLO_EJECUCION"
    return "COMPLETED"
