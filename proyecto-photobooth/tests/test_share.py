"""Servidor de descarga (8080): paginas, descargas, seguridad de rutas. Uso: python3 tests/test_share.py [carpeta_capturas]"""
import sys, os, tempfile, threading, time, urllib.request, urllib.error, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FOTOBUT_TMP"] = tempfile.mkdtemp(); os.environ["FOTOBUT_FINAL"] = tempfile.mkdtemp()
from fotobut.servicios import config as C
from fotobut.hardware.hal import SimHAL
from fotobut.hardware.camera import SimCamera
from fotobut.logica.machine import Machine
from fotobut.comunicacion.share import serve_share

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
s, h, b = get(f"/dl/strip/{sid}.jpg"); assert s == 200 and "attachment" in h["Content-Disposition"] and sid[:4] in h["Content-Disposition"] and sid not in h["Content-Disposition"]
for i in (1, 2, 3):
    s, h, b = get(f"/dl/photo/{sid}/{i}.jpg"); assert s == 200 and b[:2] == b"\xff\xd8", i
s, h, b = get("/f/Poppins-Bold.ttf"); assert s == 200 and len(b) > 10000
s, h, b = get("/"); assert s == 200 and b"Descargar" not in b and sid.encode() not in b   # sin QR no se ve la tira de nadie
s, h, b = get("/salud"); assert s == 200 and b == b"ok"
# cabeceras de seguridad y sin version del servidor
s, h, b = get(f"/s/{sid}")
assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY" and "default-src 'none'" in h["Content-Security-Policy"]
assert "Python" not in h["Server"] and "BaseHTTP" not in h["Server"], h["Server"]
# seguridad: nada fuera de las rutas permitidas (ni con el formato de id anterior, de 32 bits)
for bad in ["/api/state", "/events", "/static/app.js", f"/s/../{sid}", "/s/0001-zzzzzzzzzzzzzzzz", "/strip/../../etc/passwd",
            f"/photo/{sid}/4.jpg", f"/photo/{sid}/..%2f..%2fetc%2fpasswd", "/f/..%2f..%2frun.py", "/f/run.py",
            "/dl/strip/9999-0000000000000000.jpg", "/s/0001-0000abcd", "/estado.json", "/sesiones.log", "/s/" + sid + "/"]:
    s, h, b = get(bad); assert s == 404, (bad, s)
s, h, b = get("/s/" + "a" * 300); assert s == 414, s
# solo GET y HEAD
import http.client
def raw(method, path, ip_port=("127.0.0.1", 18080)):
    c = http.client.HTTPConnection(*ip_port, timeout=5); c.request(method, path); r = c.getresponse(); body = r.read(); c.close(); return r.status, body
for mth in ("POST", "PUT", "DELETE", "OPTIONS", "TRACE"):
    assert raw(mth, f"/s/{sid}")[0] == 405, mth
st, body = raw("HEAD", f"/strip/{sid}.jpg"); assert st == 200 and body == b""
# un enlace simbolico plantado en /tmp no saca archivos de fuera
evil = C.TMP_DIR / "0666-00000000deadbeef"; evil.mkdir(); os.symlink("/etc/passwd", evil / "tira.jpg")
s, h, b = get("/strip/0666-00000000deadbeef.jpg"); assert s == 404 and b"root:" not in b, s
import shutil; shutil.rmtree(evil)
# limites por IP (con reloj falso y una IP que no es local)
from fotobut.comunicacion import share as S
class T:
    t = 0.0
    def __call__(self): return self.t
tk = T(); L = S.Limites(tk)
assert all(L.permitir("10.0.0.5") for _ in range(S.RATE_N)) and not L.permitir("10.0.0.5")       # rafaga: se corta
assert L.permitir("10.0.0.6")                                                                    # otra IP no se afecta
tk.t += S.RATE_S + 1; assert L.permitir("10.0.0.5")                                              # ventana nueva
for _ in range(S.MISS_N): L.fallo("10.0.0.7")
assert not L.permitir("10.0.0.7"); tk.t += S.BAN_S + 1; assert L.permitir("10.0.0.7")            # bloqueo temporal por escaneo
assert all(L.abrir("10.0.0.8") for _ in range(S.MAX_CONN_IP)) and not L.abrir("10.0.0.8")        # conexiones por IP
for _ in range(S.MAX_CONN_IP): L.cerrar("10.0.0.8")
assert L.total == 0 and "10.0.0.8" not in L.conn
for k in range(2000): L.permitir(f"10.1.{k // 250}.{k % 250}"); L.fallo(f"10.1.{k // 250}.{k % 250}")
assert len(L.req) <= S.Limites.MAX_IPS + 1 and len(L.miss) <= S.Limites.MAX_IPS + 1              # memoria acotada
# slowloris: 80 conexiones que no mandan nada; el servidor sigue atendiendo y las suelta solo
import socket
socks = []
for _ in range(80):
    try:
        c = socket.create_connection(("127.0.0.1", 18080), timeout=2); c.send(b"GET /s/"); socks.append(c)
    except OSError:
        pass
time.sleep(0.3)
assert httpd.lim.total <= S.MAX_CONN, httpd.lim.total
for c in socks[:40]: c.close()
time.sleep(0.5)
s, h, b = get("/salud"); assert s == 200, "el servidor debe seguir vivo durante el ataque"
for c in socks: c.close()
t0 = time.time()
while httpd.lim.total > 0 and time.time() - t0 < 12: time.sleep(0.2)
assert httpd.lim.total == 0, httpd.lim.total
# la tira sigue disponible desde la microSD aunque se borre /tmp
shutil.rmtree(C.TMP_DIR / sid)
s, h, b = get(f"/strip/{sid}.jpg"); assert s == 200, s
# ...pero caduca: pasado SHARE_TTL_S el enlace deja de servir
old = time.time() - C.SHARE_TTL_S - 60; os.utime(C.FINAL_DIR / f"{sid}.jpg", (old, old))
s, h, b = get(f"/strip/{sid}.jpg"); assert s == 404, s
# limpieza de /tmp
for k in range(C.MAX_TMP_SESSIONS + 5):
    d = C.TMP_DIR / f"{9000+k:04d}-{k:016x}"; d.mkdir(); os.utime(d, (k + 1, k + 1))
m._prune(); left = [d for d in C.TMP_DIR.iterdir() if d.is_dir()]; assert len(left) <= C.MAX_TMP_SESSIONS, len(left)
print("TODO OK")
