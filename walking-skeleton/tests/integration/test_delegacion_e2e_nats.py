"""E2E AISLADO de la delegación segura: nats-server local (127.0.0.1, puerto libre, PKI de prueba en tmp_path),
HC-1 SIMULADO + nodo SIMULADO como tareas asyncio, firmador REAL como proceso aparte. Todo se mata por PID.

La delegación real sigue DESHABILITADA: no se toca el receptor, el agente de producción ni los permisos NATS reales
(los permisos de aquí son los de M1 escritos en una configuración de PRUEBA).
"""

from __future__ import annotations

import asyncio
import base64
import json
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import nats
import pytest

from aura_skeleton import nodo_agente
from aura_skeleton.adapters.almacen_consumidas import AlmacenConsumidas
from aura_skeleton.adapters.diario_hc1 import NOMBRE as NOMBRE_DIARIO
from aura_skeleton.adapters.diario_hc1 import DiarioHC1
from aura_skeleton.adapters.fijacion_spki import aplicar_fijacion, huella_spki
from aura_skeleton.adapters.firma_delegacion import generar_firmante, guardar_clave_privada, verificador_de
from aura_skeleton.adapters.firmador_hc1 import pedir_firma
from aura_skeleton.core.delegacion import (
    DOMINIO_ORDEN,
    DOMINIO_RESULTADO,
    EstadoNodo,
    Motivo,
    PoliticaNodo,
    RechazoOrden,
    abrir_sobre,
    empaquetar_sobre,
    verificar_y_leer,
)
from aura_skeleton.core.delegacion_hc1 import Estado, SeguimientoHC1
from aura_skeleton.core.delegacion_nodo import NodoDelegado
from tests.delegacion_apoyo import NODO, OTRO_NODO
from tests.tls_apoyo import AcPrueba, contexto_cliente

_WS = Path(__file__).resolve().parents[2]


def _binario() -> str | None:
    return shutil.which("nats-server") or next(
        (str(p) for p in [Path.home() / ".local" / "bin" / "nats-server"] if p.is_file()), None
    )


pytestmark = pytest.mark.skipif(_binario() is None, reason="nats-server no está en el PATH ni en ~/.local/bin")


class RelojReal:
    def __init__(self) -> None:
        self.desfase = 0.0
        """Segundos que se «avanzan» al reloj de HC-1 (simula el tiempo que HC-1 estuvo caída)."""

    def ahora(self) -> float:
        return time.time() + self.desfase

    def sincronizado(self) -> bool:
        return True


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def esperar(cond: Callable[[], bool], motivo: str, maximo: float = 8.0) -> None:
    limite = time.monotonic() + maximo
    while time.monotonic() < limite:
        if cond():
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"no se cumplió: {motivo}")


