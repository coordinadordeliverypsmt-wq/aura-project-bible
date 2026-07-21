#!/usr/bin/env python3
"""Demostracion de CAPACIDAD (M2): manos digitales, evaluable como producto.

Capacidad: AURA ACTUA sobre el computador cuando se lo piden hablando, PREVISUALIZA antes de
alterar nada, EXIGE confirmacion informada para lo destructivo, AUTOMATIZA por reglas sin humano
delante, CONSOLIDA notificaciones y puede DETENERSE por completo.

Lo que esta demo existe para demostrar (DoD 9 del Architecture Review M2 Entry):
que la capacidad es ALCANZABLE HABLANDO, no que las clases existan. ALERTA-005 se produjo
precisamente porque las tres piezas de M2 estaban construidas, probadas y desconectadas.

Backends por bandera:
  (por defecto)  mocks    -> reproducible en cualquier entorno
  --real         Ollama   -> demo sobre stack real (D24). ~160 s por turno conversacional en el
                            hardware actual: la demo mide CAPACIDAD, no latencia (HC-1 sigue abierto).
"""

import argparse
import asyncio
import json
import os
import tempfile
import uuid

from aura_skeleton.adapters.computador import AdaptadorComputador
from aura_skeleton.adapters.home_assistant import HomeAssistantMock
from aura_skeleton.adapters.voice import VoiceAdapterMock
from aura_skeleton.bus import InProcessEventBus
from aura_skeleton.contracts import Event
from aura_skeleton.core.automatizacion import MotorAutomatizacion, Regla
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.notificaciones import CentroNotificaciones, FuenteNoPermitida, Notificacion
from aura_skeleton.core.orchestrator import Orchestrator
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores
from aura_skeleton.modules.memory import PersistentMemory

USER = "mauricio"


class _ProveedorGuiado:
    """Doble de LLM para el modo sin --real: emite la accion prevista para cada peticion."""

    name = "mock"

    def __init__(self, guion):
        self._guion = guion

    async def infer(self, prompt):
        # Solo el turno ACTUAL: el prompt arrastra la conversacion reciente y buscar en todo el
        # texto hacia que el doble respondiera al turno anterior.
        turno = prompt.rsplit("Usuario:", 1)[-1]
        for clave, (accion, args, say) in self._guion.items():
            if clave in turno:
                return json.dumps({"intent": "x", "action": accion, "args": args, "say": say})
        return json.dumps({"intent": "x", "action": "recordatorio", "args": {}, "say": "Entendido."})


def _huella(raiz):
    """Estado completo del arbol: nombre, tamano y mtime. Detecta cualquier efecto real."""
    fotos = {}
    for base, _, ficheros in os.walk(raiz):
        for f in ficheros:
            p = os.path.join(base, f)
            st = os.stat(p)
            fotos[p] = (st.st_size, st.st_mtime_ns)
    return fotos


