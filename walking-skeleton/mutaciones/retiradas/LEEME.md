# Catálogos de mutación retirados

Aquí viven los catálogos cuyo código protegido **ya no existe por una decisión registrada**, no por descuido. No se
borran: quedan como historia, por si el código vuelve. El auditor de garantías (`test_garantias_vigentes.py`) solo lee
`mutaciones/*.toml`, así que no los cuenta.

| Catálogo | Protegía | Por qué no existe ya | Retirado |
|---|---|---|---|
| `arnes-validador-comandos.toml` (VAL-M1..M5) | `validador.py` del arnés **OpenCode** (agente externo) | CHECKPOINT §«OpenCode — cerrado, no reabrir»: desinstalado y verificado («ausente · 0 residuos · 0 procesos · 0 credenciales»). Exigía clave de proveedor y chocaba con D24. Búsqueda 2026-10-04 (`find /`, `grep`, `git log --all`): no existe en ningún sitio | 2026-10-04 |
| `arnes-ciclo-de-vida-diario-en-sitio.toml` (AL-M4, AL-M5) | La **escritura** del diario `.mutar-en-curso.json` en la raíz del proyecto (`herramientas/mutar.py`) | Regla 6 del arnés (CHECKPOINT 2026-10-25 (w)): la mutación corre en una copia aislada y el proyecto nunca contiene el mutante. La escritura del diario se retiró por ser código muerto (ambos mutantes sobrevivían). La recuperación de diarios heredados sigue protegida (AL-M6, M12, M13, M19) | 2026-10-25 |

**Para restaurar un catálogo:** si el código vuelve, devuélvelo a `mutaciones/`, declara su `raiz` si vive en otro plano y
ejecútalo con `python3 -m herramientas.mutar`.
