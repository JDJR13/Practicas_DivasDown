#!/usr/bin/env python3
"""PROCESO 2 · vision_gui: camara, maquina de estados, composicion de la tira y servidor de la pantalla (127.0.0.1:8000).
No toca el hardware: boton, potenciometro, distancia y temperatura le llegan de control_daemon por IPC (RemoteHAL)."""
from __future__ import annotations
import argparse, logging, threading, time

from fotobut.servicios import config as C
from fotobut.logica.machine import Machine
from fotobut.comunicacion.remote_hal import RemoteHAL
from fotobut.servicios.sched import set_prio
from fotobut.comunicacion.server import serve

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
    logging.getLogger("fotobut.config").info(C.resumen_conf())                 # [C22-config] de donde salieron los valores
    for aviso in C.CONF_AVISOS:
        logging.getLogger("fotobut.config").warning(aviso)
    set_prio("vision_main", nice=-10)                    # [C8-T2] camara y vista previa: los hilos nuevos heredan nice -10
    import os
    os.umask(0o027)                                      # las fotos no quedan legibles para otros usuarios del sistema
    C.TMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(C.TMP_DIR, 0o750)
    except OSError:
        pass
    from fotobut.servicios.vigia import Vigia                             # [C22-watchdog] arranca antes que la camara: si esta se cuelga al
    pruebas: dict = {}                                   # iniciar, tampoco llega la senal de vida y systemd reinicia
    Vigia("vision_gui", pruebas, gracia_s=0).start()
    if a.sim:
        from fotobut.hardware.camera import SimCamera
        cam = SimCamera()
    else:
        try:
            from fotobut.hardware.camera import PiCamera
            cam = PiCamera()
        except Exception as e:                           # noqa: BLE001
            log.error("Camara real no disponible (%s): uso la simulada", e)
            from fotobut.hardware.camera import SimCamera
            cam = SimCamera()
    hal = RemoteHAL(sim=a.sim)
    m = Machine(hal, cam)
    hal.on_button = m.wake.set                           # el boton despierta la maquina al instante
    threading.Thread(target=m.run_forever, name="H_maquina", daemon=True).start()
    def h_ping() -> None:                                # 1 Hz: mide el RTT del socket (se resume en /api/ipc)
        from fotobut.servicios.sched import name_thread
        name_thread("H_ping")
        while True:
            hal.ping()
            time.sleep(1.0)
    threading.Thread(target=h_ping, daemon=True).start()
    httpd = serve(m, hal, cam, a.host, a.port)
    pruebas["H_maquina (maquina de estados)"] = lambda: m.latido.edad() < 8.0   # senal de vida solo si la maquina da vueltas
    log.info("LISTA interfaz en %s:%d  uptime=%.1f s", a.host, a.port, _uptime())   # evidencia del requisito de arranque (<= 25 s)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        hal.close()


if __name__ == "__main__":
    main()