class Entorno:
    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.ac = AcPrueba(raiz)
        self.legitimo = self.ac.servidor("hc1")
        self.impostor = self.ac.servidor("impostor")
        self.claves = {n: secrets.token_hex(16) for n in ("hc1", NODO, OTRO_NODO)}
        self.procesos: list[subprocess.Popen[bytes]] = []
        self.puerto = self._nats(self.legitimo, "legitimo")
        self.puerto_impostor = self._nats(self.impostor, "impostor")
        self.hc1_firmante = generar_firmante("hc1-k1")
        self.autoridad_firmante = generar_firmante("autoridad-k1")
        self.nodo_firmante = generar_firmante(NODO)
        self.otro_firmante = generar_firmante(OTRO_NODO)
        self.pin = [huella_spki(self.legitimo.der)]

    def _nats(self, par: Any, nombre: str) -> int:
        puerto = _puerto_libre()
        perm = lambda pub, sub: f'permissions: {{publish: {{allow: ["{pub}"]}}, subscribe: {{allow: ["{sub}"]}}}}'  # noqa: E731
        usuarios = ",\n".join(
            [
                f'{{user: "hc1", password: "{self.claves["hc1"]}", {perm("nodo.tarea.>", "nodo.resultado.>")}}}',
                *(
                    f'{{user: "nodo-{n}", password: "{self.claves[n]}", {perm(f"nodo.resultado.{n}", f"nodo.tarea.{n}")}}}'
                    for n in (NODO, OTRO_NODO)
                ),
            ]
        )
        conf = self.raiz / f"nats-{nombre}.conf"
        conf.write_text(
            f'listen: "127.0.0.1:{puerto}"\nmax_payload: 65536\n'
            f'tls {{ cert_file: "{par.cert}", key_file: "{par.clave}", timeout: 5 }}\n'
            f"authorization {{ users: [\n{usuarios}\n] }}\n"
        )
        proc = subprocess.Popen(
            [_binario() or "", "-c", str(conf)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self.procesos.append(proc)
        limite = time.monotonic() + 15
        while time.monotonic() < limite:
            assert proc.poll() is None, "nats-server terminó al arrancar"
            try:
                with socket.create_connection(("127.0.0.1", puerto), timeout=0.2):
                    return puerto
            except OSError:
                time.sleep(0.05)
        raise AssertionError("nats-server no abrió el puerto")

    def terminar(self) -> None:
        for p in self.procesos:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(10)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(5)

    async def conectar(self, usuario: str, clave: str, puerto: int | None = None, pin: list[str] | None = None) -> Any:
        ctx = aplicar_fijacion(contexto_cliente(self.ac.ca_pem), pin or self.pin)
        return await nats.connect(
            f"tls://127.0.0.1:{puerto or self.puerto}", user=usuario, password=clave, tls=ctx,
            allow_reconnect=False, connect_timeout=5,
        )  # fmt: skip


class Firmador:
    def __init__(self, env: Entorno) -> None:
        d = env.raiz / "firmador"
        d.mkdir(mode=0o700)
        guardar_clave_privada(d / "clave.pem", env.hc1_firmante._Firmante__clave)  # type: ignore[attr-defined]
        self.sock, self.log = d / "f.sock", d / "log.jsonl"
        (d / "c.json").write_text(
            json.dumps({"kid": "hc1-k1", "emisor": "hc1", "destinatarios": [NODO, OTRO_NODO],
                        "capacidades": ["calcular_resumen_sha256"], "epoch": 1, "clave": str(d / "clave.pem"),
                        "socket": str(self.sock), "log": str(self.log)})
        )  # fmt: skip
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "aura_skeleton.adapters.firmador_hc1", str(d / "c.json")],
            cwd=_WS, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )  # fmt: skip
        assert self.proc.stdout is not None and self.proc.stdout.readline().strip() == "listo"
        env.procesos.append(self.proc)  # type: ignore[arg-type]

    async def pedir(self, **cambios: Any) -> dict[str, Any]:
        pet = {"tarea": "t-1", "intento": 1, "destinatario": NODO, "capacidad": "calcular_resumen_sha256",
               "argumentos": {"texto": "hola aura"}, "vida_s": 60}  # fmt: skip
        pet.update(cambios)
        return await asyncio.to_thread(pedir_firma, self.sock, pet)


class RegistroArchivo:
    """Registro SINTÉTICO en fichero, idempotente por `id_ejecucion` (contrato de `Registrar`)."""

    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta

    def ya_registrado(self, id_ejecucion: str) -> bool:
        if not self.ruta.exists():
            return False
        return any(json.loads(x)["id_ejecucion"] == id_ejecucion for x in self.ruta.read_text().splitlines())

    def __call__(self, entrada: dict[str, Any]) -> None:
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, sort_keys=True) + "\n")


