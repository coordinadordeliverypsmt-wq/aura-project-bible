"""Medición del razonador local — script que se ejecuta DENTRO del laboratorio.

Este fichero NO es producto: es instrumentación. Vive en `milestones/` y se copia al laboratorio
para ejecutarse allí. No modifica `aura_skeleton/` ni se importa desde él.

POR QUÉ SE EJECUTA DENTRO DEL LABORATORIO Y NO DESDE EL WORKTREE. `EjecutorProgramador` y
`EjecutorAuditor` **no reciben su raíz de `Configuracion`**: la calculan como
`Path(__file__).resolve().parents[1]`, es decir, el `walking-skeleton/` del paquete que se importe.
`raices_permitidas` no los gobierna. Si este arnés se lanzara importando `aura_skeleton` desde el
worktree real, los ejecutores operarían sobre el worktree real y el aislamiento por `git archive`
sería decorativo — y la comparación SHA-256 del laboratorio saldría idéntica precisamente porque nada
lo estaría tocando. Un falso PASS de seguridad.

Por eso el intérprete se sitúa dentro de la copia y las aserciones de §1 son BLOQUEANTES.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
import time

AQUI = pathlib.Path(__file__).resolve().parent  # <lab>/walking-skeleton


# ----------------------------------------------------------------- PROMPT CONGELADO --
#
# Fijado ANTES de la primera ejecución (DP §4.6). Si cambia, la tanda se anula y se repite desde
# cero. No se ajusta para mejorar el resultado: eso convertiría la medición en ingeniería de prompts.
#
# BRAZO A: contiene EXCLUSIVAMENTE lo que la tarea derivada transporta hoy. Ni una palabra más.

PROMPT_A = (
    "Una garantia declarada del proyecto ha dejado de aplicar y hay que corregir su declaracion. "
    "Este es TODO el contexto disponible:\n"
    "- motivo: {motivo}\n"
    "- fichero que hay que corregir: {fichero}\n"
    "- patron declarado que ya no aparece: {patron}\n"
    "- referencia de la garantia: {referencia}\n"
    "Corrige la declaracion sustituyendo en ese fichero el patron que ya no aparece por el patron "
    "correcto."
)


def _recursos() -> dict:
    """Muestra de recursos. En esta máquina el swap manda, así que se mide."""
    datos = {}
    try:
        for linea in pathlib.Path("/proc/meminfo").read_text().splitlines():
            clave, _, resto = linea.partition(":")
            if clave in ("MemFree", "MemAvailable", "SwapFree", "SwapTotal"):
                datos[clave] = int(resto.strip().split()[0]) // 1024  # MB
    except OSError:
        pass
    try:
        datos["load1"] = os.getloadavg()[0]
    except OSError:
        pass
    return datos


def _raices_efectivas(sistema) -> dict:
    """Raíz REAL sobre la que van a operar los ejecutores, leída de las instancias compuestas."""
    encontradas = {}
    pendientes = [sistema.registro_adaptadores]
    vistos = set()
    while pendientes:
        obj = pendientes.pop()
        if id(obj) in vistos:
            continue
        vistos.add(id(obj))
        nombre = getattr(obj, "name", None)
        raiz = getattr(obj, "_raiz", None)
        if nombre and raiz is not None:
            encontradas[nombre] = str(pathlib.Path(str(raiz)).resolve())
        if isinstance(obj, dict):
            pendientes.extend(obj.values())
        elif isinstance(obj, (list, tuple, set)):
            pendientes.extend(obj)
        elif hasattr(obj, "__dict__"):
            pendientes.extend(vars(obj).values())
    return encontradas


async def main() -> int:
    lab_raiz = AQUI.parent
    evidencia: dict = {
        "modelo": os.environ["AURA_LLM_MODEL"],
        "timeout_ollama_s": int(os.environ["AURA_OLLAMA_TIMEOUT_S"]),
        "timeout_wait_s": int(os.environ["AURA_WAIT_TIMEOUT_S"]),
        "prompt_congelado": PROMPT_A,
        "laboratorio": str(lab_raiz),
    }

    # ---------------------------------------------- 1 · AISLAMIENTO: aserciones BLOQUEANTES --
    import aura_skeleton
    from aura_skeleton import composicion as _comp

    paquete = pathlib.Path(aura_skeleton.__file__).resolve().parent
    raiz_ejecutores = pathlib.Path(_comp.__file__).resolve().parents[1]
    evidencia["paquete_importado"] = str(paquete)
    evidencia["raiz_que_usaran_los_ejecutores"] = str(raiz_ejecutores)

    if not paquete.is_relative_to(lab_raiz):
        evidencia["fallo_aislamiento"] = f"aura_skeleton importado FUERA del laboratorio: {paquete}"
        print(json.dumps(evidencia, ensure_ascii=False, indent=2))
        return 2
    if not raiz_ejecutores.is_relative_to(lab_raiz):
        evidencia["fallo_aislamiento"] = f"los ejecutores operarian FUERA del laboratorio: {raiz_ejecutores}"
        print(json.dumps(evidencia, ensure_ascii=False, indent=2))
        return 2

    # ------------------------------------------------- 2 · CONFIRMADOR QUE DENIEGA SIEMPRE --
    #
    # No es un atajo que salte el paso: es el `PermissionManager` real y la lista roja real
    # respondiendo «no». El motor simula ANTES de confirmar, así que aquí llega la previsualización
    # del dry-run real — y la ejecución no ocurre porque el permiso se deniega, estructuralmente.
    confirmaciones: list[dict] = []

    async def deniega_siempre(accion: str, args: dict, trace_id: str) -> bool:
        confirmaciones.append(
            {
                "accion": accion,
                "args": {k: v for k, v in args.items() if k != "_previsualizacion"},
                "previsualizacion": args.get("_previsualizacion"),
            }
        )
        return False

    # -------------------------------------- 3 · REGISTRO DE LA RESPUESTA CRUDA DEL MODELO --
    from aura_skeleton.modules.providers_real import OllamaProvider

    llamadas: list[dict] = []
    infer_original = OllamaProvider.infer

    async def infer_registrado(self, prompt: str) -> str:
        t0 = time.monotonic()
        try:
            salida = await infer_original(self, prompt)
            error = None
        except Exception as exc:  # noqa: BLE001 — se registra tal cual; es un dato de la medición
            salida, error = "", f"{type(exc).__name__}: {exc}"
        llamadas.append(
            {
                "prompt_enviado": prompt,
                "respuesta_cruda": salida,
                "error": error,
                "latencia_s": round(time.monotonic() - t0, 2),
            }
        )
        if error:
            raise RuntimeError(error)
        return salida

    OllamaProvider.infer = infer_registrado  # type: ignore[method-assign]

    # ------------------------------------------------------ 4 · CICLO REAL Y COMPOSICIÓN REAL --
    from aura_skeleton.composicion import Configuracion, componer
    from aura_skeleton.core.estado_operativo import Tarea

    cfg = Configuracion(
        datos=os.environ["AURA_DATOS"],
        raices_permitidas=(str(lab_raiz),),
        usar_stack_real=True,
    )
    sistema = componer(cfg, confirmador=deniega_siempre)

    raices = _raices_efectivas(sistema)
    evidencia["raices_efectivas_de_los_ejecutores"] = raices
    fuera = {n: r for n, r in raices.items() if not pathlib.Path(r).is_relative_to(lab_raiz)}
    if fuera:
        evidencia["fallo_aislamiento"] = f"ejecutores con raiz fuera del laboratorio: {fuera}"
        print(json.dumps(evidencia, ensure_ascii=False, indent=2))
        return 2

    # El ciclo REAL produce la tarea derivada. El contexto NO se escribe a mano: se toma de ahí.
    sistema.estado_operativo.registrar(
        Tarea(objetivo_id="obj-medicion", tarea_id="t-auditar", descripcion="auditar garantias", responsable="auditor")
    )
    await sistema.motor_ciclo.correr("obj-medicion", max_latidos=1)

    tareas = sistema.estado_operativo.tareas("obj-medicion")
    derivadas = [t for t in tareas if t.origen == "derivado"]
    evidencia["ciclo_real"] = {
        "latidos": 1,
        "tareas_totales": len(tareas),
        "causa_estado": next((t.estado for t in tareas if t.tarea_id == "t-auditar"), None),
        "causa_bloqueos": next((list(t.bloqueos) for t in tareas if t.tarea_id == "t-auditar"), []),
        "derivadas": len(derivadas),
    }
    if not derivadas:
        evidencia["fallo_protocolo"] = "el ciclo real no produjo tarea derivada: no hay contexto que medir"
        print(json.dumps(evidencia, ensure_ascii=False, indent=2))
        return 3

    args_derivada = dict(derivadas[0].args)
    evidencia["args_literales_de_la_derivada"] = args_derivada

    faltan = [c for c in ("motivo", "fichero_declarado", "buscar_declarado", "referencia") if c not in args_derivada]
    if faltan:
        evidencia["fallo_protocolo"] = f"la derivada no trae el contexto esperado, faltan: {faltan}"
        print(json.dumps(evidencia, ensure_ascii=False, indent=2))
        return 3

    # ------------------------------------------------- 5 · EL RAZONADOR, POR LA RUTA REAL --
    texto = PROMPT_A.format(
        motivo=args_derivada["motivo"],
        fichero=args_derivada["fichero_declarado"],
        patron=args_derivada["buscar_declarado"],
        referencia=args_derivada["referencia"],
    )
    evidencia["texto_entregado_al_razonador"] = texto
    evidencia["recursos_antes"] = _recursos()

    t0 = time.monotonic()
    try:
        await sistema.orquestador.handle_utterance("medicion", texto, "tr-humo")
        respuesta = await sistema.orquestador.wait("tr-humo", timeout=int(os.environ["AURA_WAIT_TIMEOUT_S"]))
        fallo = None
    except Exception as exc:  # noqa: BLE001 — un timeout o un OOM SON datos de la medición
        respuesta, fallo = None, f"{type(exc).__name__}: {exc}"
    evidencia["latencia_total_s"] = round(time.monotonic() - t0, 2)
    evidencia["recursos_despues"] = _recursos()
    evidencia["respuesta_del_producto"] = respuesta if respuesta is None else str(respuesta)
    evidencia["fallo_en_el_turno"] = fallo
    evidencia["llamadas_al_modelo"] = llamadas
    evidencia["confirmaciones_solicitadas"] = confirmaciones
    evidencia["se_denegaron_todas"] = True  # el confirmador no tiene otra rama

    print(json.dumps(evidencia, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
