"""DetectorHardwareLocal: mide el equipo real (ADR-0021/0020) sin hardcodear ningun equipo.

Se usan `/proc` y `/dev/dri` FALSOS en `tmp_path` para controlar la entrada; solo una prueba mide el equipo
real. Cada prueba lleva su caso de control (que tendria que romperse para que falle).
"""

from __future__ import annotations

from pathlib import Path

from aura_skeleton import observability as obs
from aura_skeleton.adapters.detector_hardware import DetectorHardwareLocal

_FLAGS_HC1 = "fpu vme sse sse2 ssse3 sse4_1 sse4_2 popcnt aes"
_FLAGS_MAYOR = "fpu sse sse2 ssse3 sse4_1 sse4_2 popcnt avx avx2 fma aes"


def _meminfo(total_kb: int, disp_kb: int) -> str:
    return f"MemTotal:       {total_kb} kB\nMemFree:  100 kB\nMemAvailable:   {disp_kb} kB\nBuffers: 1 kB\n"


def _equipo(tmp_path: Path, *, flags: str, total_kb: int | None, disp_kb: int = 1000000, gpus: int = 0, dri=True):
    proc = tmp_path / "proc"
    proc.mkdir()
    if total_kb is not None:
        (proc / "meminfo").write_text(_meminfo(total_kb, disp_kb))
    (proc / "cpuinfo").write_text(
        f"processor\t: 0\nmodel name\t: X\nphysical id\t: 0\ncore id\t\t: 0\nflags\t\t: {flags}\n"
    )
    (proc / "asound").mkdir()
    (proc / "asound" / "cards").write_text(" 0 [PCH            ]: HDA-Intel - HDA Intel PCH\n                      x\n")
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "video0").write_text("")
    (tmp_path / "dev" / "videoX").write_text("")
    (tmp_path / "dev" / "null").write_text("")  # no es video: no debe contarse
    net = tmp_path / "net"
    net.mkdir()
    for nombre in ("lo", "eth0"):
        (net / nombre).mkdir()
    dri_dir = tmp_path / "dri"
    if dri:
        dri_dir.mkdir()
        for i in range(gpus):
            (dri_dir / f"renderD{128 + i}").write_text("")
        (dri_dir / "card0").write_text("")  # no es render: no debe contarse
    datos = tmp_path / "datos"
    datos.mkdir()
    return proc, dri_dir, datos


def _raices(proc) -> dict:
    """Raíces falsas de /dev y /sys/class/net creadas por `_equipo` junto a `proc`."""
    return {"raiz_dev": str(proc.parent / "dev"), "raiz_sys_net": str(proc.parent / "net")}


def _detector(tmp_path, proc, dri, datos, nucleos=2):
    return DetectorHardwareLocal(
        str(datos),
        raiz_proc=str(proc),
        raiz_dev_dri=str(dri),
        bits_proceso=lambda: 64,
        **_raices(proc),
        nucleos=lambda: nucleos,
        carga=lambda: (0.5, 0.4, 0.3),
    )


def test_equipo_tipo_hc1(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=3808516, gpus=1)
    r = _detector(tmp_path, proc, dri, datos, nucleos=2).detectar().recursos
    assert 3718 <= r["ram_mb"] <= 3720  # 3808516 // 1024 = 3719
    assert r["isa_avx2"] == 0.0 and r["isa_avx"] == 0.0 and r["isa_sse4_2"] == 1.0
    assert r["gpu_render"] == 1.0  # card0 NO cuenta
    assert r["nucleos"] == 2.0 and r["carga_1m"] == 0.5
    assert r["disco_libre_mb"] > 0


def test_equipo_mayor(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=16 * 1024 * 1024, disp_kb=8 * 1024 * 1024)
    r = _detector(tmp_path, proc, dri, datos, nucleos=8).detectar().recursos
    assert r["ram_mb"] == 16384.0 and r["ram_disponible_mb"] == 8192.0
    assert r["isa_avx2"] == 1.0 and r["isa_avx"] == 1.0 and r["isa_fma"] == 1.0
    assert r["isa_avx512f"] == 0.0 and r["gpu_render"] == 0.0 and r["nucleos"] == 8.0


