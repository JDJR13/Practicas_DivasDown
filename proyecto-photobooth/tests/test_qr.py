import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
try:
    import cv2                                   # OpenCV solo se usa para LEER los QR en esta prueba; la cabina no lo necesita
except ImportError:
    print("OMITIDA: falta OpenCV para decodificar (sudo apt install python3-opencv). La cabina no lo necesita.")
    sys.exit(0)
from fotobut.logica.qr import make_qr

def render(m, scale=8, quiet=4):
    n = len(m); a = np.full(((n + 2*quiet)*scale,)*2, 255, np.uint8)
    for y in range(n):
        for x in range(n):
            if m[y][x]:
                a[(y+quiet)*scale:(y+quiet+1)*scale, (x+quiet)*scale:(x+quiet+1)*scale] = 0
    return a

det = cv2.QRCodeDetector()
cases = ["a", "http://192.168.4.1:8080/s/0001-a3f9", "WIFI:T:WPA;S:Fotobut;P:fotobut2026;;",
         "Ñandú ✓ acentos", "x" * 60, "y" * 120, "z" * 180, "https://example.com/" + "q" * 200]
ok = 0
for t in cases:
    try:
        m = make_qr(t)
    except ValueError as e:
        print("skip", len(t), e); continue
    txt, _, _ = det.detectAndDecode(render(m))
    print("v%d" % ((len(m) - 17)//4), len(t), "OK" if txt == t else "FAIL: %r" % txt)
    ok += txt == t
print(ok, "decodificados")