class Hc1Sim:
    """HC-1 simulado: sigue las ejecuciones, valida resultados y los incorpora a un log SINTÉTICO."""

    def __init__(self, env: Entorno, firmador: Firmador) -> None:
        self.env, self.firmador = env, firmador
        self.registro = env.raiz / "registro_sintetico.jsonl"
        self.dir_diario = env.raiz / "hc1-diario"
        self.reloj = RelojReal()
        self.destino = RegistroArchivo(self.registro)
        self.rechazos: list[Motivo] = []
        self.nc: Any = None
        self.seg = self._arrancar_seguimiento()

    def _arrancar_seguimiento(self) -> SeguimientoHC1:
        """Proceso de HC-1 «nuevo»: el estado se reconstruye SOLO desde el diario en disco (M-2)."""
        env = self.env
        return SeguimientoHC1(
            verificador_de({NODO: env.nodo_firmante.publica(), OTRO_NODO: env.otro_firmante.publica()}),
            self.reloj,
            diario=DiarioHC1(self.dir_diario),
            verificar_autoridad=verificador_de({"autoridad-k1": env.autoridad_firmante.publica()}),
            kids_autoridad=frozenset({"autoridad-k1"}),
            kid_hc1="hc1-k1",
        )

    async def iniciar(self) -> None:
        self.nc = await self.env.conectar("hc1", self.env.claves["hc1"])
        await self.nc.subscribe("nodo.resultado.>", cb=self._al_recibir)
        await self.nc.flush()

    async def caer(self) -> None:
        """HC-1 muere: se pierde la conexión y TODO el estado en memoria."""
        if self.nc is not None and not self.nc.is_closed:
            await self.nc.close()
        self.seg = None  # type: ignore[assignment]

    async def reiniciar(self, desfase_s: float = 0.0) -> None:
        self.reloj.desfase += desfase_s
        self.seg = self._arrancar_seguimiento()
        await self.iniciar()

    async def _al_recibir(self, msg: Any) -> None:
        id_nodo = msg.subject.rsplit(".", 1)[1]
        tipo = (msg.headers or {}).get("tipo")
        try:
            if tipo == "acuse":
                self.seg.recibir_acuse(msg.data, id_nodo)
            else:
                ej = self.seg.recibir_resultado(msg.data, id_nodo)
                if self.seg.validar(ej.id_ejecucion):
                    self.seg.incorporar(ej.id_ejecucion, self.destino)
        except RechazoOrden as e:
            self.rechazos.append(e.motivo)

    async def delegar(self, techo: float = 30, **cambios: Any) -> tuple[bytes, str]:
        r = await self.firmador.pedir(**cambios)
        assert r["ok"] is True, r
        self.seg.registrar_emision(r["sobre"], techo_total_s=techo)
        await self.nc.publish(f"nodo.tarea.{cambios.get('destinatario', NODO)}", r["sobre"])
        await self.nc.flush()
        return r["sobre"], r["id_ejecucion"]

    async def publicar_crudo(self, subject: str, datos: bytes) -> None:
        await self.nc.publish(subject, datos)
        await self.nc.flush()


class NodoSim:
    def __init__(
        self, env: Entorno, id_nodo: str, firmante: Any, directorio: Path, arranque: float | None = None
    ) -> None:
        self.env, self.id = env, id_nodo
        pol = PoliticaNodo(
            id_nodo, {"hc1-k1": "hc1"}, frozenset({"calcular_resumen_sha256"}), RelojReal(),
            time.time() - 5 if arranque is None else arranque,
        )  # fmt: skip
        self.almacen = AlmacenConsumidas(directorio)
        self.nodo = NodoDelegado(pol, verificador_de({"hc1-k1": env.hc1_firmante.publica()}),
                                 self.almacen, firmante.firmar)  # fmt: skip
        self.rechazos: list[Motivo] = []
        self.ejecutadas: list[str] = []
        self.morir_ejecutando = False
        """Tras acusar y marcar EJECUTANDO, el nodo «muere» (sin marcar FALLIDA ni COMPLETADA)."""
        self.perder_resultado = False
        """Ejecuta y COMPLETA (resultado firmado guardado) pero el resultado no llega a publicarse."""
        self.antes_del_resultado: Callable[[], Awaitable[None]] | None = None
        self.manipular: Callable[[bytes], bytes] = lambda b: b
        self.nc: Any = None

    async def iniciar(self) -> None:
        self.nc = await self.env.conectar(f"nodo-{self.id}", self.env.claves[self.id])
        await self.nc.subscribe(f"nodo.tarea.{self.id}", cb=self._al_recibir)
        await self.nc.flush()

    async def _al_recibir(self, msg: Any) -> None:
        try:
            ac = self.nodo.aceptar(msg.data)
        except RechazoOrden as e:
            self.rechazos.append(e.motivo)
            return
        await self.nc.publish(f"nodo.resultado.{self.id}", ac.acuse, headers={"tipo": "acuse"})
        await self.nc.flush()
        if self.antes_del_resultado:
            await self.antes_del_resultado()
        if self.nc.is_closed:
            return
        if self.morir_ejecutando:
            self.almacen.iniciar_ejecucion(ac.orden.campos["id_ejecucion"])
            await self.nc.close()
            return
        self.ejecutadas.append(ac.orden.campos["id_ejecucion"])
        res = self.manipular(self.nodo.ejecutar(ac.orden))
        if self.perder_resultado:
            return
        await self.nc.publish(f"nodo.resultado.{self.id}", res, headers={"tipo": "resultado"})
        await self.nc.flush()

    async def parar(self) -> None:
        if self.nc is not None and not self.nc.is_closed:
            await self.nc.close()


