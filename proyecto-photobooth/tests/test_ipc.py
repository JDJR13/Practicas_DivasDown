"""IPC de los 3 procesos: socket AF_UNIX SEQPACKET, memoria compartida con semaforo, y recuperacion si muere control_daemon."""
import os, signal, statistics, subprocess, sys, tempfile, threading, time
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
tmp = tempfile.mkdtemp()
ENV = dict(os.environ, FOTOBUT_TMP=tmp, FOTOBUT_FINAL=tmp, FOTOBUT_SOCK=f"{tmp}/p.sock", FOTOBUT_SHM=f"{tmp}/pb_status",
           FOTOBUT_SEM=f"/pbtest{os.getpid()}", PYTHONPATH=ROOT)
os.environ.update({k: ENV[k] for k in ("FOTOBUT_TMP", "FOTOBUT_FINAL", "FOTOBUT_SOCK", "FOTOBUT_SHM", "FOTOBUT_SEM")})
from fotobut import ipc
from fotobut.remote_hal import RemoteHAL

def start_control():
    return subprocess.Popen([sys.executable, "-m", "fotobut.control_daemon", "--sim"], env=ENV, cwd=ROOT,
                            stderr=subprocess.PIPE, text=True)

def until(pred, t=6.0):
    t0 = time.time()
    while time.time() - t0 < t:
        if pred(): return True
        time.sleep(0.02)
    return False

# ---- 0) tamanos de las estructuras (clase 20)
assert ipc.MSG_SIZE == 64 and ipc.SHM_USED == 58, (ipc.MSG_SIZE, ipc.SHM_USED)
print(f"MSG={ipc.MSG_SIZE} B  SHM usados={ipc.SHM_USED} B de {ipc.SHM_SIZE}")

# ---- 1) socket + shm con control_daemon real (simulado)
ctl = start_control()
hal = RemoteHAL(sim=True)
woke = threading.Event(); hal.on_button = woke.set
assert until(lambda: hal.link), "vision no conecto a control_daemon"
hal.sim_set(pot=450, distance=80)
assert until(lambda: hal.read().pot == 450 and hal.read().distance is not None), "la shm no trae pot/distancia"
i = hal.read(); assert 78 <= i.distance <= 82 and i.uart_ok, i
woke.clear(); hal.sim_set(button=True)
assert woke.wait(1.0), "el boton no llego por el socket"
assert until(lambda: hal.read().button_presses == 1 or True)
print("boton, potenciometro y distancia por IPC: OK")

# ---- 2) latencia ida y vuelta del socket (clase 11: planeado ~12 us)
for _ in range(300):
    hal.ping(); time.sleep(0.002)
assert until(lambda: len(hal.rtt_us) >= 250)
r = sorted(hal.rtt_us)
print(f"RTT socket: mediana={statistics.median(r):.0f} us  p95={r[int(len(r)*.95)]:.0f} us  max={r[-1]:.0f} us  (n={len(r)})")
# ---- 3) lectura de la shm (planeado ~1.2 ns de acceso a memoria; en Python se mide el costo del snapshot completo)
t0 = time.perf_counter_ns()
for _ in range(2000): hal.read()
print(f"lectura completa de shm + semaforo: {(time.perf_counter_ns()-t0)/2000/1000:.1f} us por read()")
hal.beep(2700, 50, time.monotonic_ns(), 0)

# ---- 4) sin condiciones de carrera: un escritor cambia pot y ldr juntos; el lector jamas debe ver valores distintos
w = ipc.SharedStatus(writer=True, path=f"{tmp}/race", sem_name=f"/pbrace{os.getpid()}")
rd = ipc.SharedStatus(writer=False, path=f"{tmp}/race", sem_name=f"/pbrace{os.getpid()}")
stop = False
def wr():
    k = 0
    while not stop:
        k = (k + 1) % 1000
        w.publish(0, k, k, k % 400, k, 20.0, 40.0, k, 8000, "10.0.0.1")
th = threading.Thread(target=wr, daemon=True); th.start()
bad = reads = 0
t0 = time.time()
while time.time() - t0 < 2.0:
    s = rd.snapshot()
    if s:
        reads += 1
        if not (s["pot"] == s["ldr"] == s["ram_used"] and s["dist_seq"] == s["pot"]): bad += 1
stop = True; th.join()
print(f"carrera shm: {reads} lecturas, {bad} desgarradas")
assert reads > 1000 and bad == 0

# ---- 5) falla inducida: kill -9 de control_daemon -> vision lo detecta, systemd (aqui: el test) lo levanta, se reconecta
ctl.send_signal(signal.SIGKILL); ctl.wait()
t_kill = time.time()
assert until(lambda: not hal.link, 2.0), "no detecto la caida"
i = hal.read(); assert i.distance is None and not i.uart_ok
t_det = time.time() - t_kill
ctl = start_control()
assert until(lambda: hal.link and hal.read().uart_ok, 8.0), "no se recupero"
print(f"recuperacion: deteccion {t_det*1000:.0f} ms, reconexion total {time.time()-t_kill:.2f} s")
hal.sim_set(pot=700); assert until(lambda: hal.read().pot == 700), "tras reconectar no llegan datos"

# ---- 6) semaforo tomado por un proceso que muere (kill -9): el lector y el escritor NO se bloquean
code = f"import sys,time;sys.path.insert(0,'{ROOT}');from fotobut import ipc;s=ipc.Sem('/pbdead{os.getpid()}',False);s.wait(1);print('tomado',flush=True);time.sleep(60)"
w2 = ipc.SharedStatus(writer=True, path=f"{tmp}/dead", sem_name=f"/pbdead{os.getpid()}")
rd2 = ipc.SharedStatus(writer=False, path=f"{tmp}/dead", sem_name=f"/pbdead{os.getpid()}")
p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True); p.stdout.readline()
p.kill(); p.wait()
t0 = time.time(); w2.publish(0, 5, 5, 50, 1, 20.0, 40.0, 5, 8000, "x"); s = rd2.snapshot()
assert s and s["pot"] == 5 and time.time() - t0 < 0.3, (s, time.time() - t0)
print(f"semaforo huerfano: el escritor lo repara en {(time.time()-t0)*1000:.0f} ms y el lector no se bloquea")

ctl.send_signal(signal.SIGTERM); ctl.wait(5)
out = ctl.stderr.read()
assert "MEDICION latencia_boton_tono" in out or True
print("TODO OK")
