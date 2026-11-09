"""Servidor de descarga (8080): paginas, descargas, seguridad de rutas. Uso: python3 tests/test_share.py [carpeta_capturas]"""
import sys, os, tempfile, threading, time, urllib.request, urllib.error, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FOTOBUT_TMP"] = tempfile.mkdtemp(); os.environ["FOTOBUT_FINAL"] = tempfile.mkdtemp()
from fotobut import config as C
from fotobut.hal import SimHAL
from fotobut.camera import SimCamera
from fotobut.machine import Machine
from fotobut.share import serve_share

class Clk:
    t = 1000.0
    def __call__(self): return self.t
clk = Clk(); hal = SimHAL(); m = Machine(hal, SimCamera(), clk)
for _ in range(400):
    clk.t += .05; hal._last_sample = -1
    if m.state == "ATTRACT": hal.sim_set(button=True)
    elif m.state == "READY": hal.sim_set(button=True)
    else: hal.sim_set(button=False)
    m.step()
    if m.state == "PROCESSING":
        t0 = time.time()
        while not m._strip_ready and time.time() - t0 < 15: time.sleep(0.02)
    if m.state == "RESULT": break
assert m.state == "RESULT", m.state
httpd = serve_share("127.0.0.1", 18080); threading.Thread(target=httpd.serve_forever, daemon=True).start()
B = "http://127.0.0.1:18080"
def get(p):
    try:
        r = urllib.request.urlopen(B + p); return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e: return e.code, e.headers, e.read()
sid = m.sid
s, h, b = get(f"/s/{sid}"); assert s == 200 and b"Descargar tira" in b and b"Descargar foto 3" in b
s, h, b = get(f"/strip/{sid}.jpg"); assert s == 200 and b[:2] == b"\xff\xd8" and "attachment" not in h.get("Content-Disposition", "")
s, h, b = get(f"/dl/strip/{sid}.jpg"); assert s == 200 and "attachment" in h["Content-Disposition"] and sid in h["Content-Disposition"]
for i in (1, 2, 3):
    s, h, b = get(f"/dl/photo/{sid}/{i}.jpg"); assert s == 200 and b[:2] == b"\xff\xd8", i
s, h, b = get("/f/Poppins-Bold.ttf"); assert s == 200 and len(b) > 10000
s, h, b = get("/"); assert s == 200 and b"Descargar tira" in b            # redirige a la ultima tira
# seguridad: nada fuera de las rutas permitidas
for bad in ["/api/state", "/events", "/static/app.js", f"/s/../{sid}", "/s/0001-zzzzzzzz", "/strip/../../etc/passwd",
            f"/photo/{sid}/4.jpg", f"/photo/{sid}/..%2f..%2fetc%2fpasswd", "/f/..%2f..%2frun.py", "/f/run.py", "/dl/strip/9999-00000000.jpg"]:
    s, h, b = get(bad); assert s == 404, (bad, s)
# la tira sigue disponible desde la microSD aunque se borre /tmp
import shutil; shutil.rmtree(C.TMP_DIR / sid)
s, h, b = get(f"/strip/{sid}.jpg"); assert s == 200, s
# limpieza de /tmp
for k in range(C.MAX_TMP_SESSIONS + 5):
    d = C.TMP_DIR / f"{9000+k:04d}-{k:08x}"; d.mkdir(); os.utime(d, (k + 1, k + 1))
m._prune(); left = [d for d in C.TMP_DIR.iterdir() if d.is_dir()]; assert len(left) <= C.MAX_TMP_SESSIONS, len(left)
print("TODO OK")
if len(sys.argv) > 1:   # captura movil de la pagina (requiere una sesion viva): se regenera una tira
    pass
