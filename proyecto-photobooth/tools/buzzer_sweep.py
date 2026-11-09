#!/usr/bin/env python3
"""Barrido de frecuencias del buzzer para encontrar la que suena MAS FUERTE (resonancia del piezo).
Uso en la Pi (con el servidor detenido):  python3 tools/buzzer_sweep.py
Escucha: el programa dice la frecuencia antes de cada tono. Anota la mas fuerte y ponla en fotobut/config.py
(TICK_HZ / SHUTTER_HZ). Ctrl+C para salir."""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fotobut.hal import PiHAL

hal = PiHAL()
freqs = list(range(1500, 5001, 250))
print("Barrido 1.5-5 kHz. Escucha cual suena mas fuerte.\n")
try:
    for f in freqs:
        print(f"{f:5d} Hz ...", end=" ", flush=True)
        hal.beep(f, 600); time.sleep(0.9); print("ok")
    print("\nRepite solo las candidatas (ej. 2500 3000 3500) o Enter para salir:")
    while True:
        r = input("> ").split()
        if not r: break
        for f in map(int, r):
            print(f, "Hz"); hal.beep(f, 700); time.sleep(1)
except KeyboardInterrupt:
    pass