async def _say(orch, text):
    tid = uuid.uuid4().hex[:12]
    print(f'\n  Usuario: "{text}"')
    await orch.handle_utterance(USER, text, tid)
    res = await orch.wait(tid, timeout=600)
    print(f"  AURA:    {res['say']}")
    return res


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true")
    args_cli = ap.parse_args()

    work = tempfile.mkdtemp(prefix="aura_m2_")
    docs = os.path.join(work, "documentos")
    os.makedirs(docs)
    for nombre, texto in (
        ("factura-marzo.txt", "importe 120"),
        ("factura-abril.txt", "importe 95"),
        ("borrador-viejo.txt", "texto obsoleto que ya no sirve"),
    ):
        with open(os.path.join(docs, nombre), "w") as f:
            f.write(texto)

    caps = {}
    confirmaciones = []  # lo que AURA mostro al pedir permiso

    async def confirmar(accion, argumentos, tid):
        """HITL de la demo: acepta, pero deja constancia de si vio la previsualizacion."""
        prev = argumentos.get("_previsualizacion")
        print(f"      (HITL) AURA pide confirmar '{accion}'")
        print(f"             previsualizacion: {prev}")
        confirmaciones.append((accion, prev))
        return prev is not None  # sin previsualizacion, el usuario NO confirma

    print("=" * 70)
    print("DEMO DE CAPACIDAD M2 — Manos digitales de AURA")
    print("=" * 70)
    print(f"Entorno de trabajo: {docs}")

    ks = KillSwitch(os.path.join(work, "KILL"))
    computador = AdaptadorComputador(raices=(work,))
    registro = RegistroAdaptadores([computador, HomeAssistantMock()])
    permisos = PermissionManager(confirmar, kill_switch=ks)
    motor = MotorAutomatizacion(registro, permisos)

    if args_cli.real:
        from aura_skeleton.modules.providers_real import OllamaProvider
        from aura_skeleton.modules.router import ModelRouter

        proveedor = OllamaProvider("ollama", os.environ.get("AURA_LLM_MODEL", "qwen2.5:3b"))
    else:
        from aura_skeleton.modules.router import ModelRouter

        proveedor = _ProveedorGuiado(
            {
                "factura": ("buscar_archivo", {"patron": "factura-*.txt", "raiz": docs}, "Busco tus facturas."),
                "borrador-viejo": (
                    "borrar_archivo",
                    {"ruta": os.path.join(docs, "borrador-viejo.txt")},
                    "Elimino el borrador.",
                ),
                "recuerdame": ("recordatorio", {"texto": "comprar pan"}, "Te lo recuerdo."),
            }
        )

    orch = Orchestrator(
        InProcessEventBus(),
        PersistentMemory(os.path.join(work, "memoria.json")),
        ModelRouter([proveedor], 1200),
        permisos,
        VoiceAdapterMock(),
        registro,
        motor=motor,
    )

    # --- 1. Accion de lectura pedida hablando (lo que ALERTA-005 impedia) ----
    print("\n" + "-" * 70)
    print("1. Manos digitales: una peticion hablada llega al computador")
    print("-" * 70)
    r = await _say(orch, f"Busca mis archivos de factura en {docs}")
    caps["lectura_alcanzable"] = "ejecutada" in r["say"]

    # --- 2. Accion destructiva: previsualizacion antes de confirmar ---------
    print("\n" + "-" * 70)
    print("2. Accion destructiva: confirmacion INFORMADA (dry-run previo)")
    print("-" * 70)
    objetivo = os.path.join(docs, "borrador-viejo.txt")
    r = await _say(orch, f"Borra el archivo {objetivo}")
    destructivas = [c for c in confirmaciones if c[0] == "borrar_archivo"]
    caps["destructiva_confirmada_con_previsualizacion"] = bool(destructivas) and destructivas[0][1] is not None
    caps["destructiva_ejecutada_tras_confirmar"] = not os.path.exists(objetivo)
    print(f"      efecto real: el archivo {'YA NO existe' if not os.path.exists(objetivo) else 'sigue ahi'}")

    # --- 3. Exito sin evidencia: prohibido -----------------------------------
    print("\n" + "-" * 70)
    print("3. Accion sin adaptador capaz: error explicito, nunca exito falso")
    print("-" * 70)
    r = await _say(orch, "Recuerdame comprar pan manana")
    caps["sin_adaptador_error_explicito"] = "No pude ejecutar" in r["say"] or "consulta" in r["say"].lower()

    # --- 4. Automatizacion con dry-run, sin humano delante -------------------
    print("\n" + "-" * 70)
    print("4. Automatizacion: una regla dispara por evento, con dry-run obligatorio")
    print("-" * 70)
    motor.agregar(
        Regla(
            "archivar-facturas",
            "sensor.disco",
            "mover_archivo",
            {"origen": os.path.join(docs, "factura-marzo.txt"), "destino": os.path.join(work, "factura-marzo.txt")},
        )
    )
    ev = Event("sensor.disco.lleno", "auto-1", USER, {})
    await motor.on_event(ev)
    ultimo = motor.ejecutadas[-1]
    print(f"      regla '{ultimo['regla']}' -> {ultimo['estado']}")
    caps["automatizacion_con_dry_run"] = ultimo["estado"] == "ejecutada" and ultimo.get("plan") is not None

    # --- 5. Kill switch alcanza AMBAS vias ------------------------------------
    print("\n" + "-" * 70)
    print("5. Kill switch: detiene conversacion Y automatizaciones")
    print("-" * 70)
    ks.engage("demostracion")
    huella_ks = _huella(work)
    await motor.on_event(Event("sensor.disco.lleno", "auto-2", USER, {}))
    detenida_auto = motor.ejecutadas[-1]["estado"] in ("detenida", "error")
    res_conv = await motor.ejecutar(
        "borrar_archivo", {"ruta": os.path.join(docs, "factura-abril.txt")}, "k", "k1", "conversacion"
    )
    detenida_conv = res_conv["estado"] == "detenida"
    print(f"      via automatizacion: {motor.ejecutadas[-1]['estado']}")
    print(f"      via conversacion:   {res_conv['estado']} ({res_conv.get('motivo')})")
    caps["kill_switch_ambas_vias"] = detenida_auto and detenida_conv and _huella(work) == huella_ks
    ks.disengage()

    # --- 6. Centro de notificaciones ------------------------------------------
    print("\n" + "-" * 70)
    print("6. Centro de notificaciones: consolida, prioriza y no ejecuta por su cuenta")
    print("-" * 70)
    centro = CentroNotificaciones(adaptador=computador, permisos=permisos, motor=motor)
    centro.recibir(Notificacion("computador", "Disco casi lleno", "quedan 2 GB", "critica"))
    centro.recibir(Notificacion("computador", "Disco casi lleno", "quedan 2 GB", "critica"))  # duplicada
    centro.recibir(Notificacion("home_assistant", "Puerta abierta", "entrada", "alta"))
    centro.recibir(
        Notificacion("aura", "Resumen listo", "informe de Ana sobre su salud", "baja", contiene_terceros=True)
    )
    listado = centro.listar()
    print(f"      recibidas: {len(listado)} (suprimidas por duplicado: {centro.suprimidas})")
    print(f"      orden por prioridad: {[n.titulo for n in listado]}")
    caps["notificaciones_dedup_y_prioridad"] = (
        len(listado) == 3 and centro.suprimidas == 1 and listado[0].prioridad == "critica"
    )

    try:
        centro.recibir(Notificacion("android", "fuera del MVP", "x"))
        caps["frontera_fuentes"] = False
    except FuenteNoPermitida:
        print("      fuente 'android' RECHAZADA (fuera del MVP hasta R2)")
        caps["frontera_fuentes"] = True

    purgadas = centro.cerrar_sesion()
    con_terceros = [n for n in centro.listar() if n.contiene_terceros]
    print(f"      al cerrar sesion: {purgadas} notificacion(es) de terceros purgadas")
    print(f"      se conserva el hecho, no el contenido: cuerpo={con_terceros[0].cuerpo!r}")
    caps["privacidad_terceros"] = purgadas == 1 and con_terceros[0].cuerpo == ""

    # --- Resultado -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CAPACIDADES DEMOSTRADAS")
    print("=" * 70)
    etiquetas = {
        "lectura_alcanzable": "Actua sobre el computador cuando se lo piden hablando",
        "destructiva_confirmada_con_previsualizacion": "Previsualiza ANTES de pedir confirmacion",
        "destructiva_ejecutada_tras_confirmar": "Ejecuta lo destructivo solo tras confirmar",
        "sin_adaptador_error_explicito": "Nunca reporta exito sin evidencia de ejecucion",
        "automatizacion_con_dry_run": "Automatiza por reglas con dry-run obligatorio",
        "kill_switch_ambas_vias": "El kill switch detiene conversacion Y automatizaciones",
        "notificaciones_dedup_y_prioridad": "Consolida y prioriza notificaciones",
        "frontera_fuentes": "Rechaza fuentes fuera del MVP",
        "privacidad_terceros": "Purga contenido de terceros al cerrar sesion",
    }
    todo = True
    for k, etiqueta in etiquetas.items():
        ok = caps.get(k, False)
        todo = todo and ok
        print(f"  [{'OK' if ok else 'XX'}] {etiqueta}")
    print("=" * 70)
    print("RESULTADO:", "CAPACIDAD M2 DEMOSTRADA" if todo else "ALGUNA CAPACIDAD NO SE DEMOSTRO")
    print(f"(backend: {'STACK REAL (Ollama)' if args_cli.real else 'mocks reproducibles'})")
    print(f"Efectos totales sobre el sistema de archivos, fuera del entorno de demo: ninguno ({work})")
    return 0 if todo else 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
