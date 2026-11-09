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

# 7) reposo: READY vuelve a ATTRACT tras NO_PRESENCE_S (5 s) sin presencia; con alguien enfrente NO se va
assert C.NO_PRESENCE_S == 5
hal.sim_set(distance=80); run(1.0); assert m.state == "READY"
run(C.NO_PRESENCE_S + 3); assert m.state == "READY", "con presencia debe quedarse en READY"
hal.sim_set(distance=None); run(C.NO_PRESENCE_S - 0.5); assert m.state == "READY", m.state
assert m.snapshot()["timeout_s"] == C.NO_PRESENCE_S and m.snapshot()["idle_ms"] >= 4000
run(1.0); assert m.state == "ATTRACT", m.state
# la perilla NO cuenta como presencia: sin MCP3008 su lectura flota y la cabina nunca volveria al inicio
hal.sim_set(button=True); run(0.2); assert m.state == "READY"
for k in range(int((C.NO_PRESENCE_S + 0.5) / 0.05)):
    hal.sim_set(pot=(k * 97) % 1024); clk.t += 0.05; hal._last_sample = -1; m.step()
assert m.state == "ATTRACT", ("perilla con ruido", m.state)
hal.sim_set(pot=450); run(0.6)
# fuera del rango 30-120 cm no cuenta como presencia
hal.sim_set(button=True); run(0.2); assert m.state == "READY"
hal.sim_set(distance=200); run(C.NO_PRESENCE_S + 0.5); assert m.state == "ATTRACT", m.state
hal.sim_set(distance=None)
# sin tramas del STM32 (sensor desconectado) se usa el respaldo de 30 s, no los 5 s
class NoUart(SimHAL):
    def read(self):
        i = super().read(); i.uart_ok = False; i.distance = None; return i
h2 = NoUart(); c2 = Clk(); m2 = Machine(h2, SimCamera(), c2)
def run2(sec, dt=0.05):
    for _ in range(int(sec / dt)): c2.t += dt; m2.step()
h2.sim_set(button=True); run2(0.2); assert m2.state == "READY"
run2(C.NO_PRESENCE_S + 5); assert m2.state == "READY", "sin sensor no debe aplicar el limite de 5 s"
run2(C.READY_TIMEOUT_S); assert m2.state == "ATTRACT", m2.state

# 8) boton azul (reset): cancela desde cualquier estado y la siguiente sesion sale limpia
def free_blocks(): return m.pool.sem_libres._value
def until(state, shot=None, lim=600):
    for _ in range(lim):
        clk.t += 0.05; hal._last_sample = -1; m.step()
        if m.state == state and (shot is None or m.shot == shot): return
    raise AssertionError(f"no llego a {state} {shot}: {m.state} {m.shot}")
def reset_and_check(desc):
    hal.sim_set(reset=True); run(0.1)
    assert m.state == "ATTRACT", (desc, m.state)
    assert m.sid is None and m.photos == [] and m.strip_url is None and m.qr_url is None, desc
    t0 = time.time()
    while free_blocks() != C.SHOTS and time.time() - t0 < 10: time.sleep(0.02)
    assert free_blocks() == C.SHOTS, (desc, "el pool no recupero sus 3 bloques", free_blocks())
    assert (hal.beeps[-1][0], hal.beeps[-1][1]) == (C.RESET_HZ, C.RESET_MS), desc
    print("reset OK:", desc)

assert m.state == "ATTRACT"; hal.sim_set(reset=True); run(0.1); assert m.state == "ATTRACT"          # en reposo: no rompe nada
hal.sim_set(button=True); run(0.2); assert m.state == "READY"; reset_and_check("READY")
hal.sim_set(button=True); run(0.2); hal.sim_set(button=True); run(0.1); assert m.state == "COUNTDOWN"
run(1.0); reset_and_check("COUNTDOWN de la foto 1 (0 fotos en el pool)")
hal.sim_set(button=True); run(0.2); hal.sim_set(button=True); run(0.1); until("CAPTURE", 1)
reset_and_check("CAPTURE 1 (1 foto en el pool)")
hal.sim_set(button=True); run(0.2); hal.sim_set(button=True); run(0.1); until("COUNTDOWN", 3)
reset_and_check("COUNTDOWN de la foto 3 (2 fotos en el pool)")
hal.sim_set(button=True); run(0.2); hal.sim_set(button=True); run(0.1); until("CAPTURE", 3)
reset_and_check("CAPTURE 3 (el compositor ya tiene las 3)")
hal.sim_set(button=True); run(0.2); hal.sim_set(button=True); run(0.1); until("PROCESSING")
reset_and_check("PROCESSING")
# la tira de la sesion cancelada no se cuela en la siguiente: sesion completa despues de los resets
done_before = m.sessions_done
hal.sim_set(button=True); run(0.2); hal.sim_set(button=True); run(0.1); assert m.state == "COUNTDOWN" and m.shot == 1
sid_new = m.sid
for _ in range(900):
    clk.t += 0.05; hal._last_sample = -1; m.step()
    if m.state == "PROCESSING": wait_strip()
    if m.state == "RESULT": break
assert m.state == "RESULT" and m.sid == sid_new and len(m.photos) == 3, (m.state, m.sid, m.photos)
assert m.strip_url == f"/strip/{sid_new}.jpg" and m.share_url.endswith("/s/" + sid_new)
assert m.sessions_done == done_before + 1, (m.sessions_done, done_before)
assert all(f"/{sid_new}/" in p for p in m.photos)
reset_and_check("RESULT")
assert (C.FINAL_DIR / f"{sid_new}.jpg").exists()               # la tira ya guardada no se borra con el reset
hal.sim_set(reset=True); m._go("SLEEP"); run(0.1); assert m.state == "ATTRACT"   # tambien despierta la pantalla
# con alguien enfrente: el reset muestra el inicio y solo tras volver a detectar presencia (5 lecturas) pasa a READY
hal.sim_set(distance=80); run(1.0); assert m.state == "READY" and m.consec >= C.PRESENCE_SAMPLES
hal.sim_set(reset=True); clk.t += 0.05; hal._last_sample = -1; m.step(); assert m.state == "ATTRACT", m.state
run(0.15); assert m.state == "ATTRACT", m.state
run(0.5); assert m.state == "READY", m.state
hal.sim_set(distance=None)
print("TODO OK")
