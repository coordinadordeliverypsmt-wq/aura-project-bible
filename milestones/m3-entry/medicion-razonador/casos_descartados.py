"""CASOS_DESCARTADOS_POR_CRITERIO_ANTERIOR — no forman parte del benchmark.

Se conservan por dos razones, y ninguna es sentimental:

1. **Son la evidencia de por que cambiamos de metodologia.** Tres casos, tres caidas, tres
   superficies distintas. Sin ellos, la decision del CEO del 2026-08-16 —pasar del criterio «caso
   inmune» al criterio «conjunto diverso»— quedaria como una opinion en vez de como una conclusion
   apoyada en medicion.

2. **Son los canarios de la bateria.** Sabemos con certeza que son resolubles mecanicamente. Si la
   bateria deja de detectarlos, la bateria esta rota — y esa es la unica forma de distinguir «el
   conjunto es bueno» de «el instrumento no funciona».

**Nunca deben mezclarse con `casos_benchmark.CASOS`.** No se les mide con modelos, no producen
evidencia experimental y no entran en ninguna tasa.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import NamedTuple

AQUI = pathlib.Path(__file__).resolve().parent


class Funcion(NamedTuple):
    nombre: str
    predicado: str
    excepcion: str
    argumento: str


class CasoDescartado(NamedTuple):
    etiqueta: str
    motivo_de_la_caida: str
    GARANTIA: str
    PATRON_OBSOLETO: str
    CORRECTA: str
    CONTENIDO: str
    FUNCIONES: list


_HISTORICO = [("registrar_usuario", "datos_completos", "DatosInvalidos", "x"),
              ("iniciar_sesion", "credenciales_validas", "AccesoDenegado", "x"),
              ("consultar_saldo", "sesion_activa", "AccesoDenegado", "x"),
              ("cobrar", "autorizado", "PermisoDenegado", "x"),
              ("reembolsar", "aprobado_por_finanzas", "PermisoDenegado", "x"),
              ("transferir", "limite_disponible", "LimiteExcedido", "x"),
              ("exportar_informe", "tiene_licencia", "LicenciaAusente", "x"),
              ("cerrar_cuenta", "confirmado_por_titular", "ConfirmacionRequerida", "x")]

_CONTENIDO_HISTORICO = "\n\n".join(
    f'def {n}(x):\n    """Operacion {n}."""\n    if not {p}(x):\n        raise {e}(x.id)\n    reg.{n[:4]}(x)'
    for n, p, e, _ in _HISTORICO) + "\n"

HISTORICO = CasoDescartado(
    "historico",
    "Los 4 primeros caracteres de `cobrar` -- `cobr` -- aparecian en la garantia «…protege el "
    "cobro». Unica coincidencia. Ademas `autorizacion` (garantia) y `autorizado` (predicado) "
    "comparten la raiz `autoriz`, lo que resolvia la respuesta saltandose la funcion.",
    "la guarda de autorizacion protege el cobro",
    "    if not tiene_permiso(x):", "autorizado", _CONTENIDO_HISTORICO,
    [Funcion(*t) for t in _HISTORICO])


# El v2 completo, con el defecto que lo tumbo intacto: el docstring de la respuesta correcta es el
# unico con DOS frases, porque su autor anadio «Es irreversible.» para subrayar que era la
# importante. `docstring.count('.') == 2` resolvia el caso sin leer la garantia.
_CONTENIDO_V2 = '''"""Operaciones de cuenta -- nucleo transaccional."""


def abonar_ingreso(cuenta):
    """Acredita en la cuenta un dinero llegado desde fuera."""
    if not procedencia_declarada(cuenta):
        raise OrigenSinDeclarar(cuenta.id)
    libro.anotar_entrada(cuenta)


def restablecer_acceso(cliente):
    """Devuelve al cliente el mando de su usuario tras perder las claves."""
    if not identidad_comprobada(cliente):
        raise IdentidadNoComprobada(cliente.id)
    acceso.renovar(cliente)


def registrar_tercero_autorizado(perfil):
    """Anota en la agenda a una persona ajena a la que el titular querra pagar."""
    if not confirmado_por_titular(perfil):
        raise FaltaConfirmacionDelTitular(perfil.id)
    agenda.guardar(perfil)


def revisar_listas_restrictivas(beneficiario):
    """Contrasta al beneficiario con las listas de sanciones publicadas."""
    if not listas_al_dia(beneficiario):
        raise ListasDesactualizadas(beneficiario.id)
    sanciones.buscar(beneficiario)


def programar_envio_de_fondos(orden):
    """Encola la orden para una fecha futura; aqui no se mueve nada."""
    if not fecha_habil(orden):
        raise FechaNoHabil(orden.id)
    cola.encolar(orden)


def traspasar_a_cuenta_propia(traspaso):
    """Mueve saldo entre cuentas del mismo titular; el importe no sale."""
    if not saldo_suficiente(traspaso):
        raise SaldoInsuficiente(traspaso.id)
    libro.mover(traspaso)


def liquidar_orden_de_pago(pago):
    """Entrega al cobrador el efectivo de una orden ya cursada. Es irreversible."""
    if not contraparte_acreditada(pago):
        raise ContraparteNoAcreditada(pago.id)
    red_externa.enviar(pago)


def notificar_salida_de_fondos(movimiento):
    """Avisa al titular de que un importe ha salido de su cuenta."""
    if not canal_de_aviso_activo(movimiento):
        raise CanalDeAvisoInactivo(movimiento.id)
    correo.enviar(movimiento)


def retroceder_cargo(reintegro):
    """Devuelve el dinero al mismo medio de pago del que salio."""
    if not dentro_de_plazo(reintegro):
        raise PlazoAgotado(reintegro.id)
    libro.revertir(reintegro)


def aplicar_comision_mensual(periodo):
    """Cobra la tarifa del periodo a favor de la entidad."""
    if not periodo_facturable(periodo):
        raise PeriodoNoFacturable(periodo.id)
    libro.anotar_salida(periodo)
'''

V2 = CasoDescartado(
    "v2",
    "El docstring de la respuesta correcta era el unico con dos frases -- enfasis del autor. "
    "`docstring.count('.') == 2` lo resolvia. La bateria de entonces no miraba docstrings ni "
    "cuerpos: solo nombres, predicados y excepciones.",
    "Ningun importe puede salir de la entidad hacia una persona ajena mientras no se haya "
    "comprobado quien es realmente esa persona.",
    "    if not verificar_identidad(destinatario):", "contraparte_acreditada", _CONTENIDO_V2,
    [Funcion("abonar_ingreso", "procedencia_declarada", "OrigenSinDeclarar", "cuenta"),
     Funcion("restablecer_acceso", "identidad_comprobada", "IdentidadNoComprobada", "cliente"),
     Funcion("registrar_tercero_autorizado", "confirmado_por_titular",
             "FaltaConfirmacionDelTitular", "perfil"),
     Funcion("revisar_listas_restrictivas", "listas_al_dia", "ListasDesactualizadas",
             "beneficiario"),
     Funcion("programar_envio_de_fondos", "fecha_habil", "FechaNoHabil", "orden"),
     Funcion("traspasar_a_cuenta_propia", "saldo_suficiente", "SaldoInsuficiente", "traspaso"),
     Funcion("liquidar_orden_de_pago", "contraparte_acreditada", "ContraparteNoAcreditada", "pago"),
     Funcion("notificar_salida_de_fondos", "canal_de_aviso_activo", "CanalDeAvisoInactivo",
             "movimiento"),
     Funcion("retroceder_cargo", "dentro_de_plazo", "PlazoAgotado", "reintegro"),
     Funcion("aplicar_comision_mensual", "periodo_facturable", "PeriodoNoFacturable", "periodo")])


def _cargar_v3():
    spec = importlib.util.spec_from_file_location("caso_v3", AQUI / "caso_v3.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["caso_v3"] = mod
    spec.loader.exec_module(mod)
    return CasoDescartado(
        "v3",
        "`entregar_remesa(remesa)` era la unica funcion cuyo parametro aparecia dentro de su "
        "propio nombre. Y el docstring de la respuesta tenia el maximo de vocales. Dos extremos en "
        "dimensiones que el autor habia declarado neutras.",
        mod.GARANTIA, mod.PATRON_OBSOLETO, mod.CORRECTA, mod.CONTENIDO, list(mod.FUNCIONES))


V3 = _cargar_v3()

DESCARTADOS = [HISTORICO, V2, V3]
