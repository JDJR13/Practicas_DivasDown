#!/usr/bin/env python3
"""Imprime archivo:linea de cada decision de la bitacora marcada en el codigo con una etiqueta [C8-..] [C9-..] [C10-..] [C11-..] [C20-..] [C21-..].
Uso:   python3 tools/mapa_bitacora.py          (desde la carpeta del proyecto)       --md   salida en tabla Markdown"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [p for pat in ("fotobut/*.py", "run.py", "systemd/*.service", "firmware_stm32/src/*.c") for p in ROOT.glob(pat)]
TAG = re.compile(r"\[(C(?:8|9|10|11|20|21)[-\w]*)\]")
found = []
for p in sorted(FILES):
    for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
        for t in TAG.findall(line):
            found.append((t, str(p.relative_to(ROOT)), n, line.strip()[:90]))
found.sort(key=lambda x: (int(re.match(r"C(\d+)", x[0]).group(1)), x[0], x[1], x[2]))
if "--md" in sys.argv:
    print("| Etiqueta | Archivo:linea | Codigo |\n|---|---|---|")
for t, f, n, code in found:
    print(f"| {t} | {f}:{n} | `{code}` |" if "--md" in sys.argv else f"{t:18s} {f}:{n:<4d} {code}")
