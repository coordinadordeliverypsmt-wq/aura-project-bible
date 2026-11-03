"""Conjunto de cinco casos — el benchmark del experimento A/B.

## Por que un conjunto y no un caso perfecto

Tres casos consecutivos cayeron ante transformaciones deterministas:

| Caso | Como cayo |
|---|---|
| historico | `cobrar`[:4] = `cobr` aparecia en «…protege el **cobro**» |
| V2 | el docstring correcto era el unico con dos frases — enfasis del autor |
| V3 | `entregar_remesa(remesa)`: la unica funcion con su parametro dentro del nombre |

El patron no era que los casos estuvieran mal disenados: era que **el criterio no convergia**. Cada
ronda ampliaba la bateria, y cada ampliacion descubria una superficie nueva. Exigir que un unico
caso sea estadisticamente indistinguible en toda dimension medible produce, ademas, codigo
irreal — y el objetivo es medir razonamiento, no resistencia a acertijos.

**Criterio nuevo, decidido por el CEO el 2026-08-16:**

> El conjunto debe impedir que una unica heuristica determinista simple explique de forma
> consistente los aciertos.

Una regla que acierta un caso y falla los demas **no invalida el benchmark**: no puede explicar un
acierto sostenido. Una regla que los explica todos, si.

## Que comparten los cinco casos, y que varia

**Identico:** la tarea conceptual —garantia -> funcion responsable -> guarda—, el contrato, la
definicion de D, la metrica y la superficie A/B.

**Variable, por variacion natural y no por trampa:** dominio, numero de funciones (5 a 7), posicion
de la respuesta, longitud de nombres y predicados, forma de los docstrings, cuerpos, tipos de
argumento y excepciones. Los casos parecen problemas de codigo razonables porque **la defensa viene
de la diversidad del conjunto, no de blindar cada pieza**.

## Derivacion automatica

`FUNCIONES` se obtiene **analizando el texto del caso**, no escribiendola aparte. En las versiones
anteriores era una lista paralela que podia desincronizarse del fichero que el modelo realmente ve
—y entonces la bateria habria medido un caso distinto del medido—. Ahora esa clase de fallo no
existe.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class Funcion(NamedTuple):
    nombre: str
    predicado: str
    excepcion: str
    argumento: str


class Caso(NamedTuple):
    letra: str
    NOMBRE_FICHERO: str
    GARANTIA: str
    PATRON_OBSOLETO: str
    PATRON_CORRECTO: str
    CONTENIDO: str
    FUNCIONES: list[Funcion]
    CORRECTA: str


_DEF = re.compile(r"def (\w+)\((\w+)[^)]*\):\n(.*?)(?=\ndef |\Z)", re.S)
_GUARDA = re.compile(r"^    if not (\w+)\(", re.M)
_RAISE = re.compile(r"^        raise (\w+)\(", re.M)


def _analizar(contenido: str) -> list[Funcion]:
    out = []
    for nombre, arg, cuerpo in _DEF.findall(contenido):
        g = _GUARDA.search(cuerpo)
        e = _RAISE.search(cuerpo)
        if not g or not e:
            raise ValueError(f"la funcion {nombre} no tiene guarda o raise reconocibles")
        out.append(Funcion(nombre, g.group(1), e.group(1), arg))
    return out


def _caso(letra, fichero, garantia, obsoleto, correcto, contenido) -> Caso:
    funcs = _analizar(contenido)
    if contenido.count(correcto) != 1:
        raise ValueError(f"caso {letra}: la respuesta no aparece exactamente una vez")
    if obsoleto in contenido:
        raise ValueError(f"caso {letra}: el patron obsoleto no deberia aparecer")
    correcta = _GUARDA.search(correcto + "\n").group(1)
    if correcta not in [f.predicado for f in funcs]:
        raise ValueError(f"caso {letra}: la respuesta no corresponde a ninguna guarda")
    return Caso(letra, fichero, garantia, obsoleto, correcto, contenido, funcs, correcta)


# ------------------------------------------------------------------- A · pagos salientes --

_A = '''"""Nucleo transaccional de cuentas."""


def registrar_ingreso(deposito):
    """Anota en el libro un dinero que llega desde otra entidad."""
    if not procedencia_declarada(deposito):
        raise OrigenSinDeclarar(deposito.id)
    libro.sumar(deposito)


def renovar_claves(cliente):
    """Emite credenciales nuevas cuando el titular pierde las suyas."""
    if not identidad_comprobada(cliente):
        raise IdentidadNoComprobada(cliente.id)
    acceso.renovar(cliente)


def guardar_beneficiario(perfil):
    """Deja anotado en la agenda a quien el titular podra pagar."""
    if not confirmado_por_titular(perfil):
        raise ConfirmacionAusente(perfil.id)
    agenda.guardar(perfil)


def revisar_sanciones(persona):
    """Compara a la persona con los listados oficiales publicados."""
    if not listado_vigente(persona):
        raise ListadoCaducado(persona.id)
    informe.emitir(persona)


def traspasar_entre_cuentas(traspaso):
    """Pasa saldo de una cuenta del titular a otra suya."""
    if not saldo_bastante(traspaso):
        raise SaldoInsuficiente(traspaso.id)
    libro.trasladar(traspaso)


def entregar_remesa(orden):
    """Pone la cuantia a disposicion de quien figura como destino."""
    if not contraparte_validada(orden):
        raise ContraparteSinValidar(orden.id)
    salida.emitir(orden)


def avisar_al_titular(movimiento):
    """Manda un correo por cada salida de la cuenta."""
    if not canal_operativo(movimiento):
        raise CanalCerrado(movimiento.id)
    correo.remitir(movimiento)
'''

# --------------------------------------------------------------- B · escritura en disco --

_B = '''"""Utilidades de fichero del area de trabajo."""


def leer_plantilla(ruta):
    """Devuelve el contenido de una plantilla del catalogo interno."""
    if not extension_permitida(ruta):
        raise ExtensionNoPermitida(ruta.id)
    return disco.leer(ruta)


def listar_carpeta(carpeta):
    """Enumera los nombres de fichero que contiene una carpeta."""
    if not carpeta_existe(carpeta):
        raise CarpetaAusente(carpeta.id)
    return disco.listar(carpeta)


def copiar_respaldo(par):
    """Duplica un fichero dentro del area de copias de seguridad."""
    if not espacio_disponible(par):
        raise DiscoLleno(par.id)
    disco.copiar(par)


def volcar_informe(salida):
    """Escribe el informe generado en la carpeta de resultados."""
    if not ruta_dentro_del_arbol(salida):
        raise RutaFueraDelArbol(salida.id)
    disco.escribir(salida)


def renombrar_adjunto(cambio):
    """Cambia el nombre de un adjunto sin moverlo de sitio."""
    if not nombre_libre(cambio):
        raise NombreOcupado(cambio.id)
    disco.renombrar(cambio)


def vaciar_temporales(purga):
    """Elimina los ficheros temporales anteriores a un plazo."""
    if not plazo_razonable(purga):
        raise PlazoAbsurdo(purga.id)
    disco.purgar(purga)
'''

# --------------------------------------------------------------------- C · sesiones --

_C = '''"""Gestion de sesiones de usuario."""


def abrir_sesion(credencial):
    """Crea una sesion nueva para un usuario que se identifica."""
    if not credencial_valida(credencial):
        raise CredencialRechazada(credencial.id)
    sesiones.crear(credencial)


def refrescar_vista(vista):
    """Vuelve a pintar la pantalla con los datos mas recientes."""
    if not vista_montada(vista):
        raise VistaNoMontada(vista.id)
    pantalla.pintar(vista)


def despachar_encargo(encargo):
    """Lanza una tarea que el usuario dejo programada para luego."""
    if not sesion_aun_valida(encargo):
        raise SesionCaducada(encargo.id)
    motor.ejecutar(encargo)


def consultar_perfil(peticion):
    """Devuelve los datos publicos del perfil solicitado."""
    if not perfil_publico(peticion):
        raise PerfilPrivado(peticion.id)
    return perfiles.leer(peticion)


def cerrar_sesion(sesion):
    """Termina la sesion en curso y libera sus recursos."""
    if not sesion_conocida(sesion):
        raise SesionDesconocida(sesion.id)
    sesiones.borrar(sesion)


def contar_conexiones(rango):
    """Cuenta las conexiones habidas en un intervalo de tiempo."""
    if not rango_coherente(rango):
        raise RangoInvalido(rango.id)
    return metricas.contar(rango)
'''

# --------------------------------------------------------------- D · notificaciones --

_D = '''"""Envio de boletines por correo."""


def componer_boletin(plantilla):
    """Redacta el texto del boletin a partir de una plantilla."""
    if not plantilla_completa(plantilla):
        raise PlantillaIncompleta(plantilla.id)
    return redactor.componer(plantilla)


def dar_de_alta(persona):
    """Apunta a una persona en la lista de distribucion."""
    if not correo_verificado(persona):
        raise CorreoSinVerificar(persona.id)
    lista.anadir(persona)


def remitir_boletin(envio):
    """Hace llegar el boletin ya compuesto a un destinatario."""
    if not sigue_suscrito(envio):
        raise SuscripcionRevocada(envio.id)
    correo.entregar(envio)


def anotar_apertura(acuse):
    """Registra que el destinatario llego a abrir el mensaje."""
    if not acuse_reciente(acuse):
        raise AcuseCaducado(acuse.id)
    metricas.anotar(acuse)


def resumir_periodo(periodo):
    """Genera un resumen de aperturas del intervalo indicado."""
    if not periodo_cerrado(periodo):
        raise PeriodoAbierto(periodo.id)
    return metricas.resumir(periodo)
'''

# ------------------------------------------------------------------- E · inventario --

_E = '''"""Preparacion y salida de pedidos."""


def reservar_articulo(reserva):
    """Aparta unidades del almacen para un pedido en curso."""
    if not unidades_disponibles(reserva):
        raise SinExistencias(reserva.id)
    almacen.apartar(reserva)


def calcular_portes(tarifa):
    """Devuelve el coste de envio segun el peso y el destino."""
    if not destino_cubierto(tarifa):
        raise DestinoNoCubierto(tarifa.id)
    return tarifas.calcular(tarifa)


def emitir_factura(documento):
    """Genera el documento fiscal que corresponde al pedido."""
    if not datos_fiscales_completos(documento):
        raise DatosFiscalesIncompletos(documento.id)
    return facturacion.emitir(documento)


def anular_pedido(anulacion):
    """Cancela el pedido y repone las unidades en el almacen."""
    if not pedido_anulable(anulacion):
        raise PedidoNoAnulable(anulacion.id)
    almacen.reponer(anulacion)


def despachar_pedido(pedido):
    """Entrega el pedido al transportista para que lo reparta."""
    if not cobro_confirmado(pedido):
        raise CobroPendiente(pedido.id)
    transporte.recoger(pedido)


def consultar_seguimiento(envio):
    """Devuelve el estado en que se encuentra un envio."""
    if not envio_registrado(envio):
        raise EnvioDesconocido(envio.id)
    return transporte.estado(envio)
'''


CASOS: list[Caso] = [
    _caso("A", "nucleo_transaccional.py",
          "Ningun importe puede quedar en manos de una persona ajena si antes no se ha comprobado "
          "la identidad de esa persona.",
          "    if not verificar_identidad(cliente):",
          "    if not contraparte_validada(orden):", _A),
    _caso("B", "utiles_de_fichero.py",
          "Nada puede escribirse en una ubicacion situada fuera del area de trabajo autorizada.",
          "    if not comprobar_destino(ruta):",
          "    if not ruta_dentro_del_arbol(salida):", _B),
    _caso("C", "sesiones.py",
          "Una tarea aplazada no puede llegar a ejecutarse si la sesion que la autorizo ya expiro.",
          "    if not token_vigente(peticion):",
          "    if not sesion_aun_valida(encargo):", _C),
    _caso("D", "boletines.py",
          "No se hace llegar ningun mensaje a quien ha pedido dejar de recibirlos.",
          "    if not permiso_de_envio(destinatario):",
          "    if not sigue_suscrito(envio):", _D),
    _caso("E", "pedidos.py",
          "Ninguna mercancia sale del almacen antes de que el pago quede confirmado.",
          "    if not pago_recibido(compra):",
          "    if not cobro_confirmado(pedido):", _E),
]

POR_LETRA = {c.letra: c for c in CASOS}