@pytest.fixture
async def mundo(tmp_path: Path) -> AsyncIterator[tuple[Entorno, Firmador, Hc1Sim, list[NodoSim]]]:
    env = Entorno(tmp_path)
    nodos: list[NodoSim] = []
    hc1: Hc1Sim | None = None
    try:
        fir = Firmador(env)
        hc1 = Hc1Sim(env, fir)
        await hc1.iniciar()
        yield env, fir, hc1, nodos
    finally:
        for n in nodos:
            await n.parar()
        if hc1 is not None and hc1.nc is not None and not hc1.nc.is_closed:
            await hc1.nc.close()
        env.terminar()


async def _nodo(env: Entorno, nodos: list[NodoSim], dir_: str = "n1", **kw: Any) -> NodoSim:
    n = NodoSim(env, NODO, env.nodo_firmante, env.raiz / dir_, **kw)
    nodos.append(n)
    await n.iniciar()
    return n


# --- los 10 casos -------------------------------------------------------------------------------------------


async def test_01_orden_valida_aceptada_ejecutada_validada_e_incorporada(mundo: Any) -> None:
    env, _, hc1, nodos = mundo
    nodo = await _nodo(env, nodos)
    _, ident = await hc1.delegar()
    await esperar(lambda: hc1.seg.ejecucion(ident).estado is Estado.INCORPORADO, "incorporada")  # type: ignore[union-attr]
    ej = hc1.seg.ejecucion(ident)
    import hashlib

    assert ej is not None and ej.completada and ej.salida == hashlib.sha256(b"hola aura").hexdigest()
    assert nodo.ejecutadas == [ident] and nodo.rechazos == [] and hc1.rechazos == []


async def test_02_orden_alterada_en_transito_se_rechaza_y_no_se_ejecuta(mundo: Any) -> None:
    env, fir, hc1, nodos = mundo
    nodo = await _nodo(env, nodos)
    r = await fir.pedir()
    ab = abrir_sobre(r["sobre"])
    alterado = empaquetar_sobre(ab.kid, ab.payload.replace(b"hola aura", b"hola AURA"), ab.firma)
    await hc1.publicar_crudo(f"nodo.tarea.{NODO}", alterado)
    await esperar(lambda: nodo.rechazos == [Motivo.FIRMA_INVALIDA], "firma inválida")
    assert nodo.ejecutadas == []
    await hc1.publicar_crudo(f"nodo.tarea.{NODO}", r["sobre"])  # control: la original sí
    await esperar(lambda: nodo.ejecutadas == [r["id_ejecucion"]], "la original se ejecuta")


async def test_03_emisor_y_destinatario_incorrectos_se_rechazan(mundo: Any) -> None:
    env, fir, hc1, nodos = mundo
    nodo = await _nodo(env, nodos)
    # destinatario ajeno: el firmador lo firma legítimamente para OTRO nodo, pero llega al subject de NODO
    r = await fir.pedir(destinatario=OTRO_NODO)
    await hc1.publicar_crudo(f"nodo.tarea.{NODO}", r["sobre"])
    await esperar(lambda: Motivo.DESTINATARIO_AJENO in nodo.rechazos, "destinatario ajeno")
    # emisor incorrecto con la clave correcta (no pasa por el firmador: fabricado)
    from tests.delegacion_apoyo import campos_validos

    forjado = env.hc1_firmante.firmar(
        DOMINIO_ORDEN, json.dumps(campos_validos(emisor="hc9"), sort_keys=True, separators=(",", ":")).encode()
    )
    await hc1.publicar_crudo(f"nodo.tarea.{NODO}", forjado)
    await esperar(lambda: Motivo.EMISOR_DESCONOCIDO in nodo.rechazos, "emisor incorrecto")
    assert nodo.ejecutadas == []


