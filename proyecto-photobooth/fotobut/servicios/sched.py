"""Prioridades y nombres de hilo (clase 8). Se llama DENTRO de cada hilo, al arrancar.

Plan del Avance 1 (tabla de tareas)         Donde queda en el codigo
  T1 boton + maquina de estados  FIFO 80    H_boton (control_daemon)   -> SCHED_FIFO 80
  T2 camara / vista previa       nice -10   proceso vision_gui         -> nice -10
  T3 muestreo SPI (MCP3008)      nice  -5   H_sensores (control_daemon)-> nice -5
  T4 composicion del collage     nice   0   H_compositor (vision_gui)  -> nice 0
  T5 telemetria / OLED / HTTP    nice +10   H_oled (control), qr_httpd -> nice +10
Subir prioridad (FIFO o nice negativo) necesita CAP_SYS_NICE: lo da systemd con AmbientCapabilities.
"""
from __future__ import annotations
import ctypes, logging, os, threading

log = logging.getLogger("fotobut.sched")
_libc = None


def name_thread(name: str) -> None:
    """Nombre visible en `ps -L` / `top -H` (prctl PR_SET_NAME, maximo 15 caracteres)."""
    global _libc
    try:
        _libc = _libc or ctypes.CDLL(None, use_errno=True)
        _libc.prctl(15, name.encode()[:15], 0, 0, 0)
    except Exception:                                    # noqa: BLE001
        pass


def set_prio(name: str, fifo: int | None = None, nice: int | None = None) -> str:
    name_thread(name)
    tid = threading.get_native_id()
    res = "CFS nice 0"
    try:
        if fifo is not None:                             # [C8-T1] tiempo real para el boton
            os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(fifo))   # pid 0 = el hilo que llama
            res = f"SCHED_FIFO {fifo}"
        elif nice is not None:                           # [C8-CFS] prioridad relativa por hilo
            os.setpriority(os.PRIO_PROCESS, tid, nice)
            res = f"CFS nice {nice}"
    except (PermissionError, OSError) as e:
        res = f"SIN PERMISO ({e.strerror}): sigue en CFS nice 0 (falta CAP_SYS_NICE)"
    log.info("[C8] hilo %-13s tid=%d -> %s", name, tid, res)
    return res
