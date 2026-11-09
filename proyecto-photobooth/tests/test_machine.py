import sys, os, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FOTOBUT_TMP"] = tempfile.mkdtemp(); os.environ["FOTOBUT_FINAL"] = tempfile.mkdtemp()
from fotobut import config as C
from fotobut.hal import SimHAL
from fotobut.camera import SimCamera
from fotobut.machine import Machine, pot_to_filter

class Clk:
    t = 1000.0
    def __call__(self): return self.t

clk = Clk(); hal = SimHAL(); m = Machine(hal, SimCamera(), clk)

def run(sec, dt=0.05):
    for _ in range(int(sec / dt)):
        clk.t += dt
        hal._last_sample = -1          # una muestra de distancia por paso (equivale a 10 Hz con dt=.1)
        m.step()

def wait_strip():
    t0 = time.time()
    while not m._strip_ready and time.time() - t0 < 15: time.sleep(0.02)
    assert m._strip_ready, "el compositor no termino la tira"

# 1) boton despierta ATTRACT -> READY
assert m.state == "ATTRACT"; hal.sim_set(button=True); run(0.2); assert m.state == "READY", m.state
# 2) presencia: 5 muestras seguidas despiertan desde ATTRACT
m._go("ATTRACT"); m.consec = 0; hal.sim_set(distance=80); run(0.1); assert m.state == "ATTRACT"
run(0.6); assert m.state == "READY", m.state
# 3) lectura espuria resetea el conteo
m._go("ATTRACT"); m.consec = 0; hal.sim_set(distance=80); run(0.15); hal.sim_set(distance=300); run(0.1)
assert m.consec == 0 and m.state == "ATTRACT"
hal.sim_set(distance=None)
# 4) potenciometro -> filtros e histeresis
assert pot_to_filter(0, None) == 0 and pot_to_filter(1023, None) == 4
assert pot_to_filter(210, 0) == 0 and pot_to_filter(240, 0) == 1     # limite 204.8 + 15% de histeresis (~236)
m._go("READY"); hal.sim_set(pot=450); run(0.6); assert m.filter_idx == 2, m.filter_idx
# 5) sesion completa
hal.sim_set(button=True); run(0.1); assert m.state == "COUNTDOWN" and m.shot == 1
seen = []
for _ in range(900):
    clk.t += 0.05; hal._last_sample = -1; m.step()
    if not seen or seen[-1] != (m.state, m.shot): seen.append((m.state, m.shot))
    if m.state == "PROCESSING": wait_strip()
    if m.state == "RESULT": break
print(seen)
assert m.state == "RESULT" and len(m.photos) == 3 and m.strip_url and m.qr_url
# sin punto de acceso (sandbox / Pi sin AP): solo el QR de la URL; con AP: tambien el de Wi-Fi
assert m.ap_active == (m.qr_wifi is not None), (m.ap_active, m.qr_wifi)
assert m.share_url and m.share_url.endswith("/s/" + m.sid) and f":{C.SHARE_PORT}/" in m.share_url
import re; assert re.fullmatch(r"[0-9]{4}-[0-9a-f]{8}", m.sid), m.sid
for i in (1, 2, 3): assert (C.TMP_DIR / m.sid / f"foto{i}_f.jpg").exists()
assert len(C.WIFI_PASS) >= 8                                  # WPA2 exige 8-63 caracteres
assert [s for s in seen if s[0] == "CAPTURE"] == [("CAPTURE", 1), ("CAPTURE", 2), ("CAPTURE", 3)]
assert (C.TMP_DIR / m.sid / "tira.jpg").exists() and (C.FINAL_DIR / f"{m.sid}.jpg").exists()
print("beeps:", hal.beeps[-8:])
# 6) timeouts
run(C.RESULT_TIMEOUT_S + 1); assert m.state == "ATTRACT", m.state
run(C.SLEEP_AFTER_S + 2); assert m.state == "SLEEP", m.state
hal.sim_set(button=True); run(0.2); assert m.state == "READY"
print("log:", (C.FINAL_DIR / "sesiones.log").read_text().strip())
print("TODO OK")
