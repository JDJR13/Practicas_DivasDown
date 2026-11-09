#!/usr/bin/env python3
"""Precision del HC-SR04 + STM32 (Avance 3, pendiente de Avance 1: error <= +-2 cm en 30-120 cm).

Uso (con fotobut-control detenido, porque ese servicio tiene abierto /dev/ttyAMA0):
    python3 tools/medir_distancia.py 10 30 60 100
Para cada distancia real (en cm, medida con regla desde la cara del sensor) pide colocar el objeto,
lee las tramas 'DIST:xx cm' durante 3 s y muestra minimo / mediana / maximo y el error de la mediana.
"""
import re
import statistics
import sys
import time

import serial

PORT, BAUD, SEG = "/dev/ttyAMA0", 115200, 3.0
TOL_CM = 2


def leer(ser, seg):
    ser.reset_input_buffer()
    fin, buf, vals, err = time.monotonic() + seg, b"", [], 0
    while time.monotonic() < fin:
        buf += ser.read(64)
        while b"\n" in buf:
            lin, buf = buf.split(b"\n", 1)
            m = re.match(rb"DIST:(\d+) cm", lin.strip())
            if m:
                vals.append(int(m.group(1)))
            elif lin.strip().startswith(b"DIST:ERR"):
                err += 1
    return vals, err


def main():
    reales = [int(x) for x in sys.argv[1:]] or [10, 30, 60, 100]
    ser = serial.Serial(PORT, BAUD, timeout=0.2)
    filas = []
    for d in reales:
        input(f"\nPon el objeto plano a {d} cm de la cara del sensor y presiona Enter... ")
        time.sleep(0.5)
        vals, err = leer(ser, SEG)
        if not vals:
            filas.append((d, None, None, None, len(vals), err))
            print(f"  real {d} cm: sin lecturas validas ({err} DIST:ERR)")
            continue
        med = statistics.median(vals)
        filas.append((d, min(vals), med, max(vals), len(vals), err))
        print(f"  real {d} cm: {len(vals)} lecturas, min {min(vals)}, mediana {med:g}, max {max(vals)}, ERR {err}")
    print("\n=== Precision de la distancia (HC-SR04 + STM32, UART 115200) ===")
    print(f"{'real(cm)':>9} {'min':>5} {'mediana':>8} {'max':>5} {'n':>4} {'ERR':>4} {'error(cm)':>10}  resultado")
    for d, mn, med, mx, n, err in filas:
        if med is None:
            print(f"{d:>9} {'-':>5} {'-':>8} {'-':>5} {n:>4} {err:>4} {'-':>10}  SIN DATO")
            continue
        e = med - d
        print(f"{d:>9} {mn:>5} {med:>8g} {mx:>5} {n:>4} {err:>4} {e:>+10g}  {'CUMPLE' if abs(e) <= TOL_CM else 'NO CUMPLE'} (+-{TOL_CM} cm)")


if __name__ == "__main__":
    main()