async def test_04_orden_repetida_tras_reiniciar_el_nodo_se_rechaza(mundo: Any) -> None:
    env, _, hc1, nodos = mundo
    n1 = await _nodo(env, nodos)
    sobre, ident = await hc1.delegar()
    await esperar(lambda: n1.ejecutadas == [ident], "primera ejecución")
    await n1.parar()
    # reinicio: proceso/instancia NUEVA, mismo directorio de consumidas; `arranque` previo para aislar el almacén
    n2 = await _nodo(env, nodos, arranque=time.time() - 60)
    await hc1.publicar_crudo(f"nodo.tarea.{NODO}", sobre)
    await esperar(lambda: n2.rechazos == [Motivo.ORDEN_REPETIDA], "repetida")
    assert n2.ejecutadas == []
    # y con el arranque real (posterior a la orden), la barrera de N1 también la corta
    await n2.parar()
    n3 = await _nodo(env, nodos, dir_="otro-almacen", arranque=time.time())
    await hc1.publicar_crudo(f"nodo.tarea.{NODO}", sobre)
    await esperar(lambda: n3.rechazos == [Motivo.EMITIDA_ANTES_DEL_ARRANQUE], "anterior al arranque")


async def test_05_resultado_alterado_o_de_otro_nodo_se_rechaza(mundo: Any) -> None:
    env, _, hc1, nodos = mundo
    nodo = await _nodo(env, nodos)

    def corromper(res: bytes) -> bytes:
        ab = abrir_sobre(res)
        return empaquetar_sobre(ab.kid, ab.payload.replace(b'"salida":"', b'"salida":"0'), ab.firma)

    nodo.manipular = corromper
    _, ident = await hc1.delegar()
    await esperar(lambda: Motivo.FIRMA_INVALIDA in hc1.rechazos, "resultado alterado")
    assert not hc1.seg.ejecucion(ident).completada  # type: ignore[union-attr]

    # otro nodo legítimo responde por la orden de NODO desde SU subject: firma e identidad válidas, destinatario no
    otro = NodoSim(env, OTRO_NODO, env.otro_firmante, env.raiz / "n2")
    nodos.append(otro)
    await otro.iniciar()
    ej = hc1.seg.ejecucion(ident)
    assert ej is not None
    payload = json.dumps(
        {"v": 1, "alg": "ed25519", "tarea": ej.tarea, "intento": 1, "id_nodo": OTRO_NODO, "id_ejecucion": ident,
         "hash_tarea": ej.hash_tarea, "salida": "0" * 64}, sort_keys=True, separators=(",", ":"),
    ).encode()  # fmt: skip
    await otro.nc.publish(
        f"nodo.resultado.{OTRO_NODO}", otro_res := env.otro_firmante.firmar(DOMINIO_RESULTADO, payload)
    )
    await otro.nc.flush()
    await esperar(lambda: Motivo.NODO_AJENO in hc1.rechazos, "resultado de otro nodo")
    assert otro_res and not hc1.seg.ejecucion(ident).completada  # type: ignore[union-attr]


async def test_05b_un_nodo_no_puede_publicar_en_el_subject_de_otro_la_acl_lo_impide(mundo: Any) -> None:
    env, _, hc1, nodos = mundo
    otro = NodoSim(env, OTRO_NODO, env.otro_firmante, env.raiz / "n2")
    nodos.append(otro)
    await otro.iniciar()
    await otro.nc.publish(f"nodo.resultado.{NODO}", b"suplantacion")
    await otro.nc.flush()
    await asyncio.sleep(0.5)
    assert hc1.rechazos == [] and hc1.seg.rechazos == []  # nunca llegó (permissions violation en el broker)
    await otro.nc.publish(f"nodo.resultado.{OTRO_NODO}", b"basura")  # control: su propio subject sí llega a HC-1
    await otro.nc.flush()
    await esperar(lambda: len(hc1.rechazos) == 1, "su propio subject sí llega")


async def test_06_tls_con_identidad_incorrecta_no_conecta_y_la_legitima_si(mundo: Any) -> None:
    env, _, _, _ = mundo
    from aura_skeleton.nodo_agente import ConfigAgente

    datos = env.raiz / "datos-agente"
    datos.mkdir()
    shutil.copy(env.ac.ca_pem, datos / "ca.crt")

    def fabrica(puerto: int, pin: list[str]) -> Any:
        cfg = ConfigAgente(str(datos), NODO, [f"tls://127.0.0.1:{puerto}"], f"nodo-{NODO}", "n", 10.0, tuple(pin))
        return nodo_agente._fabrica_nats(cfg, env.claves[NODO], resolutor=lambda _: None)

    ok = await asyncio.wait_for(fabrica(env.puerto, env.pin)(), 15)  # control: legítimo + pin correcto
    assert ok.conectado
    await ok.close()
    # impostor: certificado de la MISMA CA y otra clave. Sin pin entra (es la brecha); con pin, NO.
    sin_pin = await asyncio.wait_for(fabrica(env.puerto_impostor, [])(), 15)
    assert sin_pin.conectado
    await sin_pin.close()
    with pytest.raises(Exception):  # noqa: B017 - nats-py envuelve el fallo TLS en varios tipos
        await asyncio.wait_for(fabrica(env.puerto_impostor, env.pin)(), 20)


