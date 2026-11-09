#!/usr/bin/env python3
"""Resume las lineas MEDICION de los 3 procesos y las compara con los valores comprometidos en el Avance 1.
Uso en la Pi:   python3 tools/resumen_mediciones.py            (lee el journal de systemd del arranque actual)
                python3 tools/resumen_mediciones.py archivo.log (o un log de run.py)
Haz antes 8-10 sesiones completas con el boton fisico."""
import re, statistics, subprocess, sys

if len(sys.argv) > 1:
    text = open(sys.argv[1], errors="replace").read()
else:
    try:
        text = subprocess.run(["journalctl", "-b", "--no-pager", "-o", "cat", "-u", "fotobut-control", "-u", "fotobut-vision"],
                              capture_output=True, text=True).stdout
    except FileNotFoundError:
        text = ""
    if "MEDICION" not in text:
        text = open("/tmp/fotobut.log", errors="replace").read() if len(sys.argv) < 2 else text

def vals(pat):
    return [float(x) for x in re.findall(pat, text)]

rows = [
    # nombre, muestras, requisito (texto), funcion de cumplimiento
    ("Intervalo de cuenta regresiva (error)", [abs(v) for v in vals(r"cuenta_regresiva intervalo_ms=[\d.]+ error_ms=([+-][\d.]+)")], "|error| <= 10 ms", lambda m: m <= 10, "ms"),
    ("Latencia boton -> inicio del tono (tras antirrebote)", vals(r"latencia_boton_tono ms=([\d.]+)"), "<= 15 ms", lambda m: m <= 15, "ms"),
    ("Latencia boton -> tono contando el antirrebote", vals(r"desde_flanco_ms=([\d.]+)"), "(informativo)", None, "ms"),
    ("3a captura -> QR en pantalla", vals(r"captura3_a_QR_ms=([\d.]+)"), "<= 2500 ms", lambda m: m <= 2500, "ms"),
    ("Compositor (collage + JPEG + fsync)", vals(r"compositor_ms=([\d.]+)"), "plan C4 = 680 ms", lambda m: m <= 2500, "ms"),
]
print(f"{'Medicion':56s} {'n':>3s} {'min':>9s} {'media':>9s} {'max':>9s}  {'requisito':18s} resultado")
for name, v, req, ok, unit in rows:
    if not v:
        print(f"{name:56s}   0   (sin datos)")
        continue
    res = "" if ok is None else ("CUMPLE" if ok(max(v)) else "NO CUMPLE")
    print(f"{name:56s} {len(v):3d} {min(v):9.2f} {statistics.mean(v):9.2f} {max(v):9.2f}  {req:18s} {res}")
