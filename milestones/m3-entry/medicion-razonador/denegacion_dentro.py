"""Comprobación aislada de la denegación estructural — se ejecuta DENTRO del laboratorio.

Cierra el punto 6 que los dos ensayos de humo dejaron sin validar: el confirmador que deniega nunca
llegó a ejercitarse, porque el modelo jamás emitió una acción.

**No usa el LLM.** No hace falta: lo que se comprueba es el gobierno, y el gobierno no depende del
razonador. Se compone el sistema con el stack de mockups y se invoca el MOTOR REAL con una acción de
lista roja, para que la cadena `MotorAutomatizacion` → `PermissionManager` → confirmador sea la del
producto.

Demuestra dos cosas distintas:

  A · Una acción RED sin aprobación válida se DENIEGA, el confirmador recibe la previsualización del
      dry-run real, y el fichero no se toca.
  B · La aprobación diferida NO permite saltarse el gobierno: una aprobación registrada para OTRA
      huella no autoriza la acción original.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent  # <lab>/walking-skeleton

OBJETIVO = "laboratorio_denegacion.py"
CONTENIDO = "def cobrar(x):\n    if not autorizado(x):\n        raise PermisoDenegado\n    return x\n"
BUSCAR = "    if not autorizado(x):"
SUSTITUIR = "    if True:"


async def main() -> int:
    lab_raiz = AQUI.parent
    ev: dict = {"laboratorio": str(lab_raiz), "usa_llm": False}

    # ------------------------------------------------ AISLAMIENTO: aserciones BLOQUEANTES --
    import aura_skeleton
    from aura_skeleton import composicion as _comp

    paquete = pathlib.Path(aura_skeleton.__file__).resolve().parent
    raiz_ejecutores = pathlib.Path(_comp.__file__).resolve().parents[1]
    ev["paquete_importado"] = str(paquete)
    ev["raiz_que_usaran_los_ejecutores"] = str(raiz_ejecutores)
    if not paquete.is_relative_to(lab_raiz) or not raiz_ejecutores.is_relative_to(lab_raiz):
        ev["fallo_aislamiento"] = "el paquete o los ejecutores estan FUERA del laboratorio"
        print(json.dumps(ev, ensure_ascii=False, indent=2))
        return 2

    from aura_skeleton.composicion import Configuracion, componer

    objetivo = AQUI / OBJETIVO
    objetivo.write_text(CONTENIDO, encoding="utf-8")
    antes = objetivo.read_bytes()

    args_rojos = {"fichero": OBJETIVO, "buscar": BUSCAR, "sustituir": SUSTITUIR}

    # =================================================================== A · SIN APROBACION --
    vistas: list[dict] = []

    async def deniega(accion: str, args: dict, trace_id: str) -> bool:
        vistas.append({"accion": accion, "previsualizacion": args.get("_previsualizacion")})
        return False

    cfg = Configuracion(datos=os.environ["AURA_DATOS"], raices_permitidas=(str(lab_raiz),), usar_stack_real=False)
    sistema = componer(cfg, confirmador=deniega)

    ev["capacidad_es_lista_roja"] = "proponer_cambio" in __import__(
        "aura_skeleton.core.permissions", fromlist=["RED"]
    ).RED

    res_a = await sistema.motor.ejecutar("proponer_cambio", dict(args_rojos), "tr-den-a", "ev-a", origen="medicion")
    ev["A_sin_aprobacion"] = {
        "resultado": res_a,
        "confirmador_fue_llamado": len(vistas) == 1,
        "previsualizacion_recibida": vistas[0]["previsualizacion"] if vistas else None,
        "fichero_intacto": objetivo.read_bytes() == antes,
    }

    # ============================================ B · APROBACION DIFERIDA PARA OTRA HUELLA --
    #
    # El CEO aprueba UNA cosa concreta. Si una aprobacion registrada para otros argumentos sirviera
    # para esta accion, la aprobacion diferida seria un agujero de gobierno, no un mecanismo.
    from aura_skeleton.adapters.hitl_diferido import crear_confirmador_diferido
    from aura_skeleton.core.decisiones import AlmacenDecisiones, huella_de

    dir_dec = pathlib.Path(os.environ["AURA_DATOS"]) / "decisiones-medicion"
    almacen = AlmacenDecisiones(str(dir_dec))

    # Se aprueba explicitamente OTRA accion: mismos fichero y patron, sustituto distinto.
    args_otros = {**args_rojos, "sustituir": "    if False:"}
    almacen.aprobar(huella_de("proponer_cambio", args_otros, "previsualizacion cualquiera"))
    ev["B_aprobacion_registrada_para"] = args_otros

    sistema_b = componer(
        Configuracion(datos=os.environ["AURA_DATOS"], raices_permitidas=(str(lab_raiz),), usar_stack_real=False),
        confirmador=crear_confirmador_diferido(str(dir_dec)),
    )
    res_b = await sistema_b.motor.ejecutar("proponer_cambio", dict(args_rojos), "tr-den-b", "ev-b", origen="medicion")
    ev["B_aprobacion_ajena"] = {
        "resultado": res_b,
        "fichero_intacto": objetivo.read_bytes() == antes,
    }

    # ------------------------------------------------------------------------ VEREDICTO --
    a_ok = (
        res_a.get("estado") != "ejecutada"
        and ev["A_sin_aprobacion"]["confirmador_fue_llamado"]
        and bool(ev["A_sin_aprobacion"]["previsualizacion_recibida"])
        and ev["A_sin_aprobacion"]["fichero_intacto"]
    )
    b_ok = res_b.get("estado") != "ejecutada" and ev["B_aprobacion_ajena"]["fichero_intacto"]
    ev["veredicto"] = {"A_denegada_con_previsualizacion": a_ok, "B_no_se_puede_saltar_el_gobierno": b_ok}

    objetivo.unlink()  # el fichero sembrado no debe alterar la huella del laboratorio
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    return 0 if (a_ok and b_ok) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