async def test_07_firma_no_autorizada_nodo_la_rechaza_y_el_firmador_se_niega(mundo: Any) -> None:
    env, fir, hc1, nodos = mundo
    nodo = await _nodo(env, nodos)
    intruso = generar_firmante("hc1-k1")  # kid correcto, clave ajena
    from tests.delegacion_apoyo import campos_validos

    await hc1.publicar_crudo(
        f"nodo.tarea.{NODO}",
        intruso.firmar(DOMINIO_ORDEN, json.dumps(campos_validos(), sort_keys=True, separators=(",", ":")).encode()),
    )
    await esperar(lambda: nodo.rechazos == [Motivo.FIRMA_INVALIDA], "firma no autorizada")
    assert (await fir.pedir(capacidad="rm_rf")) == {"ok": False, "motivo": Motivo.CAPACIDAD_NO_REGISTRADA.value}
    assert nodo.ejecutadas == []


async def test_08_desconexion_deja_el_resultado_ambiguo_o_interrumpido_explicito(mundo: Any) -> None:
    env, _, hc1, nodos = mundo
    # a) el nodo acusa y se desconecta antes de devolver resultado => AMBIGUO (la orden pudo tener efecto)
    nodo = await _nodo(env, nodos)

    async def caer() -> None:
        await nodo.nc.close()

    nodo.antes_del_resultado = caer
    _, ident = await hc1.delegar(tarea="t-amb")
    await esperar(lambda: hc1.seg.ejecucion(ident).estado is Estado.ACEPTADA, "acuse recibido")  # type: ignore[union-attr]
    hc1.seg.marcar_desconexion(NODO)
    assert hc1.seg.ejecucion(ident).estado is Estado.AMBIGUO  # type: ignore[union-attr]
    # b) nodo offline: ni acuse => INTERRUMPIDA (reintentable)
    _, ident2 = await hc1.delegar(tarea="t-off")
    await asyncio.sleep(0.3)
    hc1.seg.marcar_desconexion(NODO)
    assert hc1.seg.ejecucion(ident2).estado is Estado.INTERRUMPIDA  # type: ignore[union-attr]
    assert not hc1.seg.ejecucion(ident).completada and not hc1.seg.ejecucion(ident2).completada  # type: ignore[union-attr]


async def test_09_vinculacion_tarea_orden_ejecucion_resultado(mundo: Any) -> None:
    env, _, hc1, nodos = mundo
    nodo = await _nodo(env, nodos)
    _, id1 = await hc1.delegar(tarea="t-uno", argumentos={"texto": "uno"})
    await esperar(lambda: hc1.seg.ejecucion(id1).completada, "tarea 1 completa")  # type: ignore[union-attr]
    ej1 = hc1.seg.ejecucion(id1)
    assert ej1 is not None and ej1.sobre_resultado is not None
    _, id2 = await hc1.delegar(tarea="t-dos", argumentos={"texto": "dos"})
    await esperar(lambda: hc1.seg.ejecucion(id2).completada, "tarea 2 completa")  # type: ignore[union-attr]
    ej2 = hc1.seg.ejecucion(id2)
    assert ej2 is not None
    assert (ej1.hash_tarea, ej1.id_ejecucion, ej1.salida) != (ej2.hash_tarea, ej2.id_ejecucion, ej2.salida)
    # reenviar el resultado 1 (firma válida) no sirve para la tarea 2 ni se acepta dos veces
    antes = len(hc1.rechazos)
    await nodo.nc.publish(f"nodo.resultado.{NODO}", ej1.sobre_resultado, headers={"tipo": "resultado"})
    await nodo.nc.flush()
    await esperar(lambda: len(hc1.rechazos) == antes + 1, "reenvío rechazado")
    assert hc1.rechazos[-1] is Motivo.RESULTADO_DUPLICADO and ej2.salida != ej1.salida