def test_avx_no_casa_con_avx2(tmp_path):
    # Control: una coincidencia por subcadena daria isa_avx2=1 con solo "avx".
    proc, dri, datos = _equipo(tmp_path, flags="sse4_2 avx", total_kb=2048)
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert r["isa_avx"] == 1.0 and r["isa_avx2"] == 0.0
    # y al reves: "avx2" sin "avx" no activa isa_avx
    proc2 = tmp_path / "proc"
    (proc2 / "cpuinfo").write_text("flags : avx2\n")
    r2 = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert r2["isa_avx2"] == 1.0 and r2["isa_avx"] == 0.0


def test_sin_meminfo_omite_ram_y_el_resto_sigue(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=None, gpus=1)
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert "ram_mb" not in r and "ram_disponible_mb" not in r  # omitida NO es 0
    assert r["isa_avx2"] == 1.0 and r["gpu_render"] == 1.0 and r["nucleos"] == 2.0


def test_meminfo_con_formato_raro_omite_ram(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=1)
    (proc / "meminfo").write_text("MemTotal: basura kB\nMemAvailable: 12 kB\n")
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert "ram_mb" not in r
    assert r["ram_disponible_mb"] == 0.0  # 12 kB // 1024: la fuente sana se conserva


def test_sin_cpuinfo_omite_isa(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    (proc / "cpuinfo").unlink()
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert not [k for k in r if k.startswith("isa_")]
    assert r["ram_mb"] == 2.0


def test_dri_inexistente_da_cero_gpus(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048, dri=False)
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert r["gpu_render"] == 0.0  # medido: no hay GPU (a diferencia de una fuente ilegible)


def test_ruta_datos_inexistente_usa_el_padre(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    vistas: list[str] = []

    def disco(ruta):
        vistas.append(ruta)
        return type("U", (), {"free": 5 * 1024 * 1024 * 1024})()

    det = DetectorHardwareLocal(
        str(datos / "no" / "existe"), raiz_proc=str(proc), raiz_dev_dri=str(dri), disco=disco, **_raices(proc)
    )
    r = det.detectar().recursos
    assert vistas == [str(datos)]  # el ancestro existente mas cercano, no la ruta inexistente
    assert r["disco_libre_mb"] == 5120.0


def test_fallo_de_una_fuente_no_afecta_a_las_demas(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)

    def carga_rota():
        raise OSError("sin loadavg")

    det = DetectorHardwareLocal(
        str(datos), raiz_proc=str(proc), raiz_dev_dri=str(dri), carga=carga_rota, nucleos=lambda: None, **_raices(proc)
    )
    r = det.detectar().recursos
    assert "carga_1m" not in r and "nucleos" not in r
    assert r["ram_mb"] == 2.0


def test_deteccion_real_en_este_equipo(tmp_path):
    p = DetectorHardwareLocal(str(tmp_path)).detectar()
    assert p.recursos["ram_mb"] > 0
    assert p.recursos["nucleos"] >= 1
    assert all(isinstance(v, float) for v in p.recursos.values())
    assert p.pruebas == {}


_PERMITIDAS = frozenset(
    {
        "ram_mb",
        "ram_disponible_mb",
        "nucleos",
        "carga_1m",
        "disco_libre_mb",
        "gpu_render",
        "isa_sse4_2",
        "isa_ssse3",
        "cpu_64bit",
        "proceso_bits",
        "nucleos_fisicos",
        "video_dispositivos",
        "audio_tarjetas",
        "red_interfaces",
        "isa_avx",
        "isa_avx2",
        "isa_fma",
        "isa_avx512f",
    }
)


def test_perfil_solo_metricas_permitidas(tmp_path):
    # Control: una clave nueva (p. ej. `cpu_vendor`) sale del conjunto explicito y rompe la prueba.
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=2048, gpus=1)
    p = _detector(tmp_path, proc, dri, datos).detectar()
    assert set(p.recursos) == _PERMITIDAS  # las 18, ni una mas ni una menos
    assert all(type(v) is float for v in p.recursos.values())
    assert p.pruebas == {}
    assert "X" not in str(p.recursos)  # el "model name" del cpuinfo falso no se filtra


def test_varias_cpu_isa_solo_si_todas_la_tienen(tmp_path):
    # Control: leer solo la primera linea `flags` daria isa_avx2=1 con cpu0 primero (o 0 con cpu1... segun orden).
    for orden in (("avx", "avx avx2"), ("avx avx2", "avx")):
        base = tmp_path / orden[0].replace(" ", "_")
        base.mkdir()
        proc, dri, datos = _equipo(base, flags="x", total_kb=2048)
        (proc / "cpuinfo").write_text(
            f"processor : 0\nflags : sse4_2 {orden[0]}\n\nprocessor : 1\nflags : sse4_2 {orden[1]}\n"
        )
        r = _detector(tmp_path, proc, dri, datos).detectar().recursos
        assert r["isa_avx2"] == 0.0, orden
        assert r["isa_avx"] == 1.0 and r["isa_sse4_2"] == 1.0


def _avisos_detector(desde: int) -> list[str]:
    return [r["msg"] for r in obs._records[desde:] if r["level"] == "WARN" and r["module"] == "detector-hardware"]


def test_fuente_que_falla_deja_warn_sin_datos_y_las_demas_siguen(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=2048)

    def carga_rota():
        raise OSError("secreto-ruta-/etc/x")

    previos = len(obs._records)
    det = DetectorHardwareLocal(
        str(datos), raiz_proc=str(proc), raiz_dev_dri=str(dri), carga=carga_rota, **_raices(proc)
    )
    r = det.detectar().recursos
    avisos = _avisos_detector(previos)
    assert avisos == ["no se pudo medir carga_1m: OSError"]  # fuente + tipo; sin el texto de la excepcion
    assert r["ram_mb"] == 2.0 and r["isa_avx2"] == 1.0 and "carga_1m" not in r


def test_meminfo_ausente_deja_warn_por_cada_metrica_omitida(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=None)
    previos = len(obs._records)
    _detector(tmp_path, proc, dri, datos).detectar()
    avisos = _avisos_detector(previos)
    assert any("ram_mb" in a for a in avisos) and any("ram_disponible_mb" in a for a in avisos)


def test_sin_fallos_no_hay_warn(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=2048)
    previos = len(obs._records)
    _detector(tmp_path, proc, dri, datos).detectar()
    assert _avisos_detector(previos) == []  # control: el WARN no es ruido constante


def test_meminfo_sin_memtotal_omite_ram_mb_y_conserva_la_disponible(tmp_path):
    # Control (DH-M6): un codigo que ante la linea ausente devuelve 0.0 inventa `ram_mb=0.0`.
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=2048)
    (proc / "meminfo").write_text("MemAvailable:   1024000 kB\nBuffers: 1 kB\n")
    previos = len(obs._records)
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert "ram_mb" not in r
    assert r["ram_disponible_mb"] == 1000.0
    assert _avisos_detector(previos) == ["no se pudo medir ram_mb: ValueError"]


