import pytest


@pytest.fixture(autouse=True)
def _sin_plano_de_control_real(monkeypatch):
    """La bateria NUNCA lee el ciclo autonomo real del equipo que la ejecuta.

    `componer()` cablea la fuente de estado autonomo cuando encuentra `entorno/control-plane`, que en
    este repositorio SIEMPRE esta. Sin esta fixture, las pruebas de conversacion leerian el
    `eventos.jsonl` de verdad y su resultado cambiaria solo cada media hora, cuando el `cron`
    despierta a AURORA: una prueba cuyo veredicto depende de la hora no prueba nada.

    Quien quiera ejercitar la superficie inyecta su propia fuente, que es ademas la unica forma de
    fijar los seis casos (ejecutando / esperando / sin trabajo / bloqueado / elevado / proximo ciclo)
    sin fabricar un entorno (D34).
    """
    monkeypatch.setenv("AURA_CONTROL_PLANE", "")
