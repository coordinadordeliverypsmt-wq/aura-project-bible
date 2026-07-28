"""Unit: productor de notificaciones de acciones (MVP Centro de Notificaciones).

Regla de arquitectura del CEO (2026-07-28): **las notificaciones son comunicación, no registros.** El
productor NO almacena el resultado bruto del motor (`estado=ejecutada`, `accion=mover_archivo`); genera un
mensaje en LENGUAJE NATURAL, listo para mostrarse al usuario tal cual (voz, avatar, móvil, panel…). Los
detalles técnicos quedan en auditoría; la notificación contiene únicamente lo que AURA le diría al usuario.
"""

from aura_skeleton.core.notificaciones import Notificacion, notificacion_de_accion

# Jerga tecnica que NUNCA debe aparecer en el titulo de una notificacion (seria un registro, no un mensaje).
_JERGA = ("estado=", "accion=", "motivo=", "ejecutada", "detenida", "error", "None", "{", "}", "trace")


def _sin_jerga(titulo: str) -> bool:
    bajo = titulo.lower()
    return not any(j.lower() in bajo for j in _JERGA)


def test_accion_completada_se_cuenta_en_lenguaje_natural():
    n = notificacion_de_accion(
        "mover_archivo",
        {"origen": "/home/u/informe.pdf", "destino": "/home/u/Descargas/informe.pdf"},  # ruta final
        {"estado": "ejecutada"},
    )
    assert isinstance(n, Notificacion)
    assert n.fuente == "aura"
    assert n.titulo == "Moví informe.pdf a Descargas."
    assert _sin_jerga(n.titulo)


def test_accion_fallida_explica_el_motivo_en_lenguaje_humano():
    n = notificacion_de_accion(
        "borrar_archivo",
        {"ruta": "/home/u/carpeta_proyecto"},
        {"estado": "error", "motivo": "fallo del sistema de archivos: Permission denied"},
    )
    assert n.titulo == "No pude eliminar carpeta_proyecto porque estaba protegida."
    assert _sin_jerga(n.titulo)


def test_accion_detenida_por_confirmacion():
    n = notificacion_de_accion(
        "borrar_archivo",
        {"ruta": "/home/u/x"},
        {"estado": "detenida", "motivo": "permisos: requiere confirmacion (lista roja)"},
    )
    assert n.titulo == "No ejecuté una solicitud porque requería tu confirmación."
    assert _sin_jerga(n.titulo)


def test_accion_rechazada_por_permisos():
    n = notificacion_de_accion(
        "escribir_archivo",
        {"ruta": "/etc/passwd"},
        {"estado": "detenida", "motivo": "permisos: fuera del ambito permitido"},
    )
    assert "no ejecuté" in n.titulo.lower()
    assert _sin_jerga(n.titulo)


def test_el_titulo_nunca_contiene_estado_tecnico():
    """Ninguna combinacion accion/estado debe filtrar jerga tecnica al titulo (comunicable, no log)."""
    casos = [
        ("mover_archivo", {"origen": "a.txt", "destino": "b"}, {"estado": "ejecutada"}),
        ("encender_dispositivo", {"device": "lampara"}, {"estado": "ejecutada"}),
        ("borrar_archivo", {"ruta": "x"}, {"estado": "error", "motivo": "algo raro interno"}),
        ("apagar_dispositivo", {"device": "tv"}, {"estado": "detenida", "motivo": "permisos: x"}),
    ]
    for accion, args, res in casos:
        n = notificacion_de_accion(accion, args, res)
        assert _sin_jerga(n.titulo), f"jerga tecnica en: {n.titulo!r}"
        assert n.titulo and n.titulo[0].isupper() and n.titulo.endswith(".")