def test_cpuinfo_sin_linea_flags_no_inventa_isa(tmp_path):
    # Control (DH-M8): p. ej. ARM (`Features`, no `flags`). Devolver ISA a 0 afirmaria «sin AVX2» sin haberlo medido.
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=2048)
    (proc / "cpuinfo").write_text("processor : 0\nmodel name : x\nFeatures : fp asimd\n")
    previos = len(obs._records)
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert not [k for k in r if k.startswith("isa_")]
    assert r["ram_mb"] == 2.0 and r["nucleos"] == 2.0  # las demas fuentes siguen
    # Sin `flags` fallan las fuentes que dependen de ellas (isa, cpu_64bit) y la de ids (nucleos_fisicos).
    assert _avisos_detector(previos) == [
        "no se pudo medir isa: ValueError",
        "no se pudo medir cpu_64bit: ValueError",
        "no se pudo medir nucleos_fisicos: ValueError",
    ]
    assert "cpu_64bit" not in r


# ---------------------------------------------------------------- métricas de presencia (DP-NODO-01 §4.4)

_CPUINFO_ATOM_N450 = (
    "processor\t: 0\nvendor_id\t: GenuineIntel\nmodel name\t: Intel(R) Atom(TM) CPU N450   @ 1.66GHz\n"
    "physical id\t: 0\nsiblings\t: 2\ncore id\t\t: 0\ncpu cores\t: 1\n"
    "flags\t\t: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat clflush dts acpi mmx fxsr sse "
    "sse2 ss ht tm pbe syscall nx lm constant_tsc arch_perfmon pebs bts nopl cpuid aperfmperf pni dtes64 monitor "
    "ds_cpl est tm2 ssse3 cx16 xtpr pdcm movbe lahf_lm\n\n"
    "processor\t: 1\nvendor_id\t: GenuineIntel\nmodel name\t: Intel(R) Atom(TM) CPU N450   @ 1.66GHz\n"
    "physical id\t: 0\nsiblings\t: 2\ncore id\t\t: 0\ncpu cores\t: 1\n"
    "flags\t\t: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat clflush dts acpi mmx fxsr sse "
    "sse2 ss ht tm pbe syscall nx lm constant_tsc arch_perfmon pebs bts nopl cpuid aperfmperf pni dtes64 monitor "
    "ds_cpl est tm2 ssse3 cx16 xtpr pdcm movbe lahf_lm\n"
)


