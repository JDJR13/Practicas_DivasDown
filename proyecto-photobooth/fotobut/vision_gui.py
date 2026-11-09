#!/usr/bin/env python3
"""PROCESO 2 · vision_gui: camara, maquina de estados, composicion de la tira y servidor de la pantalla (127.0.0.1:8000).
No toca el hardware: boton, potenciometro, distancia y temperatura le llegan de control_daemon por IPC (RemoteHAL)."""
from __future__ import annotations
import argparse, logging, threading, time

from . import config as C
from .machine import Machine
from .remote_hal import RemoteHAL
from .sched import set_prio
from .server import serve

log = logging.getLogger("fotobut.vision")


def _uptime() -> float:
    try:
        return float(open("/proc/uptime").read().split()[0])
    except Exception:                                    # noqa: BLE001
        return -1.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true", help="camara y hardware simulados")
    ap.add_argument("--host", default=C.UI_HOST)
    ap.add_argument("--port", type=int, default=C.UI_PORT)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s vision: %(message)s")
    set_prio("vision_main", nice=-10)                    # [C8-T2] camara y vista previa: los hilos nuevos heredan nice -10
    if a.sim:
        from .camera import SimCamera
        cam = SimCamera()
    else:
        try:
            from .camera import PiCamera
            cam = PiCamera()
        except Exception as e:                           # noqa: BLE001
            log.error("Camara real no disponible (%s): uso la simulada", e)
            from .camera import SimCamera
            cam = SimCamera()
    hal = RemoteHAL(sim=a.sim)
    m = Machine(hal, cam)
    hal.on_button = m.wake.set                           # el boton despierta la maquina al instante
    threading.Thread(target=m.run_forever, name="H_maquina", daemon=True).start()
    def h_ping() -> None:                                # 1 Hz: mide el RTT del socket (se resume en /api/ipc)
        from .sched import name_thread
        name_thread("H_ping")
        while True:
            hal.ping()
            time.sleep(1.0)
    threading.Thread(target=h_ping, daemon=True).start()
    httpd = serve(m, hal, cam, a.host, a.port)
    log.info("LISTA interfaz en %s:%d  uptime=%.1f s", a.host, a.port, _uptime())   # evidencia del requisito de arranque (<= 25 s)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        hal.close()


if __name__ == "__main__":
    main()