async def test_09b_el_resultado_aceptado_queda_en_el_registro_sintetico_y_se_reverifica_offline(mundo: Any) -> None:
    env, _, hc1, nodos = mundo
    await _nodo(env, nodos)
    _, ident = await hc1.delegar()
    await esperar(lambda: hc1.registro.exists(), "registro escrito")
    lineas = [json.loads(x) for x in hc1.registro.read_text().splitlines()]
    assert len(lineas) == 1 and lineas[0]["evento"] == "resultado_remoto" and lineas[0]["verificado"] is True
    assert lineas[0]["id_ejecucion"] == ident
    # ni un rechazo ni un latido generan hechos: solo lo incorporado está en el registro
    orden = base64.b64decode(lineas[0]["orden_firmada"])
    res = base64.b64decode(lineas[0]["resultado_firmado"])
    _, co = verificar_y_leer(orden, DOMINIO_ORDEN, verificador_de({"hc1-k1": env.hc1_firmante.publica()}))
    _, cr = verificar_y_leer(res, DOMINIO_RESULTADO, verificador_de({NODO: env.nodo_firmante.publica()}))
    import hashlib

    assert co["id_ejecucion"] == cr["id_ejecucion"] == ident
    assert cr["hash_tarea"] == hashlib.sha256(abrir_sobre(orden).payload).hexdigest() == lineas[0]["hash_tarea"]


# --- revisión de seguridad: caídas, ambigüedad y persistencia (E2E 10-12) -------------------------------------------


async def test_10_caida_de_hc1_y_del_nodo_el_estado_es_recuperable_y_explicito_desde_disco(mundo: Any) -> None:
    env, _, hc1, nodos = mundo
    nodo = await _nodo(env, nodos)
    nodo.morir_ejecutando = True
    _, ident = await hc1.delegar(techo=30)
    await esperar(lambda: hc1.seg.ejecucion(ident).estado is Estado.ACEPTADA, "acuse recibido")  # type: ignore[union-attr]
    await esperar(lambda: nodo.nc.is_closed, "el nodo muere ejecutando")
    ej_antes = hc1.seg.ejecucion(ident)
    assert ej_antes is not None
    await hc1.caer()  # caen HC-1 y el nodo: no queda NADA en memoria
    # --- reinicio de ambos, 100 s después --------------------------------------------------------------------------
    await hc1.reiniciar(desfase_s=100)
    ej = hc1.seg.ejecucion(ident)
    assert ej is not None and ej.hash_tarea == ej_antes.hash_tarea  # reconstruida desde el diario
    assert ej.estado is Estado.AMBIGUO  # vencida con acuse: EXPLÍCITO, no «se perdió»
    assert not ej.completada and hc1.seg.recuperadas == 1
    nodo2 = await _nodo(env, nodos, arranque=time.time() - 60)
    assert nodo2.almacen.estado(ident) is EstadoNodo.AMBIGUA  # el nodo también lo sabe, desde su disco
    assert nodo2.nodo.reenviar_resultado(ident) is None  # no hay resultado: nunca se completó
    eventos = [json.loads(x)["ev"] for x in (hc1.dir_diario / NOMBRE_DIARIO).read_text().splitlines()]
    assert eventos == ["emision", "acuse", "interrupcion"]  # y la decisión quedó ANOTADA


