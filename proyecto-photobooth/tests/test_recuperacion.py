"""Punto de control y recuperacion (clase 22): que pasa si vision_gui muere a media sesion o con la tira en pantalla,
y el vigia (watchdog). Uso: python3 tests/test_recuperacion.py"""
import sys, os, tempfile, time, json, socket, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FOTOBUT_TMP"] = tempfile.mkdtemp(); os.environ["FOTOBUT_FINAL"] = tempfile.mkdtemp()
from fotobut.servicios import config as C
from fotobut.hardware.hal import SimHAL
from fotobut.hardware.camera import SimCamera
from fotobut.logica.machine import Machine

class Clk:
    t = 1000.0
    def __call__(self): return self.t

def nueva():
    clk = Clk(); hal = SimHAL(); return Machine(hal, SimCamera(), clk), hal, clk

def hasta(m, hal, clk, estado, lim=900):
    for _ in range(lim):
        clk.t += .05; hal._last_sample = -1
        hal.sim_set(button=m.state in ("ATTRACT", "READY", "SLEEP"))
        m.step()
        if m.state == "PROCESSING":
            t0 = time.time()
            while not m._strip_ready and time.time() - t0 < 15: time.sleep(0.02)
        if m.state == estado: return
    raise AssertionError(f"no llego a {estado}: {m.state}")

ck = lambda: json.loads((C.FINAL_DIR / "estado.json").read_text())

# 1) el contador sobrevive al reinicio y la sesion a medias se descarta (el "proceso" muere en plena cuenta regresiva)
m, hal, clk = nueva(); hasta(m, hal, clk, "COUNTDOWN")
sid1 = m.sid; assert ck()["contador"] == 1 and ck()["estado"] == "COUNTDOWN" and ck()["sid"] == sid1
m2, hal2, clk2 = nueva()                                   # arranque nuevo, como despues de kill -9 o de un corte de luz
assert m2.state == "ATTRACT" and m2.sid is None and m2._counter == 1
assert ck()["sid"] is None, "la sesion interrumpida debe quedar descartada en el punto de control"
hasta(m2, hal2, clk2, "RESULT")
assert m2.sid.startswith("0002-") and ck()["estado"] == "RESULT" and ck()["hechas"] == 1
sid2, url2 = m2.sid, m2.share_url

# 2) el proceso muere con la tira en pantalla: al volver se restaura el resultado con su QR
m3, hal3, clk3 = nueva()
assert m3.state == "RESULT" and m3.sid == sid2 and m3.strip_url == f"/strip/{sid2}.jpg" and m3.qr_url and m3.share_url == url2
assert len(m3.photos) == 3 and m3.sessions_done == 1 and m3._counter == 2
snap = m3.snapshot(); assert snap["state"] == "RESULT" and snap["age_ms"] >= 0
hal3.sim_set(button=True); clk3.t += .05; m3.step(); assert m3.state == "READY"      # y la cabina sigue normal
hasta(m3, hal3, clk3, "RESULT"); assert m3.sid.startswith("0003-")

# 3) si ya paso el tiempo de la pantalla de resultado, no se restaura
d = ck(); d["t"] = time.time() - C.RESULT_TIMEOUT_S - 5; (C.FINAL_DIR / "estado.json").write_text(json.dumps(d))
m4, _, _ = nueva(); assert m4.state == "ATTRACT" and m4._counter == 3

# 4) punto de control corrupto o truncado: se arranca limpio, sin excepciones
for basura in ("", "{", "[1,2]", '{"contador": "x", "sid": 5, "estado": "RESULT"}', "\x00\xff" * 50):
    (C.FINAL_DIR / "estado.json").write_text(basura, errors="ignore")
    m5, _, _ = nueva(); assert m5.state == "ATTRACT", basura
# 5) instalacion anterior (solo contador.txt): se respeta
os.remove(C.FINAL_DIR / "estado.json"); (C.FINAL_DIR / "contador.txt").write_text("41")
m6, hal6, clk6 = nueva(); assert m6._counter == 41
hasta(m6, hal6, clk6, "COUNTDOWN"); assert m6.sid.startswith("0042-")
# 6) la escritura es atomica: no quedan temporales
assert not (C.FINAL_DIR / "estado.tmp").exists()
print("punto de control y recuperacion OK")

# 7) vigia: manda READY y WATCHDOG mientras las pruebas pasan, y calla cuando un hilo se cuelga
from fotobut.servicios import vigia
path = os.path.join(tempfile.mkdtemp(), "notify.sock")
srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM); srv.bind(path); srv.settimeout(3)
os.environ["NOTIFY_SOCKET"] = path; os.environ["WATCHDOG_USEC"] = "400000"
lat = vigia.Latido()
v = vigia.Vigia("prueba", {"hilo": lambda: lat.edad() < 0.5}, gracia_s=0); v.periodo = 0.1
assert v.activo; v.start()
got = [srv.recv(64) for _ in range(3)]
assert got[0] == b"READY=1" and got[1] == b"WATCHDOG=1", got
time.sleep(0.8)                                            # el "hilo" deja de dar senales de vida
while True:                                                # se vacia lo pendiente
    try: srv.settimeout(0.05); last = srv.recv(64)
    except socket.timeout: break
srv.settimeout(0.6)
try:
    extra = srv.recv(64); assert extra.startswith(b"STATUS=") or False, extra
except socket.timeout:
    pass
try:
    x = srv.recv(64); raise AssertionError(f"no debe avisar con un hilo colgado: {x}")
except socket.timeout:
    pass
assert v.fallo == "hilo"
lat.toc(); srv.settimeout(2)
threading.Thread(target=lambda: [lat.toc() or time.sleep(0.1) for _ in range(15)], daemon=True).start()
assert srv.recv(64) == b"WATCHDOG=1"                        # se recupera: vuelve a avisar
del os.environ["NOTIFY_SOCKET"]; assert vigia.notificar("WATCHDOG=1") is False   # sin systemd no hace nada
print("vigia (watchdog) OK")
print("TODO OK")
