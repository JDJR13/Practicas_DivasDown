"""Caja negra y panel de mantenimiento (proceso 4). Uso: python3 tests/test_monitor.py"""
import sys, os, tempfile, time, json, threading, http.client, io, tarfile, subprocess, signal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FOTOBUT_TMP"] = tempfile.mkdtemp(); os.environ["FOTOBUT_FINAL"] = tempfile.mkdtemp(); os.environ["FOTOBUT_ESTADO"] = tempfile.mkdtemp()
from fotobut.servicios import config as C
from fotobut.procesos import monitor as M
from fotobut.servicios.caja_negra import CajaNegra

caja = CajaNegra()
# 1) caja negra: escribe, lee, tolera lineas cortadas por un apagon y purga lo viejo
caja.muestra({"cpu_c": 50.1, "estado": "READY"}); caja.evento("WARN", "prueba de evento", servicio="vision")
with open(caja._archivo(), "a") as f: f.write('{"t": 99999999999, "k": "m", "cpu_c": 5')      # linea a medias
caja._revisado = None                                      # como si el proceso arrancara de nuevo tras el apagon
caja.evento("INFO", "primer registro tras el corte")       # no debe perderse por la linea a medias
r = caja.leer(1); assert [x["k"] for x in r] == ["m", "e", "e"], r
assert caja.leer(1, "e")[0]["txt"] == "prueba de evento" and caja.ultimo()["txt"].startswith("primer registro")
viejo = caja.dir / "2001-01-01.jsonl"; viejo.write_text("{}\n"); caja.purgar(); assert not viejo.exists() and caja._archivo().exists()
assert oct(os.stat(caja._archivo()).st_mode & 0o777)

# 2) deteccion de eventos entre dos muestras
mon = M.Monitor(caja)
base = {"cpu_c": 50, "vision_ok": True, "qr_ok": True, "stm32": True, "enlace": True, "camara": True, "voltaje": 0, "disco_libre_mb": 9000,
        "sesiones": 2, "srv": {"vision": {"activo": "active", "sub": "running", "pid": 100, "reinicios": 0}}}
mon.prev = base
nueva = json.loads(json.dumps(base)); nueva["srv"]["vision"].update(pid=222, reinicios=1); nueva.update(stm32=False, cpu_c=80, voltaje=0x50005, sesiones=3)
mon._eventos(nueva)
txt = " | ".join(e["txt"] for e in caja.leer(1, "e"))
for esperado in ("fotobut-vision se reinicio", "STM32 dejo de mandar tramas", "temperatura del CPU 80", "bajo voltaje", "sesion terminada"):
    assert esperado in txt, (esperado, txt)
n0 = len(caja.leer(1, "e")); mon.prev = nueva; mon._eventos(nueva); assert len(caja.leer(1, "e")) == n0, "sin cambios no hay eventos"
caida = json.loads(json.dumps(nueva)); caida["vision_ok"] = False; caida["stm32"] = False
mon._eventos(caida); assert "vision_gui) dejo de responder" in caja.leer(1, "e")[-1]["txt"]

# 3) muestra real del sistema (en cualquier Linux) y arranque tras un "apagon"
m = mon.tick(); assert "ram_mb" in m and isinstance(m["vision_ok"], bool) and isinstance(m["srv"], dict)   # vision_ok es True si la cabina ya corre (en la Pi)
with open(caja._archivo(), "a") as f: f.write(json.dumps({"t": time.time() - 86400, "h": "ayer", "k": "m", "estado": "COUNTDOWN"}) + "\n")
caja2 = CajaNegra(); os.rename(caja._archivo(), caja._archivo().with_suffix(".bak"))
with open(caja2._archivo(), "w") as f: f.write(json.dumps({"t": time.time() - 86400, "h": "ayer 10:00", "k": "m", "estado": "COUNTDOWN"}) + "\n")
M.Monitor(caja2).arranque(); ev = caja2.leer(24 * 200, "e")
assert any("se reinicio o estuvo apagada" in e["txt"] and "COUNTDOWN" in e["txt"] for e in ev), ev

# 4) panel: solo local, Host exacto, POST solo con la cabecera propia
httpd = M.serve_panel(mon, "127.0.0.1", 19000); threading.Thread(target=httpd.serve_forever, daemon=True).start()
def req(method, path, headers=None, body=None):
    c = http.client.HTTPConnection("127.0.0.1", 19000, timeout=10); c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse(); b = r.read(); c.close(); return r.status, r, b
s, r, b = req("GET", "/"); assert s == 200 and b"mantenimiento" in b and r.getheader("X-Frame-Options") == "DENY"
s, r, b = req("GET", "/api/resumen"); d = json.loads(b); assert s == 200 and d["eventos"] and "muestra" in d
s, r, b = req("GET", "/", {"Host": "evil.example:19000"}); assert s == 403           # DNS rebinding
s, r, b = req("GET", "/", {"Host": "192.168.4.1:19000"}); assert s == 403
J = {"Content-Type": "application/json"}
s, r, b = req("POST", "/api/reiniciar", J, b'{"servicio":"vision"}'); assert s == 403             # sin cabecera propia (CSRF)
s, r, b = req("POST", "/api/reiniciar", {"X-Fotobut": "panel", "Content-Type": "text/plain"}, b'{"servicio":"vision"}'); assert s == 403
s, r, b = req("POST", "/api/reiniciar", {**J, "X-Fotobut": "panel"}, b'{"servicio":"; rm -rf /"}'); assert s == 409 and b"desconocido" in b
s, r, b = req("POST", "/api/reiniciar", {**J, "X-Fotobut": "panel"}, b"x" * 5000); assert s == 413
s, r, b = req("GET", "/api/registro?servicio=../../etc/passwd&n=99999999"); assert s == 200 and b"root:" not in b
s, r, b = req("GET", "/../../etc/passwd"); assert s == 404
s, r, b = req("GET", "/respaldo.tar.gz"); assert s == 200
nombres = tarfile.open(fileobj=io.BytesIO(b)).getnames()
assert any(n.startswith("respaldo/caja_negra/") for n in nombres) and "respaldo/journal.txt" in nombres and not any(n.endswith(".jpg") for n in nombres), nombres

# 5) reiniciar = SIGTERM al PID que reporta systemd (aqui se simula systemd con un proceso de prueba)
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
M.servicios = lambda: {"qr": {"activo": "active", "sub": "running", "pid": p.pid, "reinicios": 0}}
ok, msg = mon.reiniciar("qr"); assert ok, msg
assert p.wait(5) == -signal.SIGTERM
assert "pedido desde el panel" in caja.leer(1, "e")[-1]["txt"]
M.servicios = lambda: {}
ok, msg = mon.reiniciar("qr"); assert not ok
print("TODO OK")