async def test_11_una_ejecucion_ambigua_no_se_repite_y_solo_se_resuelve_por_la_via_explicita(mundo: Any) -> None:
    env, _, hc1, nodos = mundo
    nodo = await _nodo(env, nodos)
    nodo.perder_resultado = True  # ejecuta y COMPLETA, pero el resultado no llega
    sobre, ident = await hc1.delegar(techo=30)
    await esperar(lambda: nodo.ejecutadas == [ident], "el nodo ejecutó")
    await esperar(lambda: hc1.seg.ejecucion(ident).estado is Estado.ACEPTADA, "acuse recibido")  # type: ignore[union-attr]
    await hc1.caer()
    await hc1.reiniciar(desfase_s=100)
    assert hc1.seg.ejecucion(ident).estado is Estado.AMBIGUO  # type: ignore[union-attr]
    # 1) la misma orden otra vez: el nodo NO la repite
    await hc1.publicar_crudo(f"nodo.tarea.{NODO}", sobre)
    await esperar(lambda: Motivo.ORDEN_REPETIDA in nodo.rechazos, "el nodo rechaza la repetida")
    assert nodo.ejecutadas == [ident]
    # 2) el nodo reenvía el resultado YA firmado: HC-1 no lo acepta solo (está AMBIGUA)
    guardado = nodo.nodo.reenviar_resultado(ident)
    assert guardado is not None and nodo.nodo.reenviar_resultado(ident) == guardado  # idempotente
    await nodo.nc.publish(f"nodo.resultado.{NODO}", guardado, headers={"tipo": "resultado"})
    await nodo.nc.flush()
    await esperar(lambda: Motivo.EJECUCION_NO_EN_CURSO in hc1.rechazos, "HC-1 no lo acepta solo")
    assert hc1.seg.ejecucion(ident).estado is Estado.AMBIGUO  # type: ignore[union-attr]
    # 3) la vía EXPLÍCITA: sin autoridad no; con autoridad declarada, firma y vínculo válidos, sí, y queda registrado
    from aura_skeleton.core.delegacion import DOMINIO_RESOLUCION, payload_resolucion

    def autorizar(firmante: Any) -> bytes:
        t = hc1.reloj.ahora()  # el reloj de HC-1 (puede llevar desfase)
        return firmante.firmar(
            DOMINIO_RESOLUCION,
            payload_resolucion(ident, "resultado firmado recuperado del nodo", t, t + 60, str(uuid.uuid4())),
        )

    with pytest.raises(RechazoOrden) as e:
        hc1.seg.resolver_ambigua(ident, autorizar(generar_firmante("intruso-k9")), guardado)
    assert e.value.motivo is Motivo.SIN_AUTORIDAD  # una clave que no es la de autoridad no resuelve nada
    ej = hc1.seg.resolver_ambigua(ident, autorizar(env.autoridad_firmante), guardado)
    assert ej.estado is Estado.RESULTADO_FIRMADO and ej.resuelta_por == "autoridad-k1"
    assert hc1.seg.validar(ident) is True
    hc1.seg.incorporar(ident, hc1.destino)
    assert hc1.seg.ejecucion(ident).completada  # type: ignore[union-attr]
    await hc1.caer()
    await hc1.reiniciar()
    ej2 = hc1.seg.ejecucion(ident)
    assert ej2 is not None and ej2.completada and ej2.resuelta_por == "autoridad-k1"  # persistente
    assert nodo.ejecutadas == [ident]  # y la capacidad corrió UNA sola vez en todo el relato


async def test_12_resultado_aceptado_vinculado_a_su_orden_y_persistido_con_fsync_reverificable_offline(
    mundo: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    import os
    import stat

    env, _, hc1, nodos = mundo
    await _nodo(env, nodos)
    sincronizados: list[bool] = []
    real = os.fsync

    def espia(fd: int) -> None:
        sincronizados.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        real(fd)

    monkeypatch.setattr(os, "fsync", espia)
    _, ident = await hc1.delegar()
    await esperar(lambda: hc1.seg.ejecucion(ident).estado is Estado.INCORPORADO, "incorporada")  # type: ignore[union-attr]
    # emision, acuse, resultado, validacion, incorporando, incorporado: seis registros, cada uno con fsync del fichero
    assert sincronizados.count(False) >= 6
    monkeypatch.undo()
    await hc1.caer()  # HC-1 muere; lo único que queda es el disco
    registros, truncados = DiarioHC1(hc1.dir_diario).recuperar()
    assert truncados == 0 and [r["ev"] for r in registros] == [
        "emision",
        "acuse",
        "resultado",
        "validacion",
        "incorporando",
        "incorporado",
    ]
    # re-verificación OFFLINE: solo bytes del diario + claves públicas, sin HC-1 ni red
    orden = base64.b64decode(registros[0]["sobre"])
    resultado = base64.b64decode(registros[2]["sobre"])
    _, co = verificar_y_leer(orden, DOMINIO_ORDEN, verificador_de({"hc1-k1": env.hc1_firmante.publica()}))
    _, cr = verificar_y_leer(resultado, DOMINIO_RESULTADO, verificador_de({NODO: env.nodo_firmante.publica()}))
    assert co["id_ejecucion"] == cr["id_ejecucion"] == ident and co["tarea"] == cr["tarea"]
    assert cr["hash_tarea"] == hashlib.sha256(abrir_sobre(orden).payload).hexdigest()
    assert cr["salida"] == hashlib.sha256(co["argumentos"]["texto"].encode()).hexdigest()
    await hc1.reiniciar()
    assert hc1.seg.ejecucion(ident).completada  # type: ignore[union-attr]