def _con_cpuinfo(tmp_path, texto, flags="sse4_2"):
    proc, dri, datos = _equipo(tmp_path, flags=flags, total_kb=2048)
    (proc / "cpuinfo").write_text(texto)
    return proc, dri, datos


def test_atom_n450_un_nucleo_fisico_con_dos_hilos(tmp_path):
    # Control: contar líneas `processor` daría 2 núcleos físicos; contar solo `core id` sueltos también.
    proc, dri, datos = _con_cpuinfo(tmp_path, _CPUINFO_ATOM_N450)
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert r["nucleos_fisicos"] == 1.0
    assert r["cpu_64bit"] == 1.0 and r["isa_ssse3"] == 1.0 and r["isa_sse4_2"] == 0.0


def test_nucleos_fisicos_cuenta_pares_distintos_socket_y_core(tmp_path):
    # Control: contar solo `core id` distintos daría 2 (0 y 1); el par con `physical id` da 4.
    texto = "".join(
        f"processor : {i}\nphysical id : {sock}\ncore id : {core}\nflags : lm\n\n"
        for i, (sock, core) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1), (1, 1)])
    )
    proc, dri, datos = _con_cpuinfo(tmp_path, texto)
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["nucleos_fisicos"] == 4.0


def test_sin_physical_ni_core_id_se_omite_nucleos_fisicos_y_las_demas_siguen(tmp_path):
    proc, dri, datos = _con_cpuinfo(tmp_path, "processor : 0\nflags : lm ssse3\n")
    previos = len(obs._records)
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert "nucleos_fisicos" not in r  # omitida, no inventada (ni 1.0 ni 0.0)
    assert r["cpu_64bit"] == 1.0 and r["isa_ssse3"] == 1.0
    assert _avisos_detector(previos) == ["no se pudo medir nucleos_fisicos: ValueError"]


def test_solo_physical_id_sin_core_id_no_cuenta(tmp_path):
    proc, dri, datos = _con_cpuinfo(tmp_path, "processor : 0\nphysical id : 0\nflags : lm\n")
    assert "nucleos_fisicos" not in _detector(tmp_path, proc, dri, datos).detectar().recursos


def test_cpu_64bit_exige_lm_en_todas_las_lineas_flags(tmp_path):
    # Control: leer solo una línea (o por subcadena: `lahf_lm` contiene «lm») daría 1.0 donde no procede.
    proc, dri, datos = _con_cpuinfo(tmp_path, "processor : 0\nflags : lm sse\n\nprocessor : 1\nflags : sse lahf_lm\n")
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["cpu_64bit"] == 0.0
    (proc / "cpuinfo").write_text("processor : 0\nflags : lm sse\n\nprocessor : 1\nflags : sse lm\n")
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["cpu_64bit"] == 1.0


def test_lahf_lm_en_todos_los_nucleos_no_equivale_a_lm(tmp_path):
    # Control (DH-M18): `lahf_lm` presente en TODAS las líneas y `lm` en ninguna; la comparación por subcadena daría 1.0.
    proc, dri, datos = _con_cpuinfo(
        tmp_path, "processor : 0\nflags : sse lahf_lm\n\nprocessor : 1\nflags : sse lahf_lm\n"
    )
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["cpu_64bit"] == 0.0


def test_cpu_64bit_cero_en_cpu_de_32_bits_y_ssse3_exacto(tmp_path):
    proc, dri, datos = _con_cpuinfo(tmp_path, "processor : 0\nflags : sse2 sse3 pae\n")
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert r["cpu_64bit"] == 0.0 and r["isa_ssse3"] == 0.0  # `sse3` NO es `ssse3`


def test_sin_flags_se_omite_cpu_64bit(tmp_path):
    proc, dri, datos = _con_cpuinfo(tmp_path, "processor : 0\nFeatures : fp\n")
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert "cpu_64bit" not in r and "isa_ssse3" not in r


