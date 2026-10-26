---
id: IE-012
titulo: Scanners-Box — catálogo de escáneres (solo categorías defensivas para revisar el código de AURA)
fuente: https://github.com/We5ter/Scanners-Box
rama-revision: master @ (fecha del último commit no visible; 1.012 commits)
fecha-revision: 2026-10-22
licencia: no identificada en la página (fichero LICENSE enlazado; tipo sin confirmar)
area: redes-seguridad
estado: investigado
cobertura: página del repositorio y README (caracteres 0-100000 de ~182000; el resto, incluida la sección «Dynamic or Static Code Analysis», NO se leyó). Ninguna herramienta listada se abrió, clonó ni ejecutó.
relacionadas: [IE-013, IE-014]
---
## Qué se examinó (rutas y símbolos)
- `README.md` (índice de secciones y las secciones de auditoría de código, fugas de secretos y vulnerabilidades de componentes). [README]
- En AURA: `walking-skeleton/quality-gate.sh` (ruff format/check, mypy, pytest, contratos), `walking-skeleton/pyproject.toml` (`[tool.ruff.lint] select = E,F,I,UP,B`), `entorno/scripts/requirements-stack.txt`, `aura_skeleton/nodo_agente.py:392-401`, `aura_skeleton/adapters/red_local.py:84-86`, `docs/libro-05-seguridad-y-confianza/5.1-modelo-amenazas.md` §Dependencias (L76). [CÓDIGO]

## Patrones relevantes
- Es un CATÁLOGO ordenado por categorías, no una librería; no hay API que adoptar. [README]
- Categorías aprovechables para AURA (solo defensivas): (a) análisis estático de código; (b) escaneo de secretos en repositorio/historial; (c) vulnerabilidades de dependencias y cadena de suministro (SCA); (d) **auditoría de skills/agentes/MCP/configuración de agentes** (sección «Security Auditing for Agent Skills», «AI Agent Runtime Controls»). [README]
- Herramientas nombradas por el catálogo en esas categorías (nombres tal como figuran; sin evaluar): secretos: truffleHog, credential-digger; SCA: grype, murphysec; agentes/skills: Cisco skill-scanner, SkillSpector, agentshield, Cisco mcp-scanner. [README]
- Resto del catálogo (smart contracts, móvil, binarios, subdominios, fuerza bruta, XSS, MITM, wireless, APT, etc.): ofensivo o fuera de alcance. NO se estudia ni se adopta. [INFER]

## Límites, riesgos y dependencias
- Lista de terceros sin garantía: cada herramienta tiene su propia licencia, mantenimiento y superficie. Ejecutar un escáner con acceso al repo y a `~/.claude` es dar lectura sobre secretos y memoria: debe probarse en copia exportada y sin red. [INFER]
- Varias herramientas de «agentes» usan LLM (nube) para analizar: incompatibles con D24 / local-first si reciben código privado. [INFER]
- Los escáneres de SCA suelen consultar bases de datos remotas de vulnerabilidades; en AURA solo sería aceptable con base descargada previamente y decisión del CEO. [INFER]
- Cobertura parcial de la lectura (ver cabecera): no se afirma nada sobre la sección de análisis estático dinámico/estático no leída.

## Comparación con AURA
Disponibilidad local comprobada con `command -v` (solo lectura, 2026-10-22):

| Herramienta | En HC-1 |
|---|---|
| ruff 0.15.22 | SÍ (`~/.local/bin/ruff`) |
| mypy | SÍ (`~/.local/bin/mypy`) |
| bandit, pip-audit, gitleaks, semgrep, detect-secrets, trufflehog, safety, osv-scanner, shellcheck, pylint, vulture | NO |

- Ya cubierto: formato, lint (`E,F,I,UP,B`) y tipado en `quality-gate.sh`; reglas de contratos/arquitectura en `tests/unit/test_manifiesto_arquitectura.py`. [CÓDIGO]
- Brecha 1 (secretos): el gate no tiene escaneo de secretos; la regla global lo exige antes de cada commit. Sin gitleaks/detect-secrets instalado; hoy depende de revisión humana/agente. [CÓDIGO][INFER]
- Brecha 2 (dependencias): `requirements-stack.txt` fija mínimos (`>=`) sin lockfile ni auditoría de vulnerabilidades; 5.1 §Dependencias remite a «3.4 cadena de suministro». No hay pip-audit/osv. [CÓDIGO]
- Brecha 3 (reglas de seguridad de código): `pyproject.toml` no activa el grupo `S` de ruff (equivalente a bandit). **Ya está disponible sin instalar nada.** Medición solo lectura (`ruff check --select S --no-cache aura_skeleton`): 17 avisos: S314 ×4 (`red_local.py:113,176,267,312`, parseo de XML de respuestas de dispositivos de la LAN), S310 ×3 (`home_assistant_real.py:116`, `providers_real.py:139,200`), S603/S607 (`microfono.py:68`, `voice_real.py:338-339`), S108 ×3, S110 ×3, S101 ×1. [EJEC]
- Triage preliminar [INFER], sin verificar caso a caso: S314 es el más relevante (XML no confiable; `xml.etree` no expande entidades externas por defecto pero sí es vulnerable a expansión de entidades anidadas; mitigación posible: límite de tamaño de respuesta o `defusedxml`, que sería dependencia nueva, a decidir). S310 aparece en destinos locales configurados; revisar que el esquema esté limitado a http/https.
- Agentes y skills de `.claude/agents/` y `~/.claude/skills`: no hay revisión automatizada; solo la regla de proceso `orquestacion-herramientas.md`. [CÓDIGO]

## Decisión
- **Descartar** el catálogo como dependencia. **Adaptar** su criterio de categorías: la brecha real y barata es activar el grupo `S` de ruff como medición informativa (sin romper el gate) y triar S314/S310. Secretos y SCA: **investigar más** (¿gitleaks/pip-audit en copia aislada, base de vulnerabilidades offline?) — requiere decisión del CEO por instalar software.
- Escáneres de skills/MCP (Cisco, etc.): no adoptar; solo referencia de qué riesgos mirar (instrucciones ocultas, permisos excesivos) para un checklist manual.

## Validación mínima
- [PROPUESTA] Candidata de mejora pequeña (única): test/ comprobación local `ruff check --select S` con línea base. Prueba: caso de control = inyectar en un fichero temporal una llamada que S-rules marcan y comprobar que se detecta; y que la línea base actual (17 avisos) está documentada o con `# noqa` justificado. Sin instalar nada; no se añade al gate hasta triar los avisos (rebajaría el gate a rojo hoy).

## Licencia y precauciones
- Licencia del catálogo sin confirmar; enlazar, no copiar texto. Las herramientas listadas no se ejecutan sobre datos de AURA sin copia exportada, sin red y con revisión previa de su código. Nada ofensivo se adopta.