def test_proceso_bits_inyectable_y_real(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    for bits in (32, 64):
        det = DetectorHardwareLocal(
            str(datos), raiz_proc=str(proc), raiz_dev_dri=str(dri), bits_proceso=lambda b=bits: b, **_raices(proc)
        )
        assert det.detectar().recursos["proceso_bits"] == float(bits)
    real = DetectorHardwareLocal(str(datos), raiz_proc=str(proc), raiz_dev_dri=str(dri), **_raices(proc))
    assert real.detectar().recursos["proceso_bits"] in (32.0, 64.0)


def test_proceso_bits_que_falla_se_omite(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)

    def rota():
        raise OSError("x")

    det = DetectorHardwareLocal(
        str(datos), raiz_proc=str(proc), raiz_dev_dri=str(dri), bits_proceso=rota, **_raices(proc)
    )
    assert "proceso_bits" not in det.detectar().recursos


def test_video_dispositivos_cuenta_solo_entradas_video(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["video_dispositivos"] == 2.0  # no `null`
    for e in (tmp_path / "dev").glob("video*"):
        e.unlink()
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["video_dispositivos"] == 0.0  # medido: ninguno


def test_dev_ausente_omite_video(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    det = DetectorHardwareLocal(
        str(datos), raiz_proc=str(proc), raiz_dev_dri=str(dri), **{**_raices(proc), "raiz_dev": str(tmp_path / "nada")}
    )
    assert "video_dispositivos" not in det.detectar().recursos


def test_audio_tarjetas_cuenta_solo_lineas_de_tarjeta(tmp_path):
    # Control: contar líneas del fichero daría 4; solo casan `^\s*\d+\s+\[`.
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    (proc / "asound" / "cards").write_text(
        " 0 [PCH            ]: HDA-Intel - HDA Intel PCH\n                      HDA Intel PCH at 0x1\n"
        " 1 [U0x46d0x825    ]: USB-Audio - USB Device\n                      Mic\n"
    )
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["audio_tarjetas"] == 2.0


def test_audio_fichero_existente_sin_tarjetas_es_cero(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    (proc / "asound" / "cards").write_text("--- no soundcards ---\n")
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["audio_tarjetas"] == 0.0


def test_audio_fichero_ausente_se_omite_con_warn(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    (proc / "asound" / "cards").unlink()
    previos = len(obs._records)
    r = _detector(tmp_path, proc, dri, datos).detectar().recursos
    assert "audio_tarjetas" not in r  # omitida NO es 0
    assert _avisos_detector(previos) == ["no se pudo medir audio_tarjetas: FileNotFoundError"]


def test_red_interfaces_excluye_loopback(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["red_interfaces"] == 1.0  # eth0, no lo
    (tmp_path / "net" / "wlan0").mkdir()
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["red_interfaces"] == 2.0
    for e in ("eth0", "wlan0"):
        (tmp_path / "net" / e).rmdir()
    assert _detector(tmp_path, proc, dri, datos).detectar().recursos["red_interfaces"] == 0.0


def test_sys_net_ausente_omite_red(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_HC1, total_kb=2048)
    det = DetectorHardwareLocal(
        str(datos),
        raiz_proc=str(proc),
        raiz_dev_dri=str(dri),
        **{**_raices(proc), "raiz_sys_net": str(tmp_path / "nada")},
    )
    assert "red_interfaces" not in det.detectar().recursos


def test_detectar_con_omisiones_devuelve_perfil_y_nombres_de_fuentes_fallidas(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=None)
    (proc / "asound" / "cards").unlink()
    perfil, omitidas = _detector(tmp_path, proc, dri, datos).detectar_con_omisiones()
    assert omitidas == ("ram_mb", "ram_disponible_mb", "audio_tarjetas")
    assert "ram_mb" not in perfil.recursos and perfil.recursos["isa_avx2"] == 1.0


def test_detectar_con_omisiones_sin_fallos_es_vacio_y_detectar_coincide(tmp_path):
    proc, dri, datos = _equipo(tmp_path, flags=_FLAGS_MAYOR, total_kb=2048)
    det = _detector(tmp_path, proc, dri, datos)
    perfil, omitidas = det.detectar_con_omisiones()
    assert omitidas == ()
    assert det.detectar() == perfil  # `detectar` delega en `detectar_con_omisiones`


def test_deteccion_real_incluye_proceso_bits(tmp_path):
    r = DetectorHardwareLocal(str(tmp_path)).detectar().recursos
    assert r["proceso_bits"] in (32.0, 64.0)
